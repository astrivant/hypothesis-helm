"""
Apply measured sampling floors only within an explicitly calibrated structural profile.
"""

import json
import logging
import math
from collections.abc import Sequence
from pathlib import Path

from hypothesis_helm.charts.model import Chart, merge_values
from hypothesis_helm.compiler.passes.sampling import fingerprint, profile
from hypothesis_helm.execution.sampling import Sampling
from hypothesis_helm.schemas.contracts import configuration_key, mapping, sequence

CALIBRATION_VERSION = "aggressive-calibration-v1"
DEFAULT_CALIBRATION = Path(__file__).with_name("calibration.json")
LOGGER = logging.getLogger(__name__)


def coordinates(description: dict[str, object]) -> dict[str, float]:
    """
    Express calibration distances in explicitly named, dimensionless relative changes.

    Args:
        description (dict[str, object]): Structural profile and reachable region counts.

    Returns:
        dict[str, float]: Numeric coordinates used for range checks and nearest-profile distance.
    """
    features = mapping(description["features"])
    regions = [sequence(row) for row in sequence(description["region_sizes"])]
    total = sum(float(str(row[0])) for row in regions)
    return {
        **{key: float(str(features[key])) for key in ("maximum_score", "input_fields", "gate_depth", "interaction_order")},
        "domain_bits": sum(math.log2(int(str(size))) for size in sequence(features["domain_sizes"])),
        "regions": float(len(regions)),
        "smallest_region_fraction": min((float(str(row[0])) / total for row in regions), default=0),
        "eligible_cases": sum(float(str(row[1])) for row in regions),
    }


def matching_profiles(document: dict[str, object], description: dict[str, object]) -> tuple[list[dict[str, object]], str, float | None]:
    """
    Match exact profiles first, then only measured nearby profiles inside the observed range.

    Args:
        document (dict[str, object]): Versioned calibration and optional measured approximation policy.
        description (dict[str, object]): Current chart's measurements and filtering context.

    Returns:
        tuple[list[dict[str, object]], str, float | None]: Selected evidence, match method and smallest relative distance.
    """
    profiles = [mapping(row) for row in sequence(document["profiles"])]
    exact = [row for row in profiles if row["descriptor"] == description]
    if exact:
        return exact, "exact", 0.0
    approximation = mapping(document.get("approximation", {}))
    if approximation.get("enabled") is not True or approximation.get("metric") != "maximum-relative-coordinate-change-v1":
        return [], "unmatched", None
    radius = float(str(approximation.get("radius", 0)))
    if not math.isfinite(radius) or not 0 < radius <= 0.5:
        return [], "unsupported approximation radius", None
    kinds = mapping(description["features"]).get("domain_kinds")
    domain_sizes = set(sequence(mapping(description["features"])["domain_sizes"]))
    compatible = [
        row
        for row in profiles
        if all(mapping(row["descriptor"]).get(key) == description.get(key) for key in ("profile_version", "context", "unit"))
        and mapping(mapping(row["descriptor"])["features"]).get("domain_kinds") == kinds
        and set(sequence(mapping(mapping(row["descriptor"])["features"])["domain_sizes"])) == domain_sizes
    ]
    if not compatible:
        return [], "unmatched domain or execution context", None
    target = coordinates(description)
    measured = [coordinates(mapping(row["descriptor"])) for row in compatible]
    if any(not min(point[key] for point in measured) <= value <= max(point[key] for point in measured) for key, value in target.items()):
        return [], "outside measured range", None
    distances = [
        max(abs(point[key] - value) / max(abs(point[key]), abs(value), 1e-12) for key, value in target.items()) for point in measured
    ]
    neighbors = [row for row, distance in zip(compatible, distances, strict=True) if distance <= radius]
    return neighbors, "nearby" if neighbors else "outside measured matching radius", min(distances)


def changed_fields(defaults: dict[str, object], overrides: dict[str, object]) -> set[str]:
    """
    Count changed leaf paths separately from complete input configurations.

    Args:
        defaults (dict[str, object]): Baseline values.
        overrides (dict[str, object]): Schema-valid case overrides.

    Returns:
        set[str]: Unambiguous JSON-encoded paths whose effective values differ.
    """
    changed: set[str] = set()

    def visit(left: object, right: object, path: tuple[str, ...]) -> None:
        """
        Compare corresponding subtrees without conflating scalars and containers.

        Args:
            left (object): Baseline subtree.
            right (object): Effective subtree.
            path (tuple[str, ...]): Original YAML keys.

        Returns:
            None: Changed leaves are accumulated.
        """
        if isinstance(left, dict) and isinstance(right, dict):
            for key in left.keys() | right.keys():
                if key not in left or key not in right:
                    changed.add(json.dumps((*path, key)))
                else:
                    visit(left[key], right[key], (*path, key))
        elif type(left) is not type(right) or left != right:
            changed.add(json.dumps(path))

    visit(defaults, merge_values(defaults, overrides), ())
    return changed


def descriptor(analysis: dict[str, object], topology: dict[str, object], context: dict[str, object]) -> dict[str, object]:
    """
    Match complexity, structural features and the actual post-filter population together.

    Args:
        analysis (dict[str, object]): Fresh compiler measurements.
        topology (dict[str, object]): Reachable region counts before and after ordinary filtering.
        context (dict[str, object]): Interaction strength and filter settings.

    Returns:
        dict[str, object]: Exact calibration cell; no interpolation or extrapolation is performed.
    """
    return {
        "profile_version": analysis["version"],
        "features": analysis["features"],
        "region_sizes": sorted(
            [int(str(mapping(row)["candidates"])), int(str(mapping(row)["retained"]))] for row in sequence(topology.get("regions", []))
        ),
        "context": context,
        "unit": "non-default configuration",
    }


def select(
    chart: Chart,
    sampling: Sampling,
    values: Sequence[dict[str, object]],
    seed: int,
    *,
    protected: set[str],
    analysis: dict[str, object],
    topology: dict[str, object],
    context: dict[str, object],
) -> tuple[Sequence[dict[str, object]], dict[str, object]]:
    """
    Preserve representatives, apply calibrated floors and report any conservative fallback.

    Args:
        chart (Chart): Current chart and effective values.
        sampling (Sampling): Requested aggressive preset and optional calibration path.
        values (Sequence[dict[str, object]]): Eligible cases after ordinary filtering.
        seed (int): Shared reproducible selection seed.
        protected (set[str]): Topology representatives and unresolved cases.
        analysis (dict[str, object]): Fresh measurements taken before planning.
        topology (dict[str, object]): Observed compiler region population.
        context (dict[str, object]): Settings that affect the eligible population.

    Returns:
        tuple[Sequence[dict[str, object]], dict[str, object]]: Selected configurations and decision evidence.
    """
    reason = None
    cell = None
    document: dict[str, object] = {}
    method, distance = "unmatched", None
    match = descriptor(analysis, topology, context)
    try:
        if fingerprint(chart) != analysis.get("fingerprint"):
            analysis = profile(chart)
            raise ValueError("chart changed after analysis; recalculated complexity but retained the existing plan")
        if analysis["status"] != "supported":
            raise ValueError(str(analysis.get("reason", "maximum complexity is unknown")))
        if topology.get("fallback") or topology.get("unknown_cases_retained"):
            raise ValueError("the topology contains unresolved cases")
        path = Path(sampling.calibration) if sampling.calibration else DEFAULT_CALIBRATION
        document = mapping(json.loads(path.read_text()))
        if document.get("version") != CALIBRATION_VERSION or document.get("status") != "complete":
            raise ValueError("calibration is incomplete or uses an unsupported version")
        matches, method, distance = matching_profiles(document, match)
        if not matches:
            raise ValueError("chart complexity or topology is outside the measured calibration profiles")
        for row in matches:
            for key in ("minimum_cases", "minimum_fields"):
                if type(row[key]) is not int or int(str(row[key])) < (1 if key == "minimum_cases" else 0):
                    raise ValueError("calibration contains an invalid sample floor")
        cell = {
            "minimum_cases": max(int(str(row["minimum_cases"])) for row in matches),
            "minimum_fields": max(int(str(row["minimum_fields"])) for row in matches),
            "evidence": [row.get("evidence") for row in matches],
        }
    except (ValueError, OSError, KeyError, TypeError) as exc:
        reason = str(exc)
        cell = None
    floor = int(str(cell["minimum_cases"])) if cell else 1
    field_floor = int(str(cell["minimum_fields"])) if cell else 0
    selected, report = Sampling(70 if cell else 100, floor).select(
        values,
        configuration_key,
        seed,
        protected=protected,
        fields=lambda value: changed_fields(chart.defaults, value),
        minimum_fields=field_floor,
    )
    try:
        if fingerprint(chart) != analysis.get("fingerprint"):
            reason = "chart changed during selection; additional sampling disabled"
            selected, report = Sampling().select(values, configuration_key, seed, protected=protected)
    except (ValueError, OSError) as exc:
        reason = str(exc)
        selected, report = Sampling().select(values, configuration_key, seed, protected=protected)
    report["aggressive"] = {
        "requested_percent": 70,
        "analysis": analysis,
        "descriptor": match,
        "calibration_version": document.get("version"),
        "calibration_id": document.get("id"),
        "match": method,
        "relative_distance": distance,
        "evidence": cell.get("evidence") if cell else None,
        "fallback": reason,
        "independent_validation": False,
        "interpretation": "Empirical calibration on generated charts; no arbitrary-chart bug-recall guarantee.",
    }
    LOGGER.info("Aggressive sampling: %s/%s cases retained; %s", len(selected), len(values), reason or "matched measured profile")
    return selected, report

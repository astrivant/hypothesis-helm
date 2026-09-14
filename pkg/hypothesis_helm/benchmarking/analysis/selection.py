"""
Share production filter presets and their recorded decisions across benchmark studies.
"""

from collections.abc import Sequence

from hypothesis_helm.charts.model import Chart
from hypothesis_helm.charts.planning import PlanningOptions, select_cases
from hypothesis_helm.compiler.passes.sampling import profile
from hypothesis_helm.execution.sampling import Sampling
from hypothesis_helm.schemas.contracts import mapping

PRESETS = ("filter", "filter-adaptive")
LABELS = {"filter": "--filter", "filter-adaptive": "--filter-adaptive"}


def select(
    chart: Chart,
    values: Sequence[dict[str, object]],
    strategy: str,
    seed: int,
    *,
    strength: int = 2,
) -> tuple[Sequence[dict[str, object]], dict[str, object]]:
    """
    Select an existing finite plan using the same preset logic as chart testing.

    Args:
        chart (Chart): Fresh fixture, including injected faults.
        values (Sequence[dict[str, object]]): Unique non-default configurations in the study's plan.
        strategy (str): Public filter preset name.
        seed (int): Reproducible selection and traversal seed.
        strength (int): Interaction strength represented by the plan.

    Returns:
        tuple[Sequence[dict[str, object]], dict[str, object]]: Initial selection and full topology/calibration evidence.
    """
    if strategy not in PRESETS:
        raise ValueError(f"unknown filter preset: {strategy}")
    aggressive = strategy == "filter-adaptive"
    options = PlanningOptions(
        random_seed=seed,
        permutations=strength,
        trim_topology=2,
        expand_failures=True,
        sampling=Sampling(aggressive=aggressive),
    )
    selected, topology, sampling = select_cases(chart, values, options, profile(chart) if aggressive else None)
    return selected, {"topology": topology, "sampling": sampling, "strength": strength, "trim_topology": 2, "expand_failures": True}


def decision(evidence: dict[str, object]) -> dict[str, object]:
    """
    Flatten sampling evidence for CSV columns and readable comparison tables.

    Args:
        evidence (dict[str, object]): Initial selection's topology and sampling report.

    Returns:
        dict[str, object]: Match, fallback, floor and actual retention fields; absent evidence stays empty.
    """
    sampling = mapping(evidence.get("sampling", {}))
    aggressive = mapping(sampling.get("aggressive", {}))
    return {
        "sample_eligible": sampling.get("eligible"),
        "sample_retained": sampling.get("retained"),
        "sample_minimum": sampling.get("minimum"),
        "sample_minimum_fields": sampling.get("minimum_fields"),
        "profile_match": aggressive.get("match"),
        "sampling_fallback": aggressive.get("fallback"),
        "calibration_id": aggressive.get("calibration_id"),
    }


def explanation(rows: list[dict[str, object]]) -> list[str]:
    """
    Explain preset behavior and publish measured sampling decisions beside comparison tables.

    Args:
        rows (list[dict[str, object]]): Flat measurements containing optional aggressive decisions.

    Returns:
        list[str]: Markdown lines describing actual non-default sampling counts and fallback reasons.
    """
    measured = [row for row in rows if row.get("strategy") == "filter-adaptive"]
    if not measured:
        return []
    lines = [
        "",
        "`--filter` and `--filter-adaptive` use topology level 2 and enable failure expansion. "
        "Aggressive sampling recomputes chart complexity, protects structural regions and applies "
        "the packaged calibration. An unmatched or unsupported chart keeps the ordinary filtered selection; "
        "70% retention is not forced. Expansion-off columns are controlled ablations of these presets.",
        "",
        "**Aggressive sampling decisions.** Counts below exclude the always-retained default configuration "
        "and precede failure expansion. Case and field floors apply only to matched calibrations.",
        "",
        "| Fixture | Match | Retained / eligible | Case floor | Field floor | Fallback reason |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    seen: set[str] = set()
    for row in measured:
        name = row.get("case", row.get("structure", "chart"))
        line = (
            f"| {name} | {row.get('profile_match') or '-'} | {row.get('sample_retained', '-')} / "
            f"{row.get('sample_eligible', '-')} | {row.get('sample_minimum') or '-'} | "
            f"{row.get('sample_minimum_fields', '-')} | {row.get('sampling_fallback') or '-'} |"
        )
        if line not in seen:
            lines.append(line)
            seen.add(line)
    return [*lines, ""]

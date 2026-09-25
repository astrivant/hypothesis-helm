"""
Measure a bounded output reference separately from chart testing and replay the recorded selection policy.
"""

import itertools
import json
import time
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path

from jsonschema import validators

from hypothesis_helm.analysis.output_space import ENCODING, manifest_vector
from hypothesis_helm.analysis.sensitivity import Mutation
from hypothesis_helm.charts.model import Chart
from hypothesis_helm.charts.testing.planning import PlanningOptions, select_cases
from hypothesis_helm.compiler.passes.sampling import profile
from hypothesis_helm.execution.planning.sampling import Sampling
from hypothesis_helm.schemas.contracts import configuration_key, json_value, mapping, sequence

__all__ = ("measure_reference",)

type _Candidate = tuple[dict[str, object], list[Mutation]]


def _candidates(chart: Chart, changes: Sequence[Mutation], limit: int, order: int) -> Iterator[_Candidate]:
    """
    Alternate single and joint changes from a fixed baseline without materializing their product.

    Args:
        chart (Chart): Supplied baseline and input schema.
        changes (Sequence[Mutation]): Seeded, schema-valid single-field changes.
        limit (int): Reference configuration ceiling, including the baseline.
        order (int): Maximum joint order allowed by the scan's permutation strength.

    Yields:
        _Candidate: Unique schema-valid configurations and their changed paths.
    """
    yield chart.defaults, []
    validator = validators.validator_for(chart.schema)(chart.schema)
    seen = {configuration_key(chart.defaults)}
    groups = [iter(itertools.combinations(changes, size)) for size in range(1, min(order, len(changes)) + 1)]
    attempted = 0
    while groups and len(seen) < limit and attempted < limit * 8:
        for group in list(groups):
            selected = next(group, None)
            if selected is None:
                groups.remove(group)
                continue
            attempted += 1
            values = chart.defaults
            for mutation in selected:
                values = mutation.apply(values)
            identity = configuration_key(values)
            if identity not in seen and validator.is_valid(json_value(values)):
                seen.add(identity)
                yield values, list(selected)
                if len(seen) == limit:
                    return


def _retained(
    chart: Chart,
    candidates: list[tuple[dict[str, object], list[Mutation]]],
    record: dict[str, object],
    settings: dict[str, object],
) -> tuple[set[str] | None, dict[str, object]]:
    """
    Use saved path ownership or the production finite selectors without inventing a filtering decision.

    Args:
        chart (Chart): Prepared measurement chart.
        candidates (list[tuple[dict[str, object], list[Mutation]]]): Bounded reference, including its baseline.
        record (dict[str, object]): Original chart test record and artifact location.
        settings (dict[str, object]): Recorded scan selection settings.

    Returns:
        tuple[set[str] | None, dict[str, object]]: Retained identities, or unknown selection with its reason.
    """
    baseline = configuration_key(chart.defaults)
    sampling = mapping(settings.get("sampling", {}))
    filtering = bool(settings.get("filter") or settings.get("filter_adaptive"))
    trim, topology = int(str(settings.get("trim", 0))), int(str(settings.get("trim_topology", 0)))
    inventory = Path(str(record.get("artifacts", ""))) / "path-inventory.json"
    path_mode = "traversal" in record or record.get("mode") == "path-properties"
    if path_mode and inventory.is_file():
        document = mapping(json.loads(inventory.read_text()))
        selected = [tuple(sequence(path)) for path in sequence(document["paths"])]

        def covered(mutation: Mutation) -> bool:
            """
            Include changes reachable from a selected property, including wildcard array paths.

            Args:
                mutation (Mutation): Concrete field change.

            Returns:
                bool: A selected property owns this path or one of its ancestors.
            """
            return any(
                len(path) <= len(mutation.path)
                and all(left == right or left == "*" for left, right in zip(path, mutation.path, strict=False))
                for path in selected
            )

        return {configuration_key(values) for values, changes in candidates if all(covered(mutation) for mutation in changes)}, {
            "label": "Recorded path selection",
            "scope": "reference changes reachable through retained path properties",
        }
    if not filtering and not trim and not topology and float(str(sampling.get("percent", 100))) == 100:
        return {configuration_key(values) for values, _ in candidates}, {"label": "No filtering", "scope": "same reference in both panels"}
    if path_mode:
        return None, {"label": "Selection unavailable", "reason": "The scan's path inventory is unavailable."}
    if not all(key in settings for key in ("trim", "trim_topology")):
        return None, {"label": "Selection unavailable", "reason": "The historical scan did not record all finite filtering options."}
    policy = Sampling(
        float(str(sampling.get("percent", 100))),
        int(str(sampling.get("minimum", 128))),
        bool(sampling.get("aggressive", False)),
    )
    options = PlanningOptions(
        trim=trim,
        trim_topology=2 if filtering else topology,
        sampling=policy,
        random_seed=int(str(settings.get("seed", 0))),
        permutations=int(str(settings.get("permutations") or 2)),
    )
    selected_values, regions, sampling_report = select_cases(
        chart, [values for values, _ in candidates[1:]], options, profile(chart) if policy.aggressive else None
    )
    label = "--filter-adaptive" if policy.aggressive else "--filter" if filtering else f"random filter {trim}; topology filter {topology}"
    return {baseline, *(configuration_key(values) for values in selected_values)}, {
        "label": label,
        "scope": "production selectors replayed on the bounded reference; not a reconstruction of the full test plan",
        "topology": regions,
        "sampling": sampling_report,
        "excludes": "runtime rejection, equivalence reuse and failure expansion; these are not selection-stage filtering",
    }


def measure_reference(
    chart: Chart,
    changes: Sequence[Mutation],
    render: Callable[[dict[str, object]], object],
    record: dict[str, object],
    settings: dict[str, object],
    *,
    limit: int = 64,
    seconds: float = 60,
) -> dict[str, object]:
    """
    Record comparable output vectors before selection and their retained subset.

    Args:
        chart (Chart): Prepared chart and schema-valid defaults.
        changes (Sequence[Mutation]): Seeded scalar changes, independent of scan findings.
        render (Callable[[dict[str, object]], object]): Controlled, bounded renderer.
        record (dict[str, object]): Original scan record used to resolve path selection.
        settings (dict[str, object]): Original scan policy.
        limit (int): Maximum measured configurations per chart, including defaults.
        seconds (float): Admission budget; renderer invocations must also respect the remaining deadline.

    Returns:
        dict[str, object]: Sampled outputs, selection metadata and explicit failed or unfinished measurements.
    """
    if limit < 1 or seconds <= 0:
        raise ValueError("Reference sample and time limits must be positive")
    deadline = time.monotonic() + seconds
    candidates = list(_candidates(chart, changes, limit, int(str(settings.get("permutations") or 2))))
    try:
        selected, selection = _retained(chart, candidates, record, settings)
    except Exception as error:
        selected, selection = None, {"label": "Selection unavailable", "reason": str(error)}
    rows = []
    failed = 0
    status = "complete"
    for values, changes_in_case in candidates:
        if time.monotonic() >= deadline:
            status = "time-limit"
            break
        try:
            output = render(values)
            vector = manifest_vector(output)
        except TimeoutError:
            status = "time-limit"
            break
        except Exception:
            # A failed render has no output coordinate. It must not become an
            # origin point or an additional chart finding in this measurement.
            failed += 1
            continue
        rows.append(
            {
                "vector": vector,
                "retained": configuration_key(values) in selected if selected is not None else None,
                "paths": [list(mutation.path) for mutation in changes_in_case],
            }
        )
    return {
        "version": 1,
        "encoding": ENCODING,
        "status": status,
        "selection": selection,
        "sample_limit": limit,
        "planned": len(candidates),
        "measured": len(rows),
        "render_failures": failed,
        "remaining": len(candidates) - len(rows) - failed,
        "observations": rows,
        "population": "bounded schema-valid Boolean/integer changes and joint changes from supplied defaults",
        "complete_output_space": False,
        "test_findings_unchanged": True,
    }

"""
Discover unique value paths, then visit filtered path properties within one budget.
"""

import hashlib
import json
import logging
import math
import time
from pathlib import Path

from hypothesis import strategies as st

from hypothesis_helm.charts.generate import Model, ValuePath, coalesce, enumerate_paths
from hypothesis_helm.charts.generated import path_values
from hypothesis_helm.charts.runner import Chart, RenderFailure, _default_paths, check_chart, render
from hypothesis_helm.compiler.inputs import FieldCoverage, InputInventory
from hypothesis_helm.execution.traversal import ALGORITHM, STRATEGIES, order_paths
from hypothesis_helm.reporting.budget import TimeLimitReached, execution_timer
from hypothesis_helm.reporting.progress import format_path
from hypothesis_helm.schemas.contracts import schema_strategy
from hypothesis_helm.schemas.priority import PriorityInputs

LOGGER = logging.getLogger(__name__)
GENERATION_ERRORS = {"Unsatisfiable", "FailedHealthCheck", "SchemaError", "InvalidArgument"}


def path_strategy(chart: Chart, entry: ValuePath, generation_schema: dict[str, object]) -> st.SearchStrategy[dict[str, object]]:
    """
    Generate one target path in baseline or schema-valid dependent context.

    Args:
        chart (Chart): Original chart whose schema validates complete candidates.
        entry (ValuePath): One discovered and filtered path strategy.
        generation_schema (dict[str, object]): Generation-only parent type information.

    Returns:
        st.SearchStrategy[dict[str, object]]: Complete values for the selected path property.
    """

    @st.composite
    def candidate(draw: st.DrawFn) -> dict[str, object]:
        """
        Draw a path value and resolve its wildcard or dependent parent context.

        Args:
            draw (st.DrawFn): Hypothesis strategy draw function.

        Returns:
            dict[str, object]: Original-schema-valid values with the selected path varied.
        """
        value = draw(schema_strategy(entry.schema))
        return path_values(chart, entry.path, value, draw(st.data()), generation_schema=generation_schema)

    return candidate()


def check_paths(
    chart: Chart,
    *,
    budget: float,
    max_examples: int,
    seed: int,
    helm: str,
    timeout: float,
    artifacts: Path,
    filtering: bool = False,
    traversal_strategy: str = "random",
    fail_fast: bool = False,
) -> dict[str, object]:
    """
    Schedule each discovered path once after filtering, retaining partial coverage.

    A path property can draw and shrink multiple values. Completing the path list
    does not exhaust all values or all joint configurations. Discovery precedes
    the execution budget; an enclosing scan deadline can still interrupt discovery.

    Args:
        chart (Chart): Original source chart, schema, and supplied defaults.
        budget (float): Chart execution budget in seconds, after path discovery.
        max_examples (int): Maximum successful examples for each path property.
        seed (int): Shared seed for path ordering and Hypothesis value generation.
        helm (str): Helm executable.
        timeout (float): Per-render subprocess timeout.
        artifacts (Path): Root for path findings and the complete traversal inventory.
        filtering (bool): Apply known-input generation restrictions before ordering.
        traversal_strategy (str): Random, linear, shallow, or deep path traversal.
        fail_fast (bool): Stop after the first observed failure without shrinking.

    Returns:
        dict[str, object]: Visited, completed, incomplete, and remaining path evidence.
    """
    if traversal_strategy not in STRATEGIES:
        raise ValueError(f"traversal_strategy must be one of {', '.join(STRATEGIES)}")
    if not math.isfinite(budget) or budget <= 0 or max_examples < 1 or timeout <= 0:
        raise ValueError("budget, max_examples, and timeout must be positive")
    planning_started = time.monotonic()
    inventory = InputInventory.build(chart)
    if filtering:
        priority = PriorityInputs.build(chart)
        model = Model(chart.defaults, priority.schema, enumerate_paths(priority.schema), priority.diagnostics)
    else:
        model = coalesce(chart)
    unique = {entry.path: entry for entry in model.paths}
    linear = list(dict.fromkeys([*map(tuple, _default_paths(chart.defaults)), *unique]))
    selected = [unique[path] for path in linear if path in unique]
    ordered = order_paths(selected, lambda entry: entry.path, strategy=traversal_strategy, seed=seed)
    planned_paths = [list(entry.path) for entry in ordered]
    planning_seconds = time.monotonic() - planning_started
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "path-inventory.json").write_text(
        json.dumps(
            {
                "seed": seed,
                "traversal_strategy": traversal_strategy,
                "traversal_algorithm": ALGORITHM,
                "paths": planned_paths,
                "diagnostics": model.diagnostics,
            },
            indent=2,
        )
        + "\n"
    )
    LOGGER.info("Discovered %d unique value paths; %s traversal, seed %d", len(ordered), traversal_strategy, seed)
    measured = FieldCoverage(inventory, chart.defaults)
    phases: list[dict[str, object]] = []
    active: ValuePath | None = None
    baseline: dict[str, object] = {"status": "not-started", "attempts": 0}
    stopped = False
    started = time.monotonic()
    try:
        with execution_timer(budget):
            baseline["attempts"] = 1
            resources = render(chart, {}, helm=helm, timeout=min(timeout, budget))
            if not resources:
                raise RenderFailure("chart rendered no resources")
            baseline["status"] = "passed"
            measured.observe(chart.defaults)
            for entry in ordered:
                remaining = budget - (time.monotonic() - started)
                if remaining <= 0:
                    raise TimeLimitReached()
                active = entry
                LOGGER.info("Testing path %s (%d/%d)", format_path(entry.path), len(phases) + 1, len(ordered))
                key = hashlib.sha256(json.dumps(entry.path).encode()).hexdigest()[:20]
                directory = artifacts / "paths" / key
                phase = check_chart(
                    chart,
                    max_examples=max_examples,
                    random_seed=seed,
                    helm=helm,
                    timeout=timeout,
                    time_limit=remaining,
                    input_strategy=path_strategy(chart, entry, model.schema),
                    input_inventory=inventory,
                    artifact_dir=directory,
                    fail_fast=fail_fast,
                    check_defaults=False,
                )
                phase.pop("input_inventory", None)
                phase.update(phase=format_path(entry.path), kind="value-path", path=list(entry.path), artifacts=str(directory))
                if phase.get("failure_type") in GENERATION_ERRORS:
                    phase["status"] = "generation-error"
                observed = phase.get("field_coverage", {})
                if isinstance(observed, dict):
                    measured.present.update(tuple(path) for path in observed.get("present_fields", []))
                    measured.varied.update(tuple(path) for path in observed.get("varied_fields", []))
                phases.append(phase)
                active = None
                directory.mkdir(parents=True, exist_ok=True)
                (directory / "report.json").write_text(json.dumps(phase, indent=2) + "\n")
                if phase["status"] == "time-limit":
                    stopped = True
                    break
                if fail_fast and phase["status"] == "failed":
                    break
    except TimeLimitReached:
        stopped = True
        if active is not None:
            phases.append({"phase": format_path(active.path), "kind": "value-path", "path": list(active.path), "status": "time-limit"})
        elif baseline["status"] != "passed":
            baseline["status"] = "time-limit"
    except Exception as exc:
        if baseline["status"] != "passed":
            baseline.update(status="failed", error=str(exc), failure_type=type(exc).__name__)
        else:
            raise
    measured.refresh()
    failures = [phase for phase in phases if phase["status"] == "failed"]
    completed = sum(phase["status"] in {"passed", "failed"} for phase in phases)
    generation_errors = any(phase["status"] == "generation-error" for phase in phases)
    status = (
        "failed"
        if failures or baseline["status"] == "failed"
        else "time-limit"
        if stopped
        else "generation-error"
        if generation_errors
        else "passed"
    )
    result: dict[str, object] = {
        "status": status,
        "mode": "paths",
        "seed": seed,
        "traversal_strategy": traversal_strategy,
        "traversal_algorithm": ALGORITHM,
        "traversal": {
            "discovered_paths": len(unique),
            "selected_paths": len(ordered),
            "visited_paths": len(phases),
            "completed_paths": completed,
            "incomplete_paths": len(phases) - completed,
            "remaining_paths": len(ordered) - len(phases),
            "visited_order": [phase["path"] for phase in phases],
            "remaining_order": planned_paths[len(phases) :],
            "path_targets_complete": completed == len(ordered) and baseline["status"] == "passed",
        },
        "baseline": baseline,
        "phases": phases,
        "attempts": int(str(baseline["attempts"])) + sum(int(str(phase.get("attempts", 0))) for phase in phases),
        "time_limit_seconds": budget,
        "planning_seconds": planning_seconds,
        "execution_seconds": time.monotonic() - started,
        "coverage_complete": False,
        "proof_of_totality": False,
        "input_inventory": inventory.report(),
        "field_coverage": measured.statistics,
        "filtering": {
            "requested": filtering,
            "applied": filtering,
            "method": "known-path-generation" if filtering else "unrestricted-path-generation",
            "order": "discover, filter, traverse, execute",
            "generated_text_policy": "C0/C1 controls excluded, except LF and CR; supplied defaults are unchanged",
        },
        "scope": "One property per discovered path; multiple values and shrinking within a property; joint input coverage is incomplete",
    }
    if failures:
        result["error"] = "\n\n".join(f"{phase['phase']}: {phase.get('error', '')}" for phase in failures)
    elif baseline.get("error"):
        result["error"] = baseline["error"]
    (artifacts / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    return result

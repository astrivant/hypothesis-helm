"""
Forecast progressive finite coverage and filtering without running Helm or properties.
"""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable
from pathlib import Path

from rich.console import Console

from hypothesis_helm.compiler.ir import specialize
from hypothesis_helm.compiler.pruning import Pruner, safe_values
from hypothesis_helm.schemas.combinations import InteractionPlan
from hypothesis_helm.schemas.contracts import configuration_key, mapping, sequence
from hypothesis_helm.schemas.finite import NonFiniteSchema
from hypothesis_helm.schemas.model import ValuesModel

LOGGER = logging.getLogger(__name__)


def duration_estimate(inputs: int, renders: int, history: dict[str, object]) -> float | None:
    """
    Apply compatible measured renderer and per-candidate costs without inventing timings.

    Args:
        inputs (int): Candidate checks in the prospective run.
        renders (int): Renderer invocations forecast for that run.
        history (dict[str, object]): Compatible historical cost profile, or an empty mapping.

    Returns:
        float | None: Advisory wall time, or unknown without usable measurements.
    """
    costs = history.get("cost_profile")
    if isinstance(costs, dict):
        render = costs.get("seconds_per_render")
        check = costs.get("seconds_per_check")
        if (
            isinstance(render, int | float)
            and not isinstance(render, bool)
            and isinstance(check, int | float)
            and not isinstance(check, bool)
            and render >= 0
            and check >= 0
        ):
            try:
                if not math.isfinite(render) or not math.isfinite(check):
                    return None
                estimate = float(render * renders + check * inputs)
            except OverflowError:
                return None
            return estimate if math.isfinite(estimate) else None
    return None


def estimate_progression(
    chart: Path,
    defaults: dict[str, object],
    model: ValuesModel,
    selected: InteractionPlan,
    build: Callable[[int], InteractionPlan],
    merge: Callable[[dict[str, object]], dict[str, object]],
    *,
    pruning: bool,
    max_cases: int,
    max_candidates: int,
    history: dict[str, object],
    fixed_names: bool = True,
    time_limit: float = 180.0,
) -> dict[str, object]:
    """
    Advance finite strengths, union their inputs, and forecast output classes.

    Forecasts never register representatives or authorize pruning. Additional
    plans respect the caller's limits; unavailable totals remain explicit bounds.

    Args:
        chart (Path): Source chart to inspect without creating artifacts.
        defaults (dict[str, object]): Default values included once in each plan.
        model (ValuesModel): Shared schema-derived hierarchy.
        selected (InteractionPlan): Actual configured plan, including promotion and groups.
        build (Callable[[int], InteractionPlan]): Bounded planning with promotion disabled.
        merge (Callable[[dict[str, object]], dict[str, object]]): Effective-value normalization.
        pruning (bool): Whether the configured run enables exact-equivalence pruning.
        max_cases (int): Configured per-plan case limit.
        max_candidates (int): Configured planning work limit.
        history (dict[str, object]): Compatible measured costs; no successes are restored.
        fixed_names (bool): Whether release and namespace satisfy the fixed-context contract.
        time_limit (float): Execution budget used for advisory strength recommendations.

    Returns:
        dict[str, object]: Exact stage counts, conditional filtering forecasts and bounded totals.
    """
    started = time.perf_counter()
    compiler = Pruner(chart, defaults, model)
    if not fixed_names:
        compiler.disabled = "empty renderer names are outside the fixed-context contract"
    input_cache: dict[tuple[str, str], tuple[str, str]] = {}
    cumulative_inputs: set[str] = set()
    cumulative_outputs: set[tuple[str, str]] = set()
    rows: list[dict[str, object]] = []
    plans: dict[int, InteractionPlan] = {}
    previous_count: int | None = None

    def classify(plan: InteractionPlan) -> dict[str, tuple[str, str]]:
        """
        Normalize duplicate inputs and project only fully supported symbolic outputs.

        Args:
            plan (InteractionPlan): Bounded complete plan for one strength.

        Returns:
            dict[str, tuple[str, str]]: Distinct inputs mapped to conditional render classes.
        """
        inputs: dict[str, tuple[str, str]] = {}
        for overrides in [{}, *plan.values]:
            effective = merge(overrides)
            key = configuration_key(effective)
            if key in inputs:
                continue
            cache_key = (key, configuration_key(overrides))
            if cache_key not in input_cache:
                identity = ("unknown", key)
                if compiler.disabled is None and safe_values(defaults, overrides):
                    symbolic: list[object] = []
                    for name, nodes in compiler.programs.items():
                        output = specialize(nodes, effective, model)
                        if output.reason is not None:
                            break
                        symbolic.append((name, output.atoms, output.partition))
                    else:
                        identity = ("known", configuration_key({"output": symbolic}))
                input_cache[cache_key] = identity
            inputs[key] = input_cache[cache_key]
        return inputs

    def row(plan: InteractionPlan, label: str) -> dict[str, object]:
        """
        Summarize a standalone stage without mutating cumulative progression.

        Args:
            plan (InteractionPlan): Stage plan to classify.
            label (str): Human-readable stage label.

        Returns:
            dict[str, object]: Exact inputs and conditional renderer workload.
        """
        classified = classify(plan)
        inputs, outputs = set(classified), set(classified.values())
        renders = len(outputs) if pruning else len(inputs)
        return {
            "label": label,
            "status": "planned",
            "strength": plan.strength,
            "strategy": plan.strategy,
            "candidate_inputs": len(inputs),
            "filter_forecast_renders": len(outputs),
            "filter_forecast_removed": len(inputs) - len(outputs),
            "opaque_inputs": sum(kind == "unknown" for kind, _ in outputs),
            "configured_renders": renders,
            "estimated_seconds": duration_estimate(len(inputs), renders, history),
        }

    strengths = range(1, max(1, len(selected.factors)) + 1)
    for strength in strengths:
        LOGGER.info("Forecasting permutation strength %d (no rendering)", strength)
        try:
            plan = build(strength)
        except NonFiniteSchema as exc:
            rows.append(
                {
                    "label": str(strength),
                    "strength": strength,
                    "status": "unavailable",
                    "reason": str(exc),
                }
            )
            continue
        plans[strength] = plan
        current = row(plan, str(strength))
        classified = classify(plan)
        inputs, outputs = set(classified), set(classified.values())
        count = len(inputs)
        outputs = {classified[key] for key in inputs - cumulative_inputs}
        current.update(
            {
                "candidate_delta": count - previous_count if previous_count is not None else None,
                "new_inputs": len(inputs - cumulative_inputs),
                "new_filter_forecast_renders": len(outputs - cumulative_outputs),
            }
        )
        cumulative_inputs.update(inputs)
        cumulative_outputs.update(outputs)
        current["cumulative_inputs"] = len(cumulative_inputs)
        current["cumulative_filter_forecast_renders"] = len(cumulative_outputs)
        rows.append(current)
        previous_count = count

    raw_space = math.prod(len(domain) for domain in selected.domains)
    full_plan = selected if selected.strategy == "exhaustive" else plans.get(len(selected.factors))
    full_reason = None
    if full_plan is None and raw_space <= min(max_cases, max_candidates, 10000):
        LOGGER.info("Forecasting the full finite domain (no rendering)")
        try:
            full_plan = build(max(1, len(selected.factors)))
        except NonFiniteSchema as exc:
            full_reason = str(exc)
    full: dict[str, object]
    if full_plan is not None:
        full = row(full_plan, "full")
        full["candidate_assignments"] = raw_space
    else:
        upper = raw_space + 1  # Baseline may lie outside enumerated override assignments.
        extrapolated = (
            (upper * len(cumulative_outputs) + len(cumulative_inputs) - 1) // len(cumulative_inputs)
            if cumulative_inputs
            else None
        )
        full = {
            "label": "full",
            "status": "bounded",
            "candidate_assignments": raw_space,
            "candidate_inputs_lower_bound": len(cumulative_inputs),
            "candidate_inputs_upper_bound": upper,
            # Opaque overrides may normalize to supported variants in a different plan.
            # Only known distinct symbolic classes imply a shared lower bound.
            "filter_forecast_renders_lower_bound": max(
                int(bool(cumulative_inputs)),
                sum(kind == "known" for kind, _ in cumulative_outputs),
            ),
            "filter_forecast_renders_upper_bound": upper,
            "heuristic_filter_forecast_renders": extrapolated,
            "heuristic_estimated_seconds": duration_estimate(
                upper, extrapolated if pruning and extrapolated is not None else upper, history
            ),
            "reason": full_reason
            or "full enumeration exceeds the configured or 10,000-case forecast limit",
            "heuristic_basis": (
                "progressive union filtering ratio applied to the raw input upper bound; "
                "not a confidence interval"
            ),
        }
    configured = row(selected, "configured")
    stable = compiler.disabled is not None or compiler.unchanged()
    if not stable:
        # A dry-run projection cannot survive observed source mutation.
        for item in [*rows, full, configured]:
            for key in list(item):
                if "filter_forecast" in key or key in (
                    "configured_renders",
                    "estimated_seconds",
                    "heuristic_estimated_seconds",
                ):
                    item[key] = None
    eligible = [
        item
        for item in [*rows, full]
        if item["status"] == "planned"
        and isinstance(item.get("estimated_seconds"), int | float)
        and float(str(item["estimated_seconds"])) <= time_limit
    ]
    recommendation = (
        max(eligible, key=lambda item: int(str(item["strength"]))) if eligible else None
    )
    timed = any(isinstance(item.get("estimated_seconds"), int | float) for item in rows)
    return {
        "execution_budget": {
            "time_limit_seconds": time_limit,
            "recommended_strength": recommendation["strength"] if recommendation else None,
            "recommended_inputs": recommendation["candidate_inputs"] if recommendation else None,
            "estimated_seconds": recommendation["estimated_seconds"] if recommendation else None,
            "status": "estimated-fit"
            if recommendation
            else "no-estimated-fit"
            if timed
            else "unknown",
            "advisory": True,
        },
        "mode": "static-progressive-forecast",
        "stages": rows,
        "configured_run": configured,
        "full_run": full,
        "pruning_enabled": pruning,
        "filtering_condition": (
            "all representatives and candidate assertions succeed; fixed chart and renderer"
        ),
        "compiler_fallback": compiler.disabled,
        "source_stable": stable,
        "forecast_seconds": time.perf_counter() - started,
        "timing_source": "compatible_history"
        if duration_estimate(1, 1, history) is not None
        else "unknown",
        "actual_renders": 0,
        "pruning_certificates": [],
        "notes": [
            "Strength previews disable exhaustive promotion but retain exhaustive groups.",
            "The configured run retains its actual promotion and pruning settings.",
            "Stages need not be nested: incremental counts use set unions, not summed stage sizes.",
            "Static filtering forecasts do not certify successful renders or authorize pruning.",
            "Opaque inputs require rendering; higher strengths can change filtering rates.",
            "Timing excludes failure shrinking and uses historical costs only when compatible.",
        ],
    }


def plot_progression(report: dict[str, object]) -> None:
    """
    Display an ASCII workload plot on stderr while preserving JSON stdout.

    Args:
        report (dict[str, object]): Finite progressive report or a per-path dry-run estimate.

    Returns:
        None: A readable plot with counts, filtering conditions and timing is printed.
    """
    console = Console(stderr=True, markup=False, highlight=False)
    progression = report.get("progressive_estimate")
    if not isinstance(progression, dict):
        selected = int(str(report.get("selected_properties", 0)))
        scheduled = int(str(report.get("scheduled_properties", 0)))
        console.print(
            "Dry-run property workload (permutation progression is unavailable for this mode)"
        )
        for label, count in (
            ("selected", selected),
            ("scheduled", scheduled),
            ("reused", selected - scheduled),
        ):
            console.print(f"  {label:9} {'#' * round(24 * count / max(selected, 1)):24} {count}")
        console.print("Time: unknown" if scheduled else "Time: 0s (nothing scheduled)")
        return
    rows = [mapping(item) for item in sequence(progression["stages"])]
    full = mapping(progression["full_run"])
    if full["status"] == "planned":
        rows.append(full)
    maximum = max(
        [int(str(item["candidate_inputs"])) for item in rows if item["status"] == "planned"] or [1]
    )
    console.print("Progressive dry-run forecast (no Helm invocations)")
    console.print("  . candidate inputs    # render forecast after equivalence filtering")
    for item in rows:
        label = str(item["label"])
        if item["status"] != "planned":
            console.print(f"  {label:>4} unavailable: {item['reason']}")
            continue
        count = int(str(item["candidate_inputs"]))
        filtered = item["filter_forecast_renders"]
        console.print(
            f"  {label:>4} {'.' * max(1, round(24 * count / max(maximum, 1))):24} {count} inputs"
        )
        if isinstance(filtered, int):
            console.print(
                f"       {'#' * max(1, round(24 * filtered / max(maximum, 1))):24} "
                f"{filtered} renders (forecast)"
            )
        if "new_inputs" in item:
            console.print(
                f"       {item['new_inputs']} additional inputs; "
                f"{item['cumulative_inputs']} cumulative"
            )
    configured = mapping(progression["configured_run"])
    seconds = configured["estimated_seconds"]
    console.print(
        f"Configured run: {configured['candidate_inputs']} inputs, "
        f"{configured['configured_renders']} renders (forecast); time: "
        + (
            f"{seconds:.2f}s"
            if isinstance(seconds, int | float)
            else "unknown (no compatible measurements)"
        )
    )
    if not progression["pruning_enabled"]:
        console.print("Filtering is potential savings; enable --prune-equivalent to apply it.")
    if full["status"] == "bounded":
        console.print(
            f"Full run: {full['candidate_inputs_lower_bound']}.."
            f"{full['candidate_inputs_upper_bound']} inputs; filtering extrapolation: "
            f"{full['heuristic_filter_forecast_renders']} renders (heuristic)."
        )
    budget = mapping(progression["execution_budget"])
    recommended = budget["recommended_strength"]
    console.print(
        f"Execution limit: {budget['time_limit_seconds']}s; highest estimated fitting strength: "
        f"{recommended if recommended is not None else budget['status']}"
    )
    console.print("Timing is advisory; actual execution stops at its budget.")
    console.print("Conditional on successful representatives; forecasts never authorize pruning.")

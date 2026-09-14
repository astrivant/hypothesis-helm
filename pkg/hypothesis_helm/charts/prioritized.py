"""
Run known chart inputs before broad robustness sampling within one chart budget.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from hypothesis_helm.charts.model import Chart
from hypothesis_helm.charts.runner import check_chart
from hypothesis_helm.compiler.passes.inputs import FieldCoverage, InputInventory
from hypothesis_helm.reporting.budget import TimeLimitReached, execution_timer
from hypothesis_helm.rules import ignored_codes
from hypothesis_helm.schemas.priority import PriorityInputs

LOGGER = logging.getLogger(__name__)


def check_prioritized(
    chart: Chart,
    *,
    budget: float,
    max_examples: int,
    seed: int,
    helm: str,
    timeout: float,
    artifacts: Path,
    fail_fast: bool = False,
) -> dict[str, object]:
    """
    Preserve deferred inputs as a separate final phase with explicit incomplete coverage.

    Args:
        chart (Chart): Original chart contract and defaults.
        budget (float): Remaining chart test budget in seconds.
        max_examples (int): Generated example target for each phase.
        seed (int): Reproducible Hypothesis seed.
        helm (str): Helm executable.
        timeout (float): Per-render subprocess bound.
        artifacts (Path): Persistent phase diagnostics and reproducer destination.
        fail_fast (bool): Stop after a failing phase, without shrinking its counterexample.

    Returns:
        dict[str, object]: Both phases, preserved findings, and aggregate attempt counts.
    """
    started = time.monotonic()
    phases: list[dict[str, object]] = []
    priority: PriorityInputs | None = None
    inventory: InputInventory | None = None
    try:
        with execution_timer(budget * 0.9):
            inventory = InputInventory.build(chart)
            priority = PriorityInputs.build(chart)
            remaining = budget * 0.9 - (time.monotonic() - started)
            if remaining <= 0:
                raise TimeLimitReached()
            LOGGER.info("Testing known inputs first; arbitrary extra-key cases are deferred")
            primary = check_chart(
                chart,
                max_examples=max_examples,
                random_seed=seed,
                helm=helm,
                timeout=timeout,
                time_limit=remaining,
                input_strategy=priority.strategy(chart),
                input_inventory=inventory,
                artifact_dir=artifacts / "known-inputs",
                fail_fast=fail_fast,
            )
            phases.append({**primary, "phase": "known-inputs"})
    except TimeLimitReached:
        phases.append(
            {
                "phase": "known-inputs",
                "status": "time-limit",
                "attempts": 0,
                "error": "Known-input preparation or testing exhausted its phase budget",
            }
        )
    except Exception as exc:
        phases.append(
            {
                "phase": "known-inputs",
                "status": "generation-error",
                "attempts": 0,
                "error": str(exc),
                "failure_type": type(exc).__name__,
            }
        )
    remaining = budget - (time.monotonic() - started)
    if fail_fast and any(
        phase["status"] == "failed"
        and phase.get("failure_type") not in {"Unsatisfiable", "FailedHealthCheck", "SchemaError", "InvalidArgument"}
        for phase in phases
    ):
        phases.append(
            {
                "phase": "robustness",
                "status": "not-started",
                "attempts": 0,
                "reason": "--fail stopped testing after a known-input failure",
            }
        )
    elif priority is not None and priority.schema == chart.schema:
        phases.append(
            {
                "phase": "robustness",
                "status": "not-needed",
                "attempts": 0,
                "reason": "Known-input generation already uses the original schema",
            }
        )
    elif remaining > 0:
        LOGGER.info("Testing deferred arbitrary-key and original-schema robustness cases")
        try:
            with execution_timer(remaining):
                secondary = check_chart(
                    chart,
                    max_examples=max_examples,
                    random_seed=seed,
                    helm=helm,
                    timeout=timeout,
                    time_limit=remaining,
                    artifact_dir=artifacts / "robustness",
                    fail_fast=fail_fast,
                    input_strategy=priority.deferred_strategy(chart) if priority is not None else None,
                    input_inventory=inventory,
                )
                phases.append({**secondary, "phase": "robustness"})
        except TimeLimitReached:
            phases.append(
                {
                    "phase": "robustness",
                    "status": "time-limit",
                    "attempts": 0,
                    "error": "Chart budget exhausted while preparing robustness cases",
                }
            )
        except Exception as exc:
            phases.append(
                {
                    "phase": "robustness",
                    "status": "generation-error",
                    "attempts": 0,
                    "error": str(exc),
                    "failure_type": type(exc).__name__,
                }
            )
    else:
        phases.append(
            {
                "phase": "robustness",
                "status": "not-started",
                "attempts": 0,
                "error": "No chart budget remained for deferred cases",
            }
        )
    for phase in phases:
        if phase.get("failure_type") in {
            "Unsatisfiable",
            "FailedHealthCheck",
            "SchemaError",
            "InvalidArgument",
        }:
            phase["status"] = "generation-error"
        directory = artifacts / str(phase["phase"])
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "report.json").write_text(json.dumps(phase, indent=2) + "\n")
    failures = [phase for phase in phases if phase["status"] == "failed"]
    incomplete = any(phase["status"] not in {"passed", "failed", "not-needed"} for phase in phases)
    status = (
        "failed"
        if failures
        else "generation-error"
        if any(phase["status"] == "generation-error" for phase in phases)
        else "time-limit"
        if incomplete
        else "ignored"
        if phases and all(phase["status"] in {"ignored", "not-needed"} for phase in phases)
        else "passed"
    )
    result: dict[str, object] = {
        "status": status,
        "ignored_rules": ignored_codes(),
        "attempts": sum(int(str(phase.get("attempts", 0))) for phase in phases),
        "phases": phases,
        "time_limit_seconds": budget,
        "execution_seconds": time.monotonic() - started,
        "coverage_complete": False,
        "proof_of_totality": False,
        "phase_targets_complete": not incomplete,
        "filtering": {
            "requested": True,
            "applied": True,
            "method": "known-inputs-first",
            "topology_applied": False,
            "reason": "Known paths first; extra-key cases run last; control-character fuzzing excluded",
            "known_input_budget_fraction": 0.9,
            "generated_text_policy": "C0/C1 controls excluded from both sampling phases, except LF and CR",
            "deferred_objects": priority.deferred_objects if priority else [],
            "dynamic_objects": priority.dynamic_objects if priority else [],
            "diagnostics": priority.diagnostics if priority else [],
        },
    }
    if failures:
        result["error"] = "\n\n".join(f"{phase['phase']}: {phase.get('error', '')}" for phase in failures)
    if inventory is not None:
        combined = FieldCoverage(inventory, chart.defaults)
        for phase in phases:
            measured = phase.get("field_coverage", {})
            if isinstance(measured, dict):
                combined.present.update(tuple(path) for path in measured.get("present_fields", []))
                combined.varied.update(tuple(path) for path in measured.get("varied_fields", []))
        combined.refresh()
        result.update(input_inventory=inventory.report(), field_coverage=combined.statistics)
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    return result

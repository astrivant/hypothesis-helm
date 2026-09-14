"""
Discover unique value paths, then visit filtered path properties within one budget.
"""

import hashlib
import json
import logging
import math
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path

from hypothesis import strategies as st
from jsonschema import validators

from hypothesis_helm.charts.generate import Model, coalesce
from hypothesis_helm.charts.generated import path_values
from hypothesis_helm.charts.model import Chart, _default_paths, merge_values
from hypothesis_helm.charts.rendering import RenderFailure, render
from hypothesis_helm.charts.runner import check_chart
from hypothesis_helm.compiler.asts.contracts import Contracts
from hypothesis_helm.compiler.passes.dependencies import Dependencies
from hypothesis_helm.compiler.passes.inputs import FieldCoverage, InputInventory
from hypothesis_helm.compiler.passes.rejections import RejectionPolicy
from hypothesis_helm.compiler.passes.sampling import profile as sampling_profile
from hypothesis_helm.execution.sampling import DEFAULT_SAMPLING, Sampling
from hypothesis_helm.execution.traversal import ALGORITHM, order_paths, validate_strategy
from hypothesis_helm.reporting.budget import TimeLimitReached, execution_timer
from hypothesis_helm.reporting.progress import format_path
from hypothesis_helm.rules import check, ignored, ignored_codes
from hypothesis_helm.schemas.contracts import json_value, schema_strategy
from hypothesis_helm.schemas.paths import ValuePath, enumerate_paths
from hypothesis_helm.schemas.priority import PriorityInputs

LOGGER = logging.getLogger(__name__)
GENERATION_ERRORS = {"Unsatisfiable", "FailedHealthCheck", "SchemaError", "InvalidArgument"}


def path_strategy(
    chart: Chart, entry: ValuePath, generation_schema: dict[str, object], dependencies: Dependencies | None = None
) -> st.SearchStrategy[dict[str, object]]:
    """
    Generate one target path in baseline or schema-valid dependent context.

    Args:
        chart (Chart): Original chart whose schema validates complete candidates.
        entry (ValuePath): One discovered and filtered path strategy.
        generation_schema (dict[str, object]): Generation-only parent type information.
        dependencies (Dependencies | None): Shared activation model for enabled child contexts.

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
        values = path_values(chart, entry.path, value, draw(st.data()), generation_schema=generation_schema)
        if dependencies is not None and dependencies.nodes:
            validator = validators.validator_for(chart.schema)(chart.schema)
            contexts = dependencies.contexts(
                chart.defaults,
                values,
                entry.path,
                lambda candidate: validator.is_valid(json_value(merge_values(chart.defaults, candidate))),
            )
            values = draw(st.sampled_from(contexts))
        return values

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
    sampling: Sampling = DEFAULT_SAMPLING,
    fail_fast: bool = False,
    release: str = "hypothesis",
    namespace: str = "default",
    kube_version: str | None = None,
    allow_empty: bool = False,
    jobs: int = 1,
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
        traversal_strategy (str): Random, linear, root-first, or leaf-first path traversal.
        sampling (Sampling): Optional retained percentage and minimum sample after filtering.
        fail_fast (bool): Stop after the first observed failure without shrinking.
        release (str): Helm release name for every input.
        namespace (str): Helm release namespace.
        kube_version (str | None): Kubernetes capability version supplied to Helm.
        allow_empty (bool): Accept inputs that render no resources.
        jobs (int): Concurrent path workers sharing this chart's execution deadline.

    Returns:
        dict[str, object]: Visited, completed, incomplete, and remaining path evidence.
    """
    traversal_strategy = validate_strategy(traversal_strategy)
    if not math.isfinite(budget) or budget <= 0 or max_examples < 1 or timeout <= 0 or jobs < 1:
        raise ValueError("budget, max_examples, and timeout must be positive")
    planning_started = time.monotonic()
    sampling_analysis = sampling_profile(chart) if sampling.aggressive else None
    inventory = InputInventory.build(chart)
    rejections = (
        RejectionPolicy(Contracts.build(chart.path), chart.defaults, (chart.path / "values.schema.json").is_file()) if filtering else None
    )
    if filtering:
        priority = PriorityInputs.build(chart)
        model = Model(chart.defaults, priority.schema, enumerate_paths(priority.schema), priority.diagnostics)
    else:
        model = coalesce(chart)
    unique = {entry.path: entry for entry in model.paths}
    linear = list(dict.fromkeys([*map(tuple, _default_paths(chart.defaults)), *unique]))
    selected: Sequence[ValuePath] = [unique[path] for path in linear if path in unique]
    eligible_paths = [list(entry.path) for entry in selected]
    selected, sampling_report = (Sampling() if sampling.aggressive else sampling).select(
        selected, lambda entry: json.dumps(list(entry.path)), seed
    )
    sampling_report["unit"] = "path property"
    if sampling_analysis is not None:
        sampling_report["aggressive"] = {
            "requested_percent": 70,
            "analysis": sampling_analysis,
            "fallback": "path-property sampling has no measured calibration; additional sampling disabled",
        }
    ordered = order_paths(selected, lambda entry: entry.path, strategy=traversal_strategy, seed=seed)
    planned_paths = [list(entry.path) for entry in ordered]
    planning_seconds = time.monotonic() - planning_started
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "path-inventory.json").write_text(
        json.dumps(
            {
                "sampling": sampling_report,
                "seed": seed,
                "traversal_strategy": traversal_strategy,
                "traversal_algorithm": ALGORITHM,
                "eligible_paths": eligible_paths,
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
            resources = render(
                chart, {}, helm=helm, timeout=min(timeout, budget), release=release, namespace=namespace, kube_version=kube_version
            )
            if not resources and not allow_empty:
                check(False, "HH1009", "chart rendered no resources")
            baseline["status"] = "passed"
            measured.observe(chart.defaults)
            if jobs > 1:
                from hypothesis_helm.execution.path_queue import execute

                context: dict[str, object] = {
                    "chart": str(chart.path),
                    "schema": chart.schema,
                    "defaults": json_value(chart.defaults),
                    "generation_schema": model.schema,
                    "paths": [{"path": list(entry.path), "schema": entry.schema} for entry in ordered],
                    "deadline": started + budget,
                    "resources": resources,
                    "artifacts": str(artifacts),
                    "max_examples": max_examples,
                    "seed": seed,
                    "helm": helm,
                    "timeout": timeout,
                    "filtering": filtering,
                    "fail_fast": fail_fast,
                    "release": release,
                    "namespace": namespace,
                    "kube_version": kube_version,
                    "allow_empty": allow_empty,
                }
                # Retain queue ownership records alongside diagnostics; never reuse a previous queue.
                queue_root = Path(tempfile.mkdtemp(prefix="path-workers-", dir=artifacts))
                phases.extend(execute(context, queue_root / "queue", jobs))
                stopped = time.monotonic() - started >= budget or any(phase["status"] == "time-limit" for phase in phases)
            for entry in ordered if jobs == 1 else []:
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
                    input_strategy=path_strategy(chart, entry, model.schema, inventory.dependencies),
                    input_inventory=inventory,
                    artifact_dir=directory,
                    fail_fast=fail_fast,
                    check_defaults=False,
                    release=release,
                    namespace=namespace,
                    kube_version=kube_version,
                    allow_empty=allow_empty,
                    rejection_policy=rejections,
                    protected_paths=(entry.path,),
                    baseline_resources=resources,
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
            baseline.update(
                status="ignored" if isinstance(exc, RenderFailure) and ignored(exc.code) else "failed",
                error=str(exc),
                failure_type=type(exc).__name__,
                code=getattr(exc, "code", None),
            )
        else:
            raise
    for phase in phases:
        observed = phase.get("field_coverage", {})
        if isinstance(observed, dict):
            measured.present.update(tuple(path) for path in observed.get("present_fields", []))
            measured.varied.update(tuple(path) for path in observed.get("varied_fields", []))
    measured.refresh()
    failures = [phase for phase in phases if phase["status"] == "failed"]
    completed = sum(phase["status"] in {"passed", "failed", "configuration-rejected"} for phase in phases)
    worker_errors = any(phase["status"] == "error" for phase in phases)
    generation_errors = any(phase["status"] == "generation-error" for phase in phases)
    status = (
        "failed"
        if failures or baseline["status"] == "failed"
        else "time-limit"
        if stopped
        else "error"
        if worker_errors
        else "generation-error"
        if generation_errors
        else "ignored"
        if baseline["status"] == "ignored" or (phases and all(phase["status"] == "ignored" for phase in phases))
        else "configuration-rejected"
        if phases and all(phase["status"] == "configuration-rejected" for phase in phases)
        else "passed"
    )
    result: dict[str, object] = {
        "status": status,
        "mode": "paths",
        "ignored_rules": ignored_codes(),
        "workers": min(jobs, len(ordered)),
        "worker_model": "shared chart path queue",
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
            "sampled_out_paths": sampling_report["omitted"],
            "path_targets_complete": completed == len(unique) and baseline["status"] == "passed",
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
        "dependency_activation": inventory.dependencies.report(chart.defaults),
        "field_coverage": measured.statistics,
        "sampling": sampling_report,
        "filtering": {
            "requested": filtering,
            "applied": filtering,
            "method": "known-path-generation" if filtering else "unrestricted-path-generation",
            "order": "discover, filter, sample, traverse, execute",
            "generated_text_policy": "C0/C1 controls excluded, except LF and CR; supplied defaults are unchanged",
        },
        "scope": "One property per discovered path; multiple values and shrinking within a property; joint input coverage is incomplete",
    }
    if failures:
        result["error"] = "\n\n".join(f"{phase['phase']}: {phase.get('error', '')}" for phase in failures)
    elif baseline.get("error"):
        result["error"] = baseline["error"]
    if rejections is not None:
        rejection_summary = rejections.snapshot()
        if jobs > 1:
            worker_rejections = {
                str(phase["worker_pid"]): phase["configuration_rejections"]
                for phase in phases
                if "worker_pid" in phase and "configuration_rejections" in phase
            }
            rejection_summary["worker_reports"] = worker_rejections
            for key in (
                "rejected_candidates",
                "filtered_candidates",
                "adjusted_candidates",
                "verification_renders",
                "classifier_disagreements",
            ):
                rejection_summary[key] = sum(
                    int(str(snapshot.get(key, 0))) for snapshot in worker_rejections.values() if isinstance(snapshot, dict)
                )
        result["configuration_rejections"] = rejection_summary
    (artifacts / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    return result

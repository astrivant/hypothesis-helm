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

from hypothesis_helm.charts.model import Chart, _default_paths, merge_values
from hypothesis_helm.charts.suites.generate import Model, coalesce
from hypothesis_helm.charts.suites.runtime import path_values
from hypothesis_helm.charts.testing.rendering import render
from hypothesis_helm.charts.testing.runner import check_chart
from hypothesis_helm.compiler.asts.contracts import Contracts
from hypothesis_helm.compiler.passes.dependencies import Dependencies
from hypothesis_helm.compiler.passes.inputs import FieldCoverage, InputInventory
from hypothesis_helm.compiler.passes.rejections import RejectionPolicy
from hypothesis_helm.compiler.passes.sampling import profile as sampling_profile
from hypothesis_helm.exceptions.execution import ChartUnavailable, TimeLimitReached
from hypothesis_helm.exceptions.rendering import RandomInputUnavailable, RenderFailure
from hypothesis_helm.execution.planning.partition import Partition, digest
from hypothesis_helm.execution.planning.sampling import DEFAULT_SAMPLING, Sampling
from hypothesis_helm.execution.planning.traversal import ALGORITHM, SELECTION_ORDER, order_paths, validate_strategy
from hypothesis_helm.execution.runtime.budget import execution_timer
from hypothesis_helm.findings.policy import RuleScope, chart_rules
from hypothesis_helm.findings.severity import policy as finding_policy
from hypothesis_helm.integrations.sharding import Shard
from hypothesis_helm.reporting.console.logs import input_baseline
from hypothesis_helm.reporting.console.progress import format_path
from hypothesis_helm.rules import check, ignored, ignored_codes
from hypothesis_helm.schemas.configuration.characters import generated_text_policy
from hypothesis_helm.schemas.contracts import json_value
from hypothesis_helm.schemas.generation.priority import PriorityInputs
from hypothesis_helm.schemas.generation.strategies import schema_strategy
from hypothesis_helm.schemas.paths import ValuePath, enumerate_paths

__all__ = ("GENERATION_ERRORS", "check_paths", "path_strategy")


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
        value = draw(schema_strategy(entry.schema, generation=chart.input_domains().generation, path=entry.path))
        values = path_values(chart, entry.path, value, draw(st.data()), generation_schema=generation_schema)
        if dependencies is not None and dependencies.nodes:
            validator = validators.validator_for(chart.generation_schema())(chart.generation_schema())
            contexts = dependencies.contexts(
                chart.defaults,
                values,
                entry.path,
                lambda candidate: validator.is_valid(json_value(merge_values(dependencies.context(chart.defaults, candidate), candidate))),
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
    shard: Shard | None = None,
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
        shard (Shard | None): Partition the same retained path inventory across CI jobs.

    Returns:
        dict[str, object]: Visited, completed, incomplete, and remaining path evidence.
    """
    traversal_strategy = validate_strategy(traversal_strategy)
    from hypothesis_helm.compiler.randomness.policy import prepare as prepare_random_renderer
    from hypothesis_helm.compiler.randomness.rendering import enabled as random_enabled

    if random_enabled(chart):
        prepare_random_renderer(chart, helm)
    if not math.isfinite(budget) or budget <= 0 or max_examples < 1 or timeout <= 0 or jobs < 1:
        raise ValueError("budget, max_examples, and timeout must be positive")
    from hypothesis_helm.schemas.opaque import warn_opaque

    warn_opaque(chart.schema, str(chart.path))
    planning_started = time.monotonic()
    sampling_analysis = sampling_profile(chart) if sampling.aggressive else None
    inventory = InputInventory.build(chart)
    input_baseline(chart.path, len(inventory.known))
    rejections = (
        RejectionPolicy(Contracts.build(chart.path, inventory.dependencies), chart.defaults, (chart.path / "values.schema.json").is_file())
        if filtering
        else None
    )
    if filtering:
        priority = PriorityInputs.build(chart)
        model = Model(chart.defaults, priority.schema, enumerate_paths(priority.schema), priority.diagnostics)
    else:
        model = coalesce(chart)
    model.schema = chart.generation_schema(model.schema)
    model.paths = enumerate_paths(model.schema)
    unique = {entry.path: entry for entry in model.paths}
    if random_enabled(chart):
        # A root property samples renderer inputs even when the chart has no configurable values.
        unique[()] = ValuePath((), {"const": json_value(chart.defaults)}, "renderer-randomness")
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
    partition = Partition.paths(shard, [entry.path for entry in selected]) if shard is not None else None
    if partition is not None:
        selected = [entry for entry in selected if partition.owns(digest(list(entry.path)))]
    ordered = order_paths(selected, lambda entry: entry.path, strategy=traversal_strategy, seed=seed)
    planned_paths = [list(entry.path) for entry in ordered]
    planning_seconds = time.monotonic() - planning_started
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "path-inventory.json").write_text(
        json.dumps(
            {
                **({"work_partition": partition.report()} if partition is not None else {}),
                "sampling": sampling_report,
                "seed": seed,
                "renderer_observations": chart.renderer_statistics,
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
    LOGGER.info(
        "Discovered %d unique value paths; %d selected for this instance; %s traversal, seed %d",
        len(unique),
        len(ordered),
        traversal_strategy,
        seed,
    )
    if partition is not None and not ordered:
        empty = {"status": "empty-shard", "attempts": 0, "mode": "paths", "work_partition": partition.report()}
        (artifacts / "report.json").write_text(json.dumps(empty, indent=2) + "\n")
        return empty
    measured = FieldCoverage(inventory, chart.defaults)
    phases: list[dict[str, object]] = []
    active: ValuePath | None = None
    baseline: dict[str, object] = {"status": "not-started", "attempts": 0}
    stopped = False
    interrupted = False
    started = time.monotonic()
    try:
        with execution_timer(budget):
            baseline["attempts"] = 1
            try:
                with RuleScope.for_values(chart, {}):
                    resources = render(
                        chart, {}, helm=helm, timeout=min(timeout, budget), release=release, namespace=namespace, kube_version=kube_version
                    )
                    if not resources and not allow_empty:
                        check(False, "HH1107", "chart rendered no resources")
                baseline["status"] = "passed"
            except RenderFailure as exc:
                if exc.random_inputs is not None:
                    baseline.update(values={}, random_inputs=exc.random_inputs)
                    (artifacts / "random-inputs.json").write_text(json.dumps(exc.random_inputs, indent=2) + "\n")
                if exc.controls["blocking"] or ignored(exc.code, chart=chart.path):
                    raise
                resources = []
                baseline.update(status="findings", code=exc.code, error=str(exc), **exc.controls)
                from hypothesis_helm.reporting.console.logs import FindingLog, chart_name

                FindingLog(chart_name(chart.path), chart.defaults, artifacts=artifacts).emit(
                    "Baseline finding", exc.code, str(exc), {}, severity=str(exc.controls["severity"])
                )
            measured.observe(chart.defaults)
            if jobs > 1:
                from hypothesis_helm.execution.workers.path_queue import execute

                context: dict[str, object] = {
                    "chart": str(chart.path),
                    "schema": chart.schema,
                    "defaults": json_value(chart.defaults),
                    "generation_schema": model.schema,
                    "input_domains": chart.input_domains().report(),
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
                interrupted = (queue_root / "queue" / "interrupted").exists()
                stopped = time.monotonic() - started >= budget or any(
                    phase["status"] == "time-limit" or phase.get("stop_reason") == "time-limit" for phase in phases
                )
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
                if phase["status"] == "interrupted":
                    interrupted = True
                    break
                if phase["status"] == "time-limit" or phase.get("stop_reason") == "time-limit":
                    stopped = True
                    break
                if phase.get("fail_fast", fail_fast) and phase["status"] == "failed":
                    break
                if phase.get("error_kind") == "execution":
                    break
    except KeyboardInterrupt:
        interrupted = True
        if active is not None:
            phases.append({"phase": format_path(active.path), "kind": "value-path", "path": list(active.path), "status": "interrupted"})
        elif baseline["status"] != "passed":
            baseline["status"] = "interrupted"
    except TimeLimitReached:
        stopped = True
        if active is not None:
            phases.append({"phase": format_path(active.path), "kind": "value-path", "path": list(active.path), "status": "time-limit"})
        elif baseline["status"] != "passed":
            baseline["status"] = "time-limit"
    except RandomInputUnavailable as exc:
        baseline.update(status="unavailable", reason=str(exc))
    except ChartUnavailable as exc:
        diagnostic = {"status": "error", "error_kind": "execution", "error": str(exc), "failure_type": type(exc).__name__}
        if active is not None:
            phases.append({"phase": format_path(active.path), "kind": "value-path", "path": list(active.path), **diagnostic})
        else:
            baseline.update(diagnostic)
    except Exception as exc:
        if baseline["status"] != "passed":
            baseline.update(
                status="ignored" if isinstance(exc, RenderFailure) and ignored(exc.code, chart=chart.path) else "failed",
                error=str(exc),
                failure_type=type(exc).__name__,
                code=getattr(exc, "code", None),
                **getattr(exc, "controls", {}),
            )
            if baseline["status"] == "failed":
                from hypothesis_helm.reporting.console.logs import FindingLog, chart_name

                FindingLog(chart_name(chart.path), chart.defaults, artifacts=artifacts).emit(
                    "Baseline check failed",
                    str(baseline["code"] or baseline["failure_type"]),
                    str(exc),
                    {},
                    severity=str(baseline["severity"]) if "severity" in baseline else None,
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
    completed = sum(
        phase["status"] in {"passed", "failed", "findings", "configuration-rejected"} and not phase.get("stop_reason") for phase in phases
    )
    worker_errors = baseline["status"] == "error" or any(phase["status"] == "error" for phase in phases)
    generation_errors = any(phase["status"] == "generation-error" for phase in phases)
    status = (
        "interrupted"
        if interrupted or any(phase["status"] == "interrupted" for phase in phases)
        else "error"
        if worker_errors
        else "failed"
        if failures or baseline["status"] == "failed"
        else "time-limit"
        if stopped
        else "generation-error"
        if generation_errors
        else "unavailable"
        if baseline["status"] == "unavailable" or any(phase["status"] == "unavailable" for phase in phases)
        else "ignored"
        if baseline["status"] == "ignored" or (phases and all(phase["status"] == "ignored" for phase in phases))
        else "configuration-rejected"
        if phases and all(phase["status"] == "configuration-rejected" for phase in phases)
        else "findings"
        if baseline["status"] == "findings" or any(phase["status"] == "findings" for phase in phases)
        else "passed"
    )
    result: dict[str, object] = {
        "status": status,
        **(
            {
                "fail_fast": any(bool(phase.get("fail_fast", fail_fast)) for phase in failures)
                or (baseline["status"] == "failed" and bool(baseline.get("fail_fast", fail_fast)))
            }
            if failures or baseline["status"] == "failed"
            else {}
        ),
        "mode": "paths",
        "ignored_rules": ignored_codes(),
        "finding_policy": finding_policy(),
        "finding_controls": chart_rules(chart.path),
        "input_domains": chart.input_domains().report(),
        "compiler_limits": dict(inventory.dependencies.limits),
        "workers": min(jobs, len(ordered)),
        "worker_model": "shared chart path queue",
        "seed": seed,
        "renderer_observations": chart.renderer_statistics,
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
            "order": SELECTION_ORDER,
            "generated_text_policy": generated_text_policy(),
        },
        "scope": "One property per discovered path; multiple values and shrinking within a property; joint input coverage is incomplete",
    }
    if partition is not None:
        partition.visited = [digest(phase["path"]) for phase in phases]
        partition.completed = [
            digest(phase["path"])
            for phase in phases
            if phase["status"] in {"passed", "failed", "findings", "configuration-rejected", "ignored"} and not phase.get("stop_reason")
        ]
        result["work_partition"] = partition.report()
        if not partition.report()["complete"] and result["status"] in {"passed", "findings", "ignored"}:
            result["status"] = "incomplete"
    execution_errors = [phase for phase in [baseline, *phases] if phase.get("error_kind") == "execution"]
    if execution_errors:
        result.update(error_kind="execution", error=execution_errors[0]["error"], coverage_complete=False)
    elif failures:
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
            rejection_summary["worker_reports_scope"] = "Last property snapshot per worker; aggregate counters sum every property delta"
            for key in (
                "rejected_candidates",
                "filtered_candidates",
                "adjusted_candidates",
                "verification_renders",
                "classifier_disagreements",
                "schema_conflicts",
                "incomplete_evaluations",
            ):
                rejection_summary[key] = sum(
                    int(str(snapshot.get(key, 0)))
                    for phase in phases
                    if isinstance(snapshot := phase.get("configuration_rejections"), dict)
                )
            rejection_summary["verify_every_candidate"] = any(
                snapshot.get("verify_every_candidate") for snapshot in worker_rejections.values() if isinstance(snapshot, dict)
            )
            for key in ("analysis_fallbacks", "unsupported_sources"):
                records: list[object] = []
                for snapshot in worker_rejections.values():
                    if isinstance(snapshot, dict):
                        for record in snapshot.get(key, []):
                            if record not in records:
                                records.append(record)
                rejection_summary[key] = records
        result["configuration_rejections"] = rejection_summary
    (artifacts / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    return result

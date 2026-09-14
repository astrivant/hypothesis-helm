"""
Schema generation, bounded rendering, and extensible manifest properties.
"""

from __future__ import annotations

import copy
import json
import logging
import math
import os
import time
from collections.abc import Callable, Sequence
from concurrent.futures import Future
from pathlib import Path

from hypothesis import HealthCheck, Phase, assume, given, seed, settings
from hypothesis.errors import Unsatisfiable
from hypothesis.strategies import SearchStrategy

from hypothesis_helm.charts import yamlio
from hypothesis_helm.charts.audit import audit as audit
from hypothesis_helm.charts.candidates import CandidateChecks
from hypothesis_helm.charts.exhaustive import ExhaustiveRenders
from hypothesis_helm.charts.model import Chart as Chart
from hypothesis_helm.charts.model import _default_paths as _default_paths
from hypothesis_helm.charts.model import _schema_nodes as _schema_nodes
from hypothesis_helm.charts.model import merge_values as merge_values
from hypothesis_helm.charts.planning import PlanningOptions, build_plan
from hypothesis_helm.charts.rendering import RenderFailure as RenderFailure
from hypothesis_helm.charts.rendering import render as render
from hypothesis_helm.charts.rendering import validate_resources as validate_resources
from hypothesis_helm.compiler.asts.contracts import Contracts
from hypothesis_helm.compiler.passes.inputs import FieldCoverage, InputInventory
from hypothesis_helm.compiler.passes.pruning import Pruner
from hypothesis_helm.compiler.passes.rejections import RejectionPolicy
from hypothesis_helm.execution.render_hashes import RenderHashes
from hypothesis_helm.execution.sampling import DEFAULT_SAMPLING, Sampling
from hypothesis_helm.execution.traversal import order_configurations, validate_strategy
from hypothesis_helm.reporting.budget import TimeLimitReached
from hypothesis_helm.reporting.changes import compare
from hypothesis_helm.reporting.reproductions import changed_values
from hypothesis_helm.rules import ignored_codes
from hypothesis_helm.schemas.contracts import (
    configuration_key,
    mapping,
)
from hypothesis_helm.schemas.groups import ExhaustiveGroup
from hypothesis_helm.schemas.model import ValuesModel
from hypothesis_helm.schemas.replay import concatenate, select

LOGGER = logging.getLogger(__name__)


def check_chart(
    chart: Chart | str | Path,
    *,
    max_examples: int = 100,
    random_seed: int = 0,
    traversal_strategy: str = "random",
    sampling: Sampling = DEFAULT_SAMPLING,
    timeout: float = 30.0,
    helm: str = "helm",
    release: str = "hypothesis",
    namespace: str = "default",
    kube_version: str | None = None,
    allow_empty: bool = False,
    artifact_dir: Path | None = None,
    exhaustive: bool = False,
    jobs: int = 1,
    max_cases: int = 10000,
    permutations: int | None = None,
    trim: int = 0,
    trim_topology: int = 0,
    expand_failures: bool = False,
    fail_fast: bool = False,
    max_candidates: int = 100000,
    exhaustive_threshold: int = 10000,
    exhaustive_groups: tuple[ExhaustiveGroup, ...] = (),
    infer_exhaustive_groups: bool = True,
    max_group_cases: int = 256,
    dry_run: bool = False,
    time_limit: float = 180.0,
    prune_equivalent: bool = False,
    properties: tuple[Callable[[list[dict[str, object]]], None], ...] = (),
    input_strategy: SearchStrategy[dict[str, object]] | None = None,
    input_inventory: InputInventory | None = None,
    check_defaults: bool = True,
    filter_rejections: bool = False,
    rejection_policy: RejectionPolicy | None = None,
    protected_paths: tuple[tuple[str | int, ...], ...] = (),
    baseline_resources: Sequence[object] | None = None,
) -> dict[str, object]:
    """
    Check defaults then generated overrides, shrinking failing inputs.

    Custom properties receive rendered resources and should raise AssertionError on
    failure. The report is evidence from a bounded sample, never a proof of totality.

    Args:
        chart (Chart | str | Path): Loaded chart and its schema and defaults.
        max_examples (int): Maximum number of generated examples per property.
        random_seed (int): Seed for reproducible property generation.
        traversal_strategy (str): Order retained finite configurations after filtering.
        sampling (Sampling): Optional retained percentage and minimum sample after filtering.
        timeout (float): Maximum seconds allowed for each Helm invocation.
        helm (str): Helm executable used to render the chart.
        release (str): Release name supplied to Helm.
        namespace (str): Release namespace supplied to Helm.
        kube_version (str | None): Optional Kubernetes capability version supplied to Helm.
        allow_empty (bool): Whether a render with no resource documents is accepted.
        artifact_dir (Path | None): Optional destination for failing values and report artifacts.
        exhaustive (bool): Whether to enumerate the entire supported finite input domain.
        jobs (int): Concurrent Helm processes for exhaustive execution; all verification stays on the coordinator.
        max_cases (int): Maximum exhaustive domain or interaction suite and factor size.
        permutations (int | None): Required finite interaction strength when supplied.
        trim (int): Seeded quarter-retention steps applied after finite permutation planning.
        trim_topology (int): Quarter-retention steps within symbolic topology regions.
        expand_failures (bool): Execute omitted members of failed regions within the same budget.
        fail_fast (bool): Stop after the first failure without shrinking or region expansion.
        max_candidates (int): Maximum interaction planning inventory and search work.
        exhaustive_threshold (int): Enumerate smaller Cartesian spaces automatically.
        exhaustive_groups (tuple[ExhaustiveGroup, ...]): Explicitly required local groups.
        infer_exhaustive_groups (bool): Infer additional groups from schema and templates.
        max_group_cases (int): Maximum candidate size of an automatically inferred group.
        dry_run (bool): Plan permutations without rendering or updating history.
        time_limit (float): Positive execution budget in seconds, excluding planning.
        prune_equivalent (bool): Skip Helm only with a successful exact-equivalence witness.
        properties (tuple[Callable[[list[dict[str, object]]], None], ...]): Additional assertions
            over rendered resources.

        input_strategy (SearchStrategy[dict[str, object]] | None): Optional generation-only
            preference; the original chart schema remains authoritative.
        input_inventory (InputInventory | None): Shared compiler inventory for phase comparisons.
        check_defaults (bool): Render the baseline first; path schedulers may skip an already verified baseline.
        filter_rejections (bool): Guide generated inputs using supported explicit rejection contracts.
        rejection_policy (RejectionPolicy | None): Shared per-chart contract verification and counters.
        protected_paths (tuple[tuple[str | int, ...], ...]): Selected paths that dependent-field adjustments must preserve.
        baseline_resources (Sequence[object] | None): Already rendered defaults for comparison across path tests.

    Returns:
        dict[str, object]: Resulting schema, values mapping, or structured report.
    """
    traversal_strategy = validate_strategy(traversal_strategy)
    if input_strategy is not None and (permutations is not None or exhaustive):
        raise ValueError("input_strategy applies to sampled testing only")
    if not check_defaults and input_strategy is None:
        raise ValueError("skipping defaults requires an explicit path input strategy")
    if not isinstance(chart, Chart):
        chart = Chart.load(chart)
    if max_examples < 1 or timeout <= 0:
        raise ValueError("max_examples and timeout must be positive")
    if sampling.percent < 100 and permutations is None and not exhaustive:
        raise ValueError("--sample-random requires a finite plan or path-based testing")
    if type(jobs) is not int or jobs < 1:
        raise ValueError("jobs must be a positive integer")
    if jobs > 1 and (not exhaustive or prune_equivalent or filter_rejections or rejection_policy is not None):
        raise ValueError("parallel exhaustive execution requires exhaustive mode without equivalence pruning or rejection filtering")
    if permutations is not None and exhaustive:
        raise ValueError("permutations and exhaustive are mutually exclusive")
    if expand_failures and permutations is None:
        raise ValueError("expand_failures requires finite permutation planning")
    if dry_run and permutations is None:
        raise ValueError("whole-chart dry runs require permutations")
    if not math.isfinite(time_limit) or time_limit <= 0:
        raise ValueError("time_limit must be positive and finite")
    if (
        type(trim) is not int
        or trim < 0
        or type(trim_topology) is not int
        or trim_topology < 0
        or ((trim or trim_topology) and permutations is None)
    ):
        raise ValueError("trim must be nonnegative and requires finite permutation planning")
    policy = (
        rejection_policy
        if rejection_policy is not None
        else RejectionPolicy(Contracts.build(chart.path), chart.defaults, (chart.path / "values.schema.json").is_file())
        if filter_rejections
        else None
    )
    initial_rejections = policy.snapshot() if policy is not None else {}
    inputs = input_inventory if input_inventory is not None else InputInventory.build(chart)
    if policy is not None and inputs.dependencies.nodes:
        policy.verify_every_candidate = True
    dependency_attempts = {node.path: {"enabled": 0, "disabled": 0, "unknown": 0} for node in inputs.dependencies.nodes}
    field_coverage = FieldCoverage(inputs, chart.defaults)
    LOGGER.info("Compiler input baseline: %d statically named fields", len(inputs.known))
    hashes = RenderHashes(scope="run-local")
    model = ValuesModel.from_schema(chart.schema) if permutations is not None or prune_equivalent else None
    pruner = Pruner(chart.path, chart.defaults, model) if prune_equivalent and model is not None else None
    if pruner is not None and (not release or not namespace):
        pruner.disabled = "empty release or namespace is outside the fixed-context proof contract"
    plan = build_plan(
        chart,
        model,
        PlanningOptions(
            random_seed=random_seed,
            traversal_strategy=traversal_strategy,
            sampling=sampling,
            timeout=timeout,
            helm=helm,
            release=release,
            namespace=namespace,
            kube_version=kube_version,
            allow_empty=allow_empty,
            artifact_dir=artifact_dir,
            exhaustive=exhaustive,
            max_cases=max_cases,
            permutations=permutations,
            trim=trim,
            trim_topology=trim_topology,
            expand_failures=expand_failures,
            max_candidates=max_candidates,
            exhaustive_threshold=exhaustive_threshold,
            exhaustive_groups=exhaustive_groups,
            infer_exhaustive_groups=infer_exhaustive_groups,
            max_group_cases=max_group_cases,
            dry_run=dry_run,
            time_limit=time_limit,
            prune_equivalent=prune_equivalent,
            properties=properties,
        ),
        inventory_report=inputs.report(),
        field_coverage_report=field_coverage.statistics,
        policy_enabled=policy is not None,
        clock=time.perf_counter,
    )
    if plan.dry_report is not None:
        return {**plan.dry_report, "render_hashes": hashes.snapshot(), **({"pruning": pruner.report()} if pruner is not None else {})}
    finite_values = plan.finite_values
    finite_domain_size = plan.finite_domain_size
    duplicate_cases_removed = plan.duplicate_cases_removed
    trimmed_cases = plan.trimmed_cases
    expansion = plan.expansion
    expansion_values = plan.expansion_values
    expansion_positions = plan.expansion_positions
    coverage = plan.coverage
    statistics = plan.statistics
    expansion_failures: list[dict[str, object]] = []
    expansion_checked = 0
    expansion_executed = 0
    baseline_documents = copy.deepcopy(list(baseline_resources)) if baseline_resources is not None else None
    execution_started = time.perf_counter()
    if statistics is not None:
        statistics.started = execution_started

    def remaining_time() -> float:
        """
        Stop scheduling work when the execution budget has expired.

        Returns:
            float: Remaining seconds available to the next bounded operation.
        """
        remaining = time_limit - (time.perf_counter() - execution_started)
        if remaining <= 0:
            raise TimeLimitReached()
        return remaining

    parallel: ExhaustiveRenders | None = None
    prefetched: Future[str] | None = None
    consumed = 0

    def render_candidate(values: dict[str, object], record_hashes: bool) -> list[dict[str, object]]:
        """
        Render within the coordinator's remaining budget and fixed Helm context.

        Args:
            values (dict[str, object]): Overrides to render.
            record_hashes (bool): Record ordinary renders, excluding rejection probes.

        Returns:
            list[dict[str, object]]: Validated rendered resources.
        """
        nonlocal consumed
        output: str | None = None
        if prefetched is not None and record_hashes:
            consumed += 1
            try:
                output = prefetched.result(timeout=remaining_time())
            except TimeoutError as exc:
                raise TimeLimitReached() from exc
        if record_hashes:
            return render(
                chart,
                values,
                helm=helm,
                timeout=min(timeout, remaining_time()),
                release=release,
                namespace=namespace,
                kube_version=kube_version,
                hashes=hashes,
                rendered_output=output,
            )
        return render(
            chart,
            values,
            helm=helm,
            timeout=min(timeout, remaining_time()),
            release=release,
            namespace=namespace,
            kube_version=kube_version,
        )

    def pruning_context() -> str:
        """
        Capture the current environment as part of the exact-equivalence contract.

        Returns:
            str: Stable configuration identity for this rendering context.
        """
        return configuration_key(
            {
                "helm": helm,
                "release": release,
                "namespace": namespace,
                "kube_version": kube_version,
                "timeout": timeout,
                "allow_empty": allow_empty,
                "environment": dict(os.environ),
            }
        )

    checks = CandidateChecks(
        chart=chart,
        inputs=inputs,
        policy=policy,
        pruner=pruner,
        statistics=statistics,
        field_coverage=field_coverage,
        dependency_attempts=dependency_attempts,
        hashes=hashes,
        protected_paths=protected_paths,
        properties=properties,
        clock=time.perf_counter,
        remaining_time=remaining_time,
        render_candidate=render_candidate,
        pruning_context=pruning_context,
        finite_values=finite_values,
        allow_empty=allow_empty,
        baseline_documents=baseline_documents,
    )
    check = checks.check

    def expansion_report(result: dict[str, object]) -> None:
        """
        Report observed failures and scheduled work separately from inference.

        Args:
            result (dict[str, object]): Report receiving expansion accounting.

        Returns:
            None: In-place additions preserve successful and failed execution counts separately.
        """
        result["ignored_rules"] = ignored_codes()
        result["ignored_failures"] = dict(checks.ignored_failures)
        if checks.ignored_failures:
            result["coverage_complete"] = False
            if result["status"] == "passed" and checks.completed_count == 0:
                result["status"] = "ignored"
        if parallel is not None:
            result["parallel_execution"] = {
                "workers": parallel.workers,
                "scheduled_renders": parallel.submitted,
                "finished_render_tasks": parallel.finished,
                "results_consumed": consumed,
                "unverified_scheduled_renders": parallel.submitted - consumed,
                "scope": "Concurrent Helm processes; ordered coordinator validation and one shared execution deadline",
            }
        if inputs.dependencies.nodes:
            result["dependency_activation"] = {
                **inputs.dependencies.report(chart.defaults),
                "render_attempts_by_predicted_state": [{"path": list(path), **counts} for path, counts in dependency_attempts.items()],
                "activation_coverage_proven": False,
            }
        if policy is not None:
            evidence = policy.snapshot()
            for key in (
                "rejected_candidates",
                "filtered_candidates",
                "adjusted_candidates",
                "verification_renders",
                "classifier_disagreements",
                "schema_conflicts",
            ):
                evidence[key] = int(str(evidence[key])) - int(str(initial_rejections.get(key, 0)))
            result["configuration_rejections"] = evidence
            if evidence["rejected_candidates"]:
                result["coverage_complete"] = False
                result["scope"] = "Sample of inputs accepted by analyzed chart validation; rejected configurations are reported separately"
                if result["status"] == "passed" and checks.completed_count <= int(check_defaults):
                    result["status"] = "configuration-rejected"
            if finite_values is not None:
                result["remaining_iterations"] = max(0, len(finite_values) + 1 - checks.count - int(str(evidence["filtered_candidates"])))
                result["unattempted_iterations"] = result["remaining_iterations"]
        if expansion is None:
            return
        total = len(finite_values or []) + 1
        result.update(
            {
                "failure_expansion": {
                    "enabled": True,
                    "additional_scheduled": len(expansion.added),
                    "additional_executed": expansion_executed,
                    "additional_remaining": len(expansion.added) - expansion_executed,
                    "unclassified_inputs": len(expansion_values) - len(expansion.membership),
                    "failures": expansion_failures,
                    "inferred_failures": 0,
                },
                "completed_iterations": expansion_checked,
                "successful_iterations": checks.completed_count,
                "failed_iterations": len(expansion_failures),
                "planned_iterations": total,
                "remaining_iterations": total - expansion_checked,
                "unattempted_iterations": total
                - checks.count
                - (policy.filtered - int(str(initial_rejections.get("filtered_candidates", 0))) if policy is not None else 0),
            }
        )

    def stopped_report() -> dict[str, object]:
        """
        Preserve incomplete coverage and successful measurements on a budget stop.

        Returns:
            dict[str, object]: Graceful time-limit report without a false counterexample.
        """
        total = len(finite_values) + 1 if finite_values is not None else None
        result: dict[str, object] = {
            **coverage,
            "status": "time-limit",
            "exit_code": 124,
            "chart": str(chart.path),
            "seed": random_seed,
            "attempts": checks.count,
            "attempted_iterations": checks.count,
            "completed_iterations": checks.completed_count,
            "planned_iterations": total,
            "remaining_iterations": total - checks.completed_count if total is not None else None,
            "unattempted_iterations": total - checks.count if total is not None else None,
            "coverage_complete": False,
            "proof_of_totality": False,
            "time_limit_seconds": time_limit,
            "execution_seconds": time.perf_counter() - execution_started,
            "render_hashes": hashes.snapshot(),
            **({"pruning": pruner.report()} if pruner is not None else {}),
        }
        message = f"Execution stopped at the {time_limit:g}s time limit; coverage is incomplete"
        LOGGER.info(message)
        hashes.log_summary()
        if statistics is not None:
            result.update(statistics.finish("time-limit", message))
        expansion_report(result)
        if artifact_dir is not None:
            artifact_dir.mkdir(parents=True, exist_ok=True)
            (artifact_dir / "report.json").write_text(json.dumps(result, indent=2) + "\n")
        return result

    def comparisons(values: dict[str, object], documents: list[object] | None) -> dict[str, object]:
        """
        Compare observed inputs and outputs without rendering extra cases or masking failures.

        Args:
            values (dict[str, object]): Exact overrides that failed.
            documents (list[object] | None): Parsed output, if rendering reached that stage.

        Returns:
            dict[str, object]: Replay records or explicit reasons a comparison is unavailable.
        """
        records: dict[str, object] = {}
        for name, before, after in (
            ("overrides", {}, values),
            ("values", chart.defaults, merge_values(chart.defaults, values)),
            ("manifests", checks.baseline_documents, documents),
        ):
            if before is None or after is None:
                records[name] = {"unavailable": "No parsed failing output or successful baseline is available."}
                continue
            try:
                records[name] = compare(before, after)
            except Exception as error:
                records[name] = {"unavailable": f"Comparison could not be recorded: {error}"}
        return records

    def save_failure(exc: BaseException) -> dict[str, object]:
        """
        Persist the final counterexample and construct its failure report.

        Args:
            exc (BaseException): Failure or interruption while checking a chart input.

        Returns:
            dict[str, object]: Resulting schema, values mapping, or structured report.
        """
        hashes.log_summary()
        if pruner is not None:
            LOGGER.info(
                "Exact-equivalence pruning: %d rendered, %d proved equivalent",
                pruner.rendered,
                len(pruner.certificates),
            )
        values, message, documents = checks.last_failure or ({}, str(exc), None)
        result = {
            **coverage,
            "status": "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed",
            "chart": str(chart.path),
            "seed": random_seed,
            "attempts": checks.count,
            "error": message,
            "values": values,
            "input_changes": changed_values(values, chart.defaults),
            "comparisons": comparisons(values, documents),
            "failure_type": type(exc).__name__,
            "code": getattr(exc, "code", None),
            "render_hashes": hashes.snapshot(),
            **({"pruning": pruner.report()} if pruner is not None else {}),
        }
        if statistics is not None:
            result.update(statistics.finish(str(result["status"]), message))
        expansion_report(result)
        if artifact_dir is not None:
            artifact_dir.mkdir(parents=True, exist_ok=True)
            (artifact_dir / "values.json").write_text(yamlio.json_for_helm(values, indent=2) + "\n", encoding="utf-8")
            (artifact_dir / "changes.json").write_text(json.dumps(result["comparisons"], indent=2) + "\n")
            # Write only serializable baselines; an unavailable comparison retains its reason.
            records = mapping(result["comparisons"])
            if "unavailable" not in mapping(records["values"]):
                (artifact_dir / "values-baseline.json").write_text(json.dumps(chart.defaults, indent=2) + "\n")
            if "unavailable" not in mapping(records["manifests"]):
                (artifact_dir / "manifests-baseline.json").write_text(json.dumps(checks.baseline_documents, indent=2) + "\n")
            (artifact_dir / "report.json").write_text(json.dumps(result, indent=2) + "\n")
        return result

    if expansion is not None:
        assert finite_values is not None
        work = [0, *(expansion_positions[configuration_key(value)] for value in finite_values)]
        first_error: Exception | None = None
        first_failure = None
        initial_count = len(work)
        for position, index in enumerate(work):
            values = expansion_values[index]
            try:
                check(values, force_render=position >= initial_count, baseline=position == 0)
            except TimeLimitReached:
                return stopped_report()
            except KeyboardInterrupt as exc:
                save_failure(exc)
                raise
            except Exception as exc:
                failed_values, message, documents = checks.last_failure or (values, str(exc), None)
                expansion_failures.append(
                    {
                        "values": failed_values,
                        "input_changes": changed_values(failed_values, chart.defaults),
                        "error": message,
                        "comparisons": comparisons(failed_values, documents),
                    }
                )
                if fail_fast:
                    expansion_checked += 1
                    expansion_executed += int(position >= initial_count)
                    return save_failure(exc)
                if first_error is None:
                    first_error, first_failure = exc, checks.last_failure
                added = expansion.failed(expansion_positions[configuration_key(values)])
                additional = order_configurations(
                    select(expansion_values, added),
                    lambda value: merge_values(chart.defaults, value),
                    chart.defaults,
                    strategy=traversal_strategy,
                    seed=random_seed,
                )
                work.extend(expansion_positions[configuration_key(value)] for value in additional)
                finite_values = concatenate(finite_values, additional)
                LOGGER.info(
                    "Failure expansion: %d additional cases scheduled; %d remain",
                    len(added),
                    len(work) - position - 1,
                )
            expansion_checked += 1
            expansion_executed += int(position >= initial_count)
        if first_error is not None:
            checks.last_failure = first_failure
            return save_failure(first_error)
        # Successful opt-in runs share the usual finite report below, without repeating checks.

    try:
        if expansion is None and check_defaults:
            check({}, baseline=True)
    except TimeLimitReached:
        return stopped_report()
    except KeyboardInterrupt as exc:
        if statistics is not None or pruner is not None:
            save_failure(exc)
        raise
    except Exception as exc:
        return save_failure(exc)

    if finite_values is not None:
        try:
            if expansion is None:
                if jobs == 1:
                    for values in finite_values:
                        check(values)
                else:
                    parallel = ExhaustiveRenders(
                        chart,
                        finite_values,
                        jobs,
                        time.perf_counter() + remaining_time(),
                        helm=helm,
                        timeout=timeout,
                        release=release,
                        namespace=namespace,
                        kube_version=kube_version,
                    )
                    with parallel:
                        for values, future in parallel:
                            prefetched = future
                            check(values)
                    prefetched = None
        except TimeLimitReached:
            return stopped_report()
        except KeyboardInterrupt as exc:
            if statistics is not None or pruner is not None:
                save_failure(exc)
            raise
        except Exception as exc:
            return save_failure(exc)
        hashes.log_summary()
        if pruner is not None:
            LOGGER.info(
                "Exact-equivalence pruning: %d rendered, %d proved equivalent",
                pruner.rendered,
                len(pruner.certificates),
            )
        result = {
            "render_hashes": hashes.snapshot(),
            **({"pruning": pruner.report()} if pruner is not None else {}),
            "status": "passed",
            "time_limit_seconds": time_limit,
            "execution_seconds": time.perf_counter() - execution_started,
            "chart": str(chart.path),
            "seed": random_seed,
            "attempts": checks.count,
            "mode": "exhaustive",
            **({"domain_size": finite_domain_size} if exhaustive else {}),
            "unique_configurations": len(finite_values) + 1,
            "duplicate_cases_removed": duplicate_cases_removed,
            "scope": "selected subset of finite overrides; random sampling omits inputs"
            if trimmed_cases
            else "all schema-valid overrides in this finite domain, current Helm environment",
            "proof_of_totality": False,
            **coverage,
            "coverage_complete": not bool(trimmed_cases),
        }
        if statistics is not None:
            result.update(statistics.finish("ignored" if checks.ignored_failures and checks.completed_count == 0 else "passed"))
        expansion_report(result)
        if artifact_dir is not None and (statistics is not None or pruner is not None):
            artifact_dir.mkdir(parents=True, exist_ok=True)
            (artifact_dir / "report.json").write_text(json.dumps(result, indent=2) + "\n")
        return result

    first_sample_failure: Exception | None = None

    @seed(random_seed)
    @settings(
        max_examples=max_examples,
        deadline=None,
        database=None,
        phases=(Phase.generate,) if fail_fast else (Phase.generate, Phase.shrink),
        report_multiple_bugs=False,
        suppress_health_check=(HealthCheck.too_slow, HealthCheck.filter_too_much) if policy is not None else (HealthCheck.too_slow,),
    )
    @given(input_strategy if input_strategy is not None else chart.strategy())
    def property_test(values: dict[str, object]) -> None:
        """
        Exercise a schema-generated candidate through the render contract.

        Args:
            values (dict[str, object]): Values document used as the rendering baseline.

        Returns:
            None: None. The operation completes through its documented side effects.
        """
        nonlocal first_sample_failure
        # Hypothesis confirms failures even without shrinking; retain the first
        # counterexample without invoking Helm again in fail-fast mode.
        if first_sample_failure is not None:
            raise first_sample_failure
        ignored_before = sum(checks.ignored_failures.values())
        try:
            accepted = check(values)
        except Exception as exc:
            if fail_fast:
                first_sample_failure = exc
            raise
        # Disabled failures consume an example without becoming a successful witness.
        assume(accepted or sum(checks.ignored_failures.values()) > ignored_before)

    try:
        property_test()
    except TimeLimitReached:
        return stopped_report()
    except KeyboardInterrupt as exc:
        if pruner is not None:
            save_failure(exc)
        raise
    except Unsatisfiable as exc:
        if (
            policy is None
            or policy.filtered == int(str(initial_rejections.get("filtered_candidates", 0)))
            or checks.completed_count > int(check_defaults)
        ):
            return save_failure(exc)
        result = {
            **coverage,
            "status": "configuration-rejected",
            "chart": str(chart.path),
            "attempts": checks.count,
            "seed": random_seed,
            "coverage_complete": False,
            "proof_of_totality": False,
        }
        expansion_report(result)
        if artifact_dir is not None:
            artifact_dir.mkdir(parents=True, exist_ok=True)
            (artifact_dir / "report.json").write_text(json.dumps(result, indent=2) + "\n")
        return result
    except Exception as exc:
        return save_failure(exc)
    hashes.log_summary()
    if pruner is not None:
        LOGGER.info(
            "Exact-equivalence pruning: %d rendered, %d proved equivalent",
            pruner.rendered,
            len(pruner.certificates),
        )
    result = {
        **coverage,
        "render_hashes": hashes.snapshot(),
        **({"pruning": pruner.report()} if pruner is not None else {}),
        "status": "passed",
        "chart": str(chart.path),
        "seed": random_seed,
        "attempts": checks.count,
        "time_limit_seconds": time_limit,
        "execution_seconds": time.perf_counter() - execution_started,
        "max_examples": max_examples,
        "mode": "sampled",
        "proof_of_totality": False,
    }

    expansion_report(result)
    if (pruner is not None or policy is not None) and artifact_dir is not None:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    return result

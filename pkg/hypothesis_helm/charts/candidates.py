"""
Evaluate individual chart candidates and own their observed execution state.
"""

from __future__ import annotations

import copy
import subprocess
from collections.abc import Callable, Sequence

from attrs import define, field
from jsonschema import validators

from hypothesis_helm.charts.model import Chart, merge_values
from hypothesis_helm.charts.rendering import RenderFailure
from hypothesis_helm.compiler.passes.inputs import FieldCoverage, InputInventory
from hypothesis_helm.compiler.passes.pruning import Pruner
from hypothesis_helm.compiler.passes.rejections import RejectionPolicy, matches_rejection
from hypothesis_helm.execution.render_hashes import RenderHashes
from hypothesis_helm.reporting.budget import execution_timer
from hypothesis_helm.reporting.output import emit_manifest
from hypothesis_helm.reporting.permutations import PermutationStatistics
from hypothesis_helm.rules import check as check_rule
from hypothesis_helm.rules import ignored, record_ignored
from hypothesis_helm.schemas.contracts import json_value


@define(kw_only=True)
class CandidateChecks:
    """
    Own candidate counters, render evidence and the policies used by one chart run.

    The coordinator supplies bounded rendering and the remaining execution budget.
    This evaluator never schedules other candidates or writes final reports.

    Attributes:
        chart (Chart): Loaded contract and original values used by this run.
        inputs (InputInventory): Compiler inventory shared by candidate evaluation and reporting.
        policy (RejectionPolicy | None): Explicit rejection predictions and their verification evidence.
        pruner (Pruner | None): Exact-equivalence witnesses and successful representatives.
        statistics (PermutationStatistics | None): Per-iteration timing and completion accounting, when planning is finite.
        field_coverage (FieldCoverage): Live counters for named input paths observed during rendering.
        dependency_attempts (dict[tuple[str, ...], dict[str, int]]): Render attempts grouped by predicted dependency activation state.
        hashes (RenderHashes): Run-local index of rendered bundles.
        protected_paths (tuple[tuple[str | int, ...], ...]): Selected paths that dependent-field adjustments must preserve.
        properties (tuple[Callable[[list[dict[str, object]]], None], ...]): Additional assertions over rendered resources.
        clock (Callable[[], float]): Monotonic clock shared with the coordinator.
        remaining_time (Callable[[], float]): Remaining execution budget, raising when exhausted.
        render_candidate (Callable[[dict[str, object], bool], list[dict[str, object]]]): Coordinator-owned bounded renderer; the Boolean
            selects hash accounting.
        pruning_context (Callable[[], str]): Current environment and fixed renderer context identity.
        finite_values (Sequence[dict[str, object]] | None): Retained finite overrides, or None for Hypothesis generation.
        allow_empty (bool): Whether a render with no resource documents is accepted.
        baseline_documents (list[object] | None): Successful baseline resources retained for failure comparisons.
        ignored_failures (dict[str, int]): Cases blocked by disabled checks, never successful validation witnesses.
        count (int): Number of attempted candidates, including failures.
        completed_count (int): Number of candidates that passed all configured checks.
        last_failure (tuple[dict[str, object], str, list[object] | None] | None): Exact overrides, message and available output from the
            latest failed candidate.
    """

    chart: Chart
    inputs: InputInventory
    policy: RejectionPolicy | None
    pruner: Pruner | None
    statistics: PermutationStatistics | None
    field_coverage: FieldCoverage
    dependency_attempts: dict[tuple[str, ...], dict[str, int]]
    hashes: RenderHashes
    protected_paths: tuple[tuple[str | int, ...], ...]
    properties: tuple[Callable[[list[dict[str, object]]], None], ...]
    clock: Callable[[], float]
    remaining_time: Callable[[], float]
    render_candidate: Callable[[dict[str, object], bool], list[dict[str, object]]]
    pruning_context: Callable[[], str]
    finite_values: Sequence[dict[str, object]] | None
    allow_empty: bool
    baseline_documents: list[object] | None
    ignored_failures: dict[str, int] = field(factory=dict)
    count: int = 0
    completed_count: int = 0
    last_failure: tuple[dict[str, object], str, list[object] | None] | None = None

    def check(self, values: dict[str, object], *, force_render: bool = False, baseline: bool = False) -> bool:
        """
        Render one candidate and retain failure details for replay.

        Args:
            values (dict[str, object]): Values document used as the rendering baseline.
            force_render (bool): Execute Helm for an explicitly expanded input.
            baseline (bool): Always test supplied defaults without excluding or changing them.

        Returns:
            bool: Whether this candidate reached manifest testing rather than configuration exclusion.
        """
        self.remaining_time()
        attempted = False
        iteration_started = self.clock()
        passed = False
        rendered = False
        render_seconds = 0.0
        observed: list[object] | None = None
        try:
            with execution_timer(self.remaining_time()):
                effective = merge_values(self.chart.defaults, values)
                # Helm coalesces child defaults and imports before validating dependency charts.
                # A parent-only merge cannot authoritatively reject those configurations.
                if not self.inputs.dependencies.nodes:
                    validators.validator_for(self.chart.schema)(self.chart.schema).validate(json_value(effective))
                rejection = (
                    self.policy.predict(effective) if self.policy is not None and not baseline and not self.policy.declared_schema else None
                )
                if rejection is not None and self.policy is not None:
                    if self.policy.needs_probe(rejection, effective):
                        self.policy.probes += 1
                        try:
                            self.render_candidate(values, False)
                        except RenderFailure as exc:
                            if not matches_rejection(str(exc), rejection):
                                self.policy.disabled.add(rejection.key)
                                self.policy.contradictions += 1
                                raise
                            self.policy.verified(rejection, effective)
                        else:
                            self.policy.disabled.add(rejection.key)
                            self.policy.contradictions += 1
                            rejection = None
                    if rejection is not None:
                        self.policy.candidates += 1
                        record = self.policy.records[rejection.key]
                        record["occurrences"] = int(str(record["occurrences"])) + 1
                        replacement = self.policy.repair(
                            values,
                            rejection,
                            self.protected_paths if self.finite_values is None else ((),),
                            lambda candidate: (
                                validators.validator_for(self.chart.schema)(self.chart.schema).is_valid(
                                    json_value(merge_values(self.chart.defaults, candidate))
                                )
                                and self.policy is not None
                                and self.policy.predict(merge_values(self.chart.defaults, candidate)) is None
                            ),
                        )
                        if replacement is None:
                            self.policy.filtered += 1
                            return False
                        self.policy.adjusted += 1
                        values = replacement
                        effective = merge_values(self.chart.defaults, values)
                self.count += 1
                attempted = True
                witness = None
                resources = None
                if self.pruner is not None:
                    context = self.pruning_context()
                    witness = self.pruner.candidate(values, effective, context)
                    resources = self.pruner.lookup(None if force_render else witness, self.count)
                if resources is None:
                    self.field_coverage.observe(effective)
                    for path, state in self.inputs.dependencies.states(self.chart.defaults, values).items():
                        self.dependency_attempts[path]["unknown" if state is None else "enabled" if state else "disabled"] += 1
                    render_started = self.clock()
                    rendered = True
                    resources = self.render_candidate(values, True)
                    render_seconds = self.clock() - render_started
                else:
                    for resource in resources:
                        emit_manifest(resource)
                pristine = copy.deepcopy(resources) if self.pruner is not None or self.properties else resources
                observed = list(pristine)
                if not resources and not self.allow_empty:
                    check_rule(False, "HH1009", "chart rendered no resources (use allow_empty explicitly)")
                for prop in self.properties:
                    self.remaining_time()
                    prop(resources)
                passed = True
                if baseline:
                    self.baseline_documents = copy.deepcopy(observed)
                self.completed_count += 1
                if self.pruner is not None:
                    self.pruner.remember(witness, self.count, pristine)
                return True
        except RenderFailure as exc:
            if not attempted:
                self.count += 1
                attempted = True
            if isinstance(exc.__cause__, subprocess.TimeoutExpired):
                self.remaining_time()
            if ignored(exc.code):
                record_ignored(exc.code, str(exc))
                self.ignored_failures[exc.code] = self.ignored_failures.get(exc.code, 0) + 1
                return False
            if self.policy is not None and self.policy.declared_schema:
                declared_rejection = self.policy.predict(merge_values(self.chart.defaults, values))
                if declared_rejection is not None and matches_rejection(str(exc), declared_rejection):
                    self.policy.schema_conflicts += 1
                    self.policy.verified(declared_rejection, merge_values(self.chart.defaults, values))
                    conflict_record = self.policy.records[declared_rejection.key]
                    conflict_record["occurrences"] = int(str(conflict_record["occurrences"])) + 1
            self.last_failure = (values, str(exc), observed if observed is not None else exc.resources)
            raise
        except (Exception, KeyboardInterrupt) as exc:
            if not attempted:
                self.count += 1
                attempted = True
            self.last_failure = (values, str(exc), observed)
            raise
        finally:
            if self.statistics is not None and attempted:
                self.statistics.advance(
                    passed,
                    self.clock() - iteration_started,
                    rendered=rendered,
                    render_seconds=render_seconds,
                )

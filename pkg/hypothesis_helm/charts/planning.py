"""
Plan finite inputs, filtering, failure expansion and progressive estimates before execution.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Sequence
from pathlib import Path

from attrs import frozen
from jsonschema import validators

from hypothesis_helm.charts.model import Chart, merge_values
from hypothesis_helm.compiler.passes.expansion import FailureExpansion
from hypothesis_helm.compiler.passes.sampling import profile as sampling_profile
from hypothesis_helm.compiler.passes.topology import trim_topology as topology_trim
from hypothesis_helm.execution.aggressive import select as select_aggressive
from hypothesis_helm.execution.sampling import DEFAULT_SAMPLING, Sampling
from hypothesis_helm.execution.traversal import ALGORITHM, order_configurations
from hypothesis_helm.reporting.permutations import PermutationStatistics
from hypothesis_helm.reporting.progressive import estimate_progression
from hypothesis_helm.schemas.combinations import plan_interactions, trim_values
from hypothesis_helm.schemas.conformity import ENVIRONMENT
from hypothesis_helm.schemas.contracts import configuration_key, json_value, mapping
from hypothesis_helm.schemas.finite import enumerate_values
from hypothesis_helm.schemas.groups import ExhaustiveGroup, infer_groups
from hypothesis_helm.schemas.model import ValuesModel
from hypothesis_helm.schemas.replay import concatenate, select, transform

LOGGER = logging.getLogger(__name__)


@frozen(kw_only=True)
class PlanningOptions:
    """
    Keep the coordinator's finite-domain selection and estimation settings together.

    Attributes:
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
        max_cases (int): Maximum exhaustive domain or interaction suite and factor size.
        permutations (int | None): Required finite interaction strength when supplied.
        trim (int): Seeded quarter-retention steps applied after finite permutation planning.
        trim_topology (int): Quarter-retention steps within symbolic topology regions.
        expand_failures (bool): Execute omitted members of failed regions within the same budget.
        max_candidates (int): Maximum interaction planning inventory and search work.
        exhaustive_threshold (int): Enumerate smaller Cartesian spaces automatically.
        exhaustive_groups (tuple[ExhaustiveGroup, ...]): Explicitly required local groups.
        infer_exhaustive_groups (bool): Infer additional groups from schema and templates.
        max_group_cases (int): Maximum candidate size of an automatically inferred group.
        dry_run (bool): Plan permutations without rendering or updating history.
        time_limit (float): Positive execution budget in seconds, excluding planning.
        prune_equivalent (bool): Skip Helm only with a successful exact-equivalence witness.
        properties (tuple[Callable[[list[dict[str, object]]], None], ...]): Additional assertions over rendered resources.
    """

    random_seed: int = 0
    traversal_strategy: str = "random"
    sampling: Sampling = DEFAULT_SAMPLING
    timeout: float = 30.0
    helm: str = "helm"
    release: str = "hypothesis"
    namespace: str = "default"
    kube_version: str | None = None
    allow_empty: bool = False
    artifact_dir: Path | None = None
    exhaustive: bool = False
    max_cases: int = 10000
    permutations: int | None = None
    trim: int = 0
    trim_topology: int = 0
    expand_failures: bool = False
    max_candidates: int = 100000
    exhaustive_threshold: int = 10000
    exhaustive_groups: tuple[ExhaustiveGroup, ...] = ()
    infer_exhaustive_groups: bool = True
    max_group_cases: int = 256
    dry_run: bool = False
    time_limit: float = 180.0
    prune_equivalent: bool = False
    properties: tuple[Callable[[list[dict[str, object]]], None], ...] = ()


@frozen
class PlannedRun:
    """
    Transfer a complete plan and its mutable execution-accounting objects to the coordinator.

    Attributes:
        finite_values (Sequence[dict[str, object]] | None): Retained finite overrides, or None for Hypothesis generation.
        finite_domain_size (int | None): Complete exhaustive domain size before default merging and deduplication.
        duplicate_cases_removed (int): Configurations already represented by defaults or another input.
        trimmed_cases (int): Non-default configurations omitted by the selected filters.
        expansion (FailureExpansion | None): Failure-region scheduling state, when expansion is enabled.
        expansion_values (Sequence[dict[str, object]]): Untrimmed inputs available for failure-region expansion.
        expansion_positions (dict[str, int]): Stable configuration identities mapped to expansion indices.
        coverage (dict[str, object]): Plan and input-coverage evidence included in execution reports.
        statistics (PermutationStatistics | None): Per-iteration timing and completion accounting, when planning is finite.
        dry_report (dict[str, object] | None): Completed progressive estimate, or None when tests should execute.
    """

    finite_values: Sequence[dict[str, object]] | None
    finite_domain_size: int | None
    duplicate_cases_removed: int
    trimmed_cases: int
    expansion: FailureExpansion | None
    expansion_values: Sequence[dict[str, object]]
    expansion_positions: dict[str, int]
    coverage: dict[str, object]
    statistics: PermutationStatistics | None
    dry_report: dict[str, object] | None


def select_cases(
    chart: Chart,
    values: Sequence[dict[str, object]],
    options: PlanningOptions,
    sampling_analysis: dict[str, object] | None,
) -> tuple[Sequence[dict[str, object]], dict[str, object], dict[str, object]]:
    """
    Apply the shared production selectors before ordering retained configurations.

    Args:
        chart (Chart): Current chart and defaults.
        values (Sequence[dict[str, object]]): Unique non-default configurations from the finite plan.
        options (PlanningOptions): Filtering, sampling and traversal settings.
        sampling_analysis (dict[str, object] | None): Fresh complexity profile for aggressive sampling.

    Returns:
        tuple[Sequence[dict[str, object]], dict[str, object], dict[str, object]]:
            Ordered configurations, topology evidence and sampling decisions.
    """
    topology: dict[str, object] = {}
    memberships: dict[str, str] = {}
    if options.trim_topology:
        selected, topology = topology_trim(
            chart.path,
            chart.defaults,
            values,
            transform(values, lambda item: merge_values(chart.defaults, item)),
            options.trim_topology,
            options.random_seed,
            random_steps=options.trim,
            memberships=memberships,
            fixed_names=bool(options.release and options.namespace),
        )
    else:
        selected = trim_values(values, options.trim, options.random_seed)
    protected: set[str] = set()
    regions: set[str] = set()
    if options.trim_topology:
        for value in selected:
            identity = configuration_key(value)
            region = memberships.get(identity)
            if region is None or region not in regions:
                protected.add(identity)
                if region is not None:
                    regions.add(region)
    if sampling_analysis is not None:
        selected, sampling_report = select_aggressive(
            chart,
            options.sampling,
            selected,
            options.random_seed,
            protected=protected,
            analysis=sampling_analysis,
            topology=topology,
            context={"strength": options.permutations, "trim": options.trim, "trim_topology": options.trim_topology},
        )
    else:
        selected, sampling_report = options.sampling.select(selected, configuration_key, options.random_seed, protected=protected)
    sampling_report["unit"] = "non-default configuration"
    ordered = order_configurations(
        selected,
        lambda value: merge_values(chart.defaults, value),
        chart.defaults,
        strategy=options.traversal_strategy,
        seed=options.random_seed,
    )
    return ordered, topology, sampling_report


def build_plan(
    chart: Chart,
    model: ValuesModel | None,
    options: PlanningOptions,
    *,
    inventory_report: dict[str, object],
    field_coverage_report: dict[str, object],
    policy_enabled: bool,
    clock: Callable[[], float],
) -> PlannedRun:
    """
    Complete finite planning and optional estimation before the execution budget starts.

    Args:
        chart (Chart): Chart schema and original defaults.
        model (ValuesModel | None): Shared typed model when finite planning is enabled.
        options (PlanningOptions): Finite-domain and rendering-context settings.
        inventory_report (dict[str, object]): Compiler's already collected input inventory.
        field_coverage_report (dict[str, object]): Live field-coverage counters shared with execution.
        policy_enabled (bool): Whether explicit chart rejections will guide execution.
        clock (Callable[[], float]): Monotonic clock shared with execution statistics.

    Returns:
        PlannedRun: Planned inputs, coverage accounting and optional dry-run report.
    """
    planning_started = clock()
    sampling_analysis = sampling_profile(chart) if options.sampling.aggressive else None
    dry_report = None
    interaction_plan = None
    group_diagnostics: list[dict[str, object]] = []
    if options.permutations is not None:
        LOGGER.info(
            "Planning %d-way permutations (max cases %d, max candidates %d)",
            options.permutations,
            options.max_cases,
            options.max_candidates,
        )
        validator = validators.validator_for(chart.schema)(chart.schema)
        assert model is not None
        inferred: list[ExhaustiveGroup] = []
        if options.infer_exhaustive_groups:
            inferred, group_diagnostics = infer_groups(chart.path, model)
        interaction_plan = plan_interactions(
            model,
            options.permutations,
            max_cases=options.max_cases,
            max_candidates=options.max_candidates,
            accept=lambda values: validator.is_valid(json_value(merge_values(chart.defaults, values))),
            exhaustive_threshold=options.exhaustive_threshold,
            exhaustive_groups=(*options.exhaustive_groups, *inferred),
            max_group_cases=options.max_group_cases,
        )
    finite_values = enumerate_values(chart.schema, options.max_cases) if options.exhaustive else None
    finite_domain_size = len(finite_values) if finite_values is not None else None
    duplicate_cases_removed = 0
    if interaction_plan is not None:
        finite_values = interaction_plan.values
    if finite_values is not None:
        seen = {configuration_key(chart.defaults)}
        distinct: list[int] = []
        for index, values in enumerate(finite_values):
            identity = configuration_key(merge_values(chart.defaults, values))
            if identity in seen:
                duplicate_cases_removed += 1
            else:
                seen.add(identity)
                distinct.append(index)
        finite_values = select(finite_values, distinct)
        if interaction_plan is not None:
            interaction_plan.values = finite_values
            interaction_plan.duplicate_cases_removed = duplicate_cases_removed
    topology: dict[str, object] = {}
    sampling_report: dict[str, object] = {}

    expansion_values = concatenate([{}], finite_values or []) if options.expand_failures else []
    untrimmed_cases = len(finite_values) if finite_values is not None else 0
    if interaction_plan is not None:
        interaction_plan.values, topology, sampling_report = select_cases(chart, interaction_plan.values, options, sampling_analysis)
    elif finite_values is not None:
        finite_values, topology, sampling_report = select_cases(chart, finite_values, options, sampling_analysis)
    trimmed_cases = (
        untrimmed_cases - len(finite_values or []) if interaction_plan is None else untrimmed_cases - len(interaction_plan.values)
    )
    if options.sampling.percent < 100:
        LOGGER.info(
            "Random sampling: %s/%s retained; %s omitted; minimum %s; no bug-recall guarantee",
            sampling_report.get("retained", 0),
            sampling_report.get("eligible", 0),
            sampling_report.get("omitted", 0),
            options.sampling.minimum,
        )
    expansion = None
    expansion_positions = {configuration_key(value): index for index, value in enumerate(expansion_values)}
    if options.expand_failures and interaction_plan is not None:
        expansion = FailureExpansion.build(
            chart.path,
            chart.defaults,
            expansion_values,
            transform(expansion_values, lambda value: merge_values(chart.defaults, value)),
            [
                0,
                *(expansion_positions[configuration_key(value)] for value in interaction_plan.values),
            ],
            fixed_names=bool(options.release and options.namespace),
        )
    coverage: dict[str, object] = {
        "sampling": sampling_report,
        "input_inventory": inventory_report,
        "field_coverage": field_coverage_report,
        "traversal_strategy": options.traversal_strategy,
        "traversal_algorithm": ALGORITHM,
        "traversal_unit": "configuration" if finite_values is not None else "Hypothesis samples",
    }
    statistics = None
    if interaction_plan is not None:
        finite_values = interaction_plan.values
        coverage = {
            **coverage,
            "mode": "permutations",
            "trim": options.trim,
            "trim_random": options.trim,
            "trim_topology": options.trim_topology,
            "expand_failures": options.expand_failures,
            "topology": topology,
            "trim_seed": options.random_seed,
            "untrimmed_iterations": untrimmed_cases + 1,
            "trimmed_iterations": trimmed_cases,
            "retained_fraction": (len(interaction_plan.values) / untrimmed_cases) if untrimmed_cases else 1.0,
            "coverage_guaranteed_by_plan": not bool(trimmed_cases),
            "coverage_strategy": "trimmed" if trimmed_cases else interaction_plan.strategy,
            "untrimmed_coverage_strategy": interaction_plan.strategy,
            "exhaustive_groups_scope": "untrimmed plan",
            "requested_strength": options.permutations,
            "effective_strength": interaction_plan.strength,
            "factors": [list(path) for path in interaction_plan.factors],
            "factor_domains": [list(domain) for domain in interaction_plan.domains],
            "planned_cases": len(interaction_plan.values),
            "valid_interactions": interaction_plan.interactions,
            "planning_candidates": interaction_plan.candidates,
            "exhaustive_groups": interaction_plan.group_reports,
            "group_diagnostics": group_diagnostics,
            "coverage_complete": False,
            "proof_of_totality": False,
            "scope": "schema-valid finite factor interactions with schema-valid merged values",
        }
        statistics = PermutationStatistics(
            chart.path,
            interaction_plan,
            options.artifact_dir,
            clock() - planning_started,
            {
                "sampling": {
                    "percent": options.sampling.percent,
                    "minimum": options.sampling.minimum,
                    "aggressive": options.sampling.aggressive,
                    "calibration": options.sampling.calibration,
                    "calibration_id": mapping(sampling_report.get("aggressive", {})).get("calibration_id"),
                },
                "trim": options.trim,
                "trim_topology": options.trim_topology,
                "expand_failures": options.expand_failures,
                "trim_seed": options.random_seed,
                "traversal_strategy": options.traversal_strategy,
                "helm": options.helm,
                "release": options.release,
                "namespace": options.namespace,
                "kube_version": options.kube_version,
                "timeout": options.timeout,
                "allow_empty": options.allow_empty,
                "conformity": os.environ.get(ENVIRONMENT),
                "custom_properties": bool(options.properties),
                "prune_equivalent": options.prune_equivalent,
                "filter_rejections": policy_enabled,
            },
        )
        LOGGER.info("Coverage strategy: %s", coverage["coverage_strategy"])
        if options.trim or options.trim_topology:
            LOGGER.info(
                "Trim random=%d, topology=%d: %d non-default cases retained, %d omitted; "
                "defaults retained; "
                "interaction and group coverage are not guaranteed when cases are omitted",
                options.trim,
                options.trim_topology,
                len(interaction_plan.values),
                trimmed_cases,
            )
        for group in interaction_plan.group_reports:
            LOGGER.info(
                "Planned exhaustive group %s: %s (%s candidate assignments)%s",
                group["source"],
                group["status"],
                group["candidate_assignments"],
                f"; {group['reason']}" if group["reason"] else "",
            )
        for diagnostic in group_diagnostics:
            LOGGER.info("Group inference needs review: %s", diagnostic)
        if options.dry_run:
            assert model is not None
            progression = estimate_progression(
                chart.path,
                chart.defaults,
                model,
                interaction_plan,
                lambda strength: plan_interactions(
                    model,
                    strength,
                    max_cases=options.max_cases,
                    max_candidates=options.max_candidates,
                    accept=lambda values: validator.is_valid(json_value(merge_values(chart.defaults, values))),
                    exhaustive_threshold=0,
                    exhaustive_groups=(*options.exhaustive_groups, *inferred),
                    max_group_cases=options.max_group_cases,
                ),
                lambda values: merge_values(chart.defaults, values),
                pruning=options.prune_equivalent,
                max_cases=options.max_cases,
                max_candidates=options.max_candidates,
                history=statistics.previous if statistics.previous.get("context") == statistics.context and not options.properties else {},
                selector=lambda values: select_cases(chart, values, options, sampling_analysis)[0],
                trim_topology=options.trim_topology,
                trim=options.trim,
                random_seed=options.random_seed,
                fixed_names=bool(options.release and options.namespace),
                time_limit=options.time_limit,
            )
            dry_report = {
                "failure_expansion": {
                    "enabled": options.expand_failures,
                    "maximum_additional_iterations": trimmed_cases,
                    "actual_additions": "depend on observed failures",
                },
                "progressive_estimate": progression,
                **coverage,
                **statistics.snapshot(),
                "time_limit_seconds": options.time_limit,
                "status": "dry-run",
                "exit_code": 0,
                "chart": str(chart.path),
                "attempts": 0,
            }
    return PlannedRun(
        finite_values,
        finite_domain_size,
        duplicate_cases_removed,
        trimmed_cases,
        expansion,
        expansion_values,
        expansion_positions,
        coverage,
        statistics,
        dry_report,
    )

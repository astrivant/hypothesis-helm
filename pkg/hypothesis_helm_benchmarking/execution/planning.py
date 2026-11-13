"""
Pass explicit backend options to every measured finite planner and retain its receipts.
"""

from __future__ import annotations

from hypothesis_helm.compiler.backends.scheduler import DEFAULT_BACKEND
from hypothesis_helm.schemas.generation.combinations import InteractionPlan, plan_interactions
from hypothesis_helm.schemas.model import ValuesModel

from hypothesis_helm_benchmarking.charts.fixture import FixtureWorkspace

__all__ = ("plan",)


def plan(
    schema: dict[str, object] | ValuesModel,
    strength: int,
    *,
    workspace: FixtureWorkspace | None = None,
    max_cases: int = 10000,
    max_candidates: int = 100000,
    exhaustive_threshold: int = 10000,
) -> InteractionPlan:
    """
    Measure the production planner with the invocation's explicit compute settings.

    Args:
        schema (dict[str, object] | ValuesModel): Original schema or shared typed model.
        strength (int): Required interaction strength.
        workspace (FixtureWorkspace | None): Invocation owner and receipt sink; absent means reference execution.
        max_cases (int): Maximum configurations and per-factor domain size.
        max_candidates (int): Logical planning and interaction-inventory limit.
        exhaustive_threshold (int): Automatic exhaustive promotion limit; zero disables promotion.

    Returns:
        InteractionPlan: Exact ordered selection with measured backend provenance.
    """
    result = plan_interactions(
        schema,
        strength,
        max_cases=max_cases,
        max_candidates=max_candidates,
        exhaustive_threshold=exhaustive_threshold,
        backend=workspace.backend if workspace is not None else DEFAULT_BACKEND,
    )
    if workspace is not None:
        workspace.backend_reports.append(result.backend_report)
    return result

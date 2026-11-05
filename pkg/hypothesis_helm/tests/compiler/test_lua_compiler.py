"""
Keep Lua complexity bounds identical to Python evidence, including fallback boundaries.
"""

import itertools
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from hypothesis_helm.compiler.lua.bounds import BoundEvaluator
from hypothesis_helm.compiler.passes.complexity import Component, OutputCase, bound, measure
from hypothesis_helm.environment import refresh_env
from hypothesis_helm.schemas.configuration.policy import ENVIRONMENT
from hypothesis_helm.schemas.contracts import mapping
from hypothesis_helm.tests.compiler.test_complexity import _chart

MEMORY = 64 * 1024 * 1024


@st.composite
def component_tables(draw: st.DrawFn) -> list[Component]:
    """
    Generate complete small tables with shared factors, invalid rows and empty outputs.

    Args:
        draw (st.DrawFn): Hypothesis source of structural choices.

    Returns:
        list[Component]: Complete local domains with arbitrary nonnegative level counts.
    """
    components = []
    for _ in range(draw(st.integers(0, 5))):
        factors = tuple(sorted(draw(st.sets(st.integers(0, 3), max_size=3))))
        cases = []
        for choices in itertools.product(range(2), repeat=len(factors)):
            valid = draw(st.booleans())
            levels = tuple(draw(st.lists(st.integers(0, 10000), max_size=8))) if valid else ()
            cases.append(OutputCase(choices, () if valid else None, levels))
        components.append(Component(factors, tuple(cases)))
    return components


@given(component_tables(), st.dictionaries(st.integers(0, 4), st.integers(0, 2)))
@settings(max_examples=150, deadline=None)
def test_lua_matches_reference(components: list[Component], assigned: dict[int, int]) -> None:
    """
    Compare repeated Lua queries against Python for arbitrary shared-factor component tables.

    Args:
        components (list[Component]): Complete component tables.
        assigned (dict[int, int]): Partial choices, including impossible domain indices.

    Returns:
        None: No conversion, empty-state or integer-zero case changes the bound.
    """
    evaluator = BoundEvaluator(components, max_memory_bytes=MEMORY)
    for assignment in ({}, assigned, {0: 0}, {0: 1}, {}):
        assert evaluator(assignment) == bound(components, assignment)
    assert evaluator.lua_calls == 4
    assert evaluator.fallback_reason is None


@pytest.mark.parametrize("levels", [((1, 2**63),), ((1, 2**62),), ((2**62,), (2**62,))])
def test_large_integers_use_exact_python_fallback(levels: tuple[tuple[int, ...], ...]) -> None:
    """
    Preserve admissible bounds across conversion, addition and multiplication overflow.

    Args:
        levels (tuple[tuple[int, ...], ...]): Valid profiles crossing each Lua integer boundary.

    Returns:
        None: Lua never wraps an upper bound into a smaller pruning value.
    """
    components = [Component((), (OutputCase((), (), profile),)) for profile in levels]
    evaluator = BoundEvaluator(components, max_memory_bytes=MEMORY)
    assert evaluator({}) == bound(components, {})
    assert evaluator({}) == bound(components, {})
    assert evaluator.python_calls == 2
    assert evaluator.fallback_reason is not None


def test_memory_exhaustion_keeps_python_evidence() -> None:
    """
    Fall back without claiming impossible output when the Lua allocation budget is exhausted.

    Returns:
        None: The exact Python bound remains available and fallback is recorded.
    """
    components = [Component((0,), (OutputCase((0,), (), (1, 8)),))]
    evaluator = BoundEvaluator(components, max_memory_bytes=1)
    assert evaluator({}) == 16
    assert evaluator({0: 0}) == 16
    assert evaluator.report()["engine"] == "python"
    assert evaluator.fallback_reason is not None
    assert evaluator.runtime is None


def test_keyboard_interrupt_is_not_swallowed() -> None:
    """
    Preserve coordinator shutdown signals instead of treating them as optimization failures.

    Returns:
        None: Cancellation immediately propagates out of the bound evaluator.
    """
    evaluator = BoundEvaluator([], max_memory_bytes=MEMORY)
    evaluator({})
    evaluator.prepare()

    def interrupt(assigned: object) -> object:
        """
        Simulate cancellation while calling the native kernel.

        Args:
            assigned (object): Prepared Lua assignment table.

        Returns:
            object: No result is produced after interruption.
        """
        raise KeyboardInterrupt

    evaluator.evaluate = interrupt
    with pytest.raises(KeyboardInterrupt):
        evaluator({})


def test_independent_runtimes_for_parallel_analyses() -> None:
    """
    Keep concurrent analyses from sharing Lua tables or assignment state.

    Returns:
        None: Independent workers obtain only their own component bounds.
    """

    def run(value: int) -> int:
        """
        Query one worker's isolated evaluator repeatedly.

        Args:
            value (int): Distinct breadth assigned to this worker.

        Returns:
            int: Last exact bound after native calls.
        """
        evaluator = BoundEvaluator([Component((), (OutputCase((), (), (1, value)),))], max_memory_bytes=MEMORY)
        for _ in range(10):
            assert evaluator({}) == 2 * value
        return evaluator({})

    with ThreadPoolExecutor(max_workers=4) as workers:
        assert list(workers.map(run, range(1, 9))) == list(range(2, 18, 2))


def test_lua_and_fallback_searches_keep_identical_witnesses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Compare complete chart searches under normal and deliberately exhausted Lua memory budgets.

    Args:
        tmp_path (Path): Finite chart source.
        monkeypatch (pytest.MonkeyPatch): Select per-chart runtime allocation limits.

    Returns:
        None: Maximum, witness and search accounting are unchanged by backend selection.
    """
    chart = _chart(tmp_path)
    normal = measure(chart)
    monkeypatch.setenv(
        ENVIRONMENT, json.dumps({"input_constraints": [{"charts": ["example"], "path": "$", "compiler": {"max_lua_memory_bytes": 1}}]})
    )
    refresh_env()
    fallback = measure(chart)
    assert mapping(normal["bound_backend"])["engine"] == "lua54"
    assert mapping(fallback["bound_backend"])["fallback_reason"] is not None
    assert {key: value for key, value in normal.items() if key not in {"analysis_seconds", "bound_backend"}} == {
        key: value for key, value in fallback.items() if key not in {"analysis_seconds", "bound_backend"}
    }

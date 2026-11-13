"""
Compile sparse benchmark trees within the existing finite-program budgets.
"""

from __future__ import annotations

import copy
import itertools
import json
from pathlib import Path

import pytest
from hypothesis_helm.compiler.backends.engine import prepare
from hypothesis_helm.compiler.backends.lowering import compile_plan
from hypothesis_helm.compiler.backends.model import DEFAULT_LIMITS, State
from hypothesis_helm.schemas.contracts import mapping
from hypothesis_helm.schemas.generation.factors import factor_space
from hypothesis_helm_benchmarking.charts.generator import generate
from hypothesis_helm_benchmarking.charts.structural_sparsity import configure
from jsonschema import Draft202012Validator


@pytest.mark.parametrize("breadth", [50, 800])
def test_deep_sparse_benchmark_compiles_with_default_limits(tmp_path: Path, native_backend: str, breadth: int) -> None:
    """
    Reproduce the failed depth-24 workload and the largest default benchmark profile.

    Args:
        tmp_path (Path): Isolated generated chart.
        native_backend (str): Explicit real CPU or GPU verification lane.
        breadth (int): Failed or largest supported default branch count.

    Returns:
        None: The default-budget program accepts the same sixteen valid configurations.
    """
    chart = tmp_path / "chart"
    generate(chart, input_complexity=4)
    configure(chart, breadth, 24, "near", 2026)
    schema = mapping(json.loads((chart / "values.schema.json").read_text()))
    space = factor_space(schema)
    program = compile_plan(schema, space)
    assert program.limits == DEFAULT_LIMITS
    assert len(program.nodes) < 128
    assert program.cardinality == 16
    validator = Draft202012Validator(schema)
    expected = []
    for assignments in itertools.product(*space.domains):
        values = copy.deepcopy(space.skeleton)
        for path, assignment in zip(space.paths, assignments, strict=True):
            target = values
            for component in path[:-1]:
                target = mapping(target[component])
            target.update(assignment)
        expected.append(State.TRUE if validator.is_valid(values) else State.FALSE)
    engine = prepare(program, native_backend)
    try:
        assert engine.evaluate(tuple(range(16))).states == tuple(expected) == (State.TRUE,) * 16
    finally:
        engine.close()


@pytest.mark.parametrize(
    "fragment,expected",
    [
        ({"oneOf": [True, True]}, State.FALSE),
        ({"oneOf": [True, False]}, State.TRUE),
        ({"oneOf": [True, {"pattern": "synthetic"}]}, State.UNKNOWN),
        ({"allOf": [False, {"pattern": "synthetic"}]}, State.FALSE),
        ({"anyOf": [True, {"pattern": "synthetic"}]}, State.TRUE),
        ({"not": {"pattern": "synthetic"}}, State.UNKNOWN),
    ],
)
def test_constant_folding_preserves_three_state_logic(fragment: dict[str, object], expected: State) -> None:
    """
    Preserve decisive constants, unknown host work and duplicate oneOf operands.

    Args:
        fragment (dict[str, object]): A finite composition with explicit constants and unknowns.
        expected (State): Required conservative three-state result.

    Returns:
        None: Constant propagation preserves production truth semantics and fallback evidence.
    """
    schema = {"type": "object", "properties": {}, "additionalProperties": False, **fragment}
    program = compile_plan(schema, factor_space(schema))
    engine = prepare(program, "reference")
    try:
        assert engine.evaluate((0,)).states == (expected,)
        if expected == State.UNKNOWN:
            assert program.fallbacks
    finally:
        engine.close()

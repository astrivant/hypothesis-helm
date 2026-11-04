"""
Compare compiled programs against an independent JSON Schema oracle and serial planner.
"""

from __future__ import annotations

import copy
import itertools
import json
import tomllib
from collections.abc import Iterator
from pathlib import Path

import pytest
from attrs import evolve
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis_helm.compiler.backends.engine import prepare
from hypothesis_helm.compiler.backends.lowering import compile_plan
from hypothesis_helm.compiler.backends.model import Factor, Limits, Node, Opcode, Plan, State, digest, load_plan
from hypothesis_helm.compiler.backends.scheduler import BackendOptions
from hypothesis_helm.exceptions.backends import InvalidPlan
from hypothesis_helm.exceptions.schemas import NonFiniteSchema
from hypothesis_helm.schemas.generation.combinations import plan_interactions
from hypothesis_helm.schemas.generation.factors import factor_space
from hypothesis_helm.schemas.generation.finite import enumerate_values
from jsonschema import validators
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet


def schema_fixture() -> dict[str, object]:
    """
    Combine typed finite values, omission, nested predicates and irregular fan-in.

    Returns:
        dict[str, object]: A small closed schema with cross-factor constraints.
    """
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "enabled": {"type": "boolean"},
            "count": {"enum": [None, False, -2, 0, 1, 2, 2**63 - 1]},
            "name": {"enum": ["", "a", "\u03b1"]},
        },
        "required": ["enabled"],
        "allOf": [
            {"if": {"properties": {"enabled": {"const": True}}}, "then": {"required": ["count"]}},
            {"anyOf": [{"properties": {"count": {"type": "integer", "minimum": 0}}}, {"properties": {"enabled": {"const": False}}}]},
            {"not": {"required": ["name"], "properties": {"name": {"const": "a"}, "count": {"const": 2}}}},
        ],
    }


def test_cuda_numpy_dependency_range() -> None:
    """
    Keep the selected CUDA compiler inside NVIDIA's supported NumPy range.

    Returns:
        None: Dependency markers retain compatible CUDA and Python 3.15 CPU versions.
    """
    project = Path(__file__).resolve().parents[2] / "pyproject.toml"
    with project.open("rb") as stream:
        settings = tomllib.load(stream)["tool"]["poetry"]
    for requirements in (settings["dependencies"]["numpy"], settings["group"]["dev"]["dependencies"]["numpy"]):
        for version, accepted, rejected in (("3.13", "2.4.6", "2.5.0"), ("3.14", "2.4.6", "2.5.0"), ("3.15", "2.5.3", "2.4.6")):
            selected = [entry for entry in requirements if version in SpecifierSet(entry["python"])]
            assert len(selected) == 1
            allowed = SpecifierSet(selected[0]["version"])
            assert accepted in allowed
            assert rejected not in allowed

    with project.open("rb") as stream:
        extras = tomllib.load(stream)["project"]["optional-dependencies"]
    cpu = [Requirement(value) for value in extras["cpu"]]
    gpu = [Requirement(value) for value in extras["gpu"]]
    for version in ("3.13", "3.14"):
        environment = {"python_version": version, "sys_platform": "linux"}
        assert [str(item.specifier) for item in cpu if item.marker and item.marker.evaluate(environment)] == ["==0.66.0"]
        assert {item.name: str(item.specifier) for item in gpu if item.marker and item.marker.evaluate(environment)} == {
            "numba": "==0.66.0",
            "numba-cuda": "==0.30.4",
        }
    environment = {"python_version": "3.15", "sys_platform": "linux"}
    assert [str(item.specifier) for item in cpu if item.marker and item.marker.evaluate(environment)] == ["==0.68.1"]
    assert not [item for item in gpu if item.marker and item.marker.evaluate(environment)]


def configurations(schema: dict[str, object]) -> Iterator[dict[str, object]]:
    """
    Independently reconstruct a small flat Cartesian corpus for oracle comparison.

    Args:
        schema (dict[str, object]): Flat finite schema.

    Yields:
        dict[str, object]: Complete candidate in the reference factor order.
    """
    space = factor_space(schema)
    for choices in itertools.product(*space.domains):
        result: dict[str, object] = {}
        for choice in choices:
            result.update(choice)
        yield result


def test_native_matches_schema(native_backend: str) -> None:
    """
    Require exact finite-corpus parity across transfers, batches and optional runtimes.

    Args:
        native_backend (str): Required engine under test.

    Returns:
        None: Every supported result agrees with the independent schema oracle.
    """
    schema = schema_fixture()
    original = copy.deepcopy(schema)
    plan = compile_plan(schema, factor_space(schema))
    engine = prepare(plan, native_backend)
    validator = validators.validator_for(schema)(schema)
    expected = tuple(State.TRUE if validator.is_valid(value) else State.FALSE for value in configurations(schema))
    try:
        assert engine.evaluate(()).states == ()
        observed = ()
        for start in range(0, plan.cardinality, 7):
            ids = tuple(range(start, min(start + 7, plan.cardinality)))
            result = engine.evaluate(ids)
            assert result.ids == ids
            observed += result.states
        assert observed == expected
        assert engine.evaluate((0, plan.cardinality - 1, 0)).states == (expected[0], expected[-1], expected[0])
    finally:
        engine.close()
    assert schema == original
    assert compile_plan(schema, factor_space(schema)).encode() == plan.encode()


@pytest.mark.parametrize("threshold", [0, 10000])
def test_exhaustive_plans_batch_without_changing_callbacks(native_backend: str, threshold: int) -> None:
    """
    Consolidate explicit full strength and automatic promotion into consecutive native batches.

    Args:
        native_backend (str): Physical native engine under test.
        threshold (int): Disabled or enabled exhaustive promotion.

    Returns:
        None: Ordered selection, callback prefixes and logical counts match the reference.
    """
    schema = schema_fixture()
    calls: list[dict[str, object]] = []

    def accept(value: dict[str, object]) -> bool:
        """
        Observe accepted candidates and reject one deterministic subset.

        Args:
            value (dict[str, object]): Complete schema-valid candidate.

        Returns:
            bool: Whether to retain this candidate.
        """
        calls.append(value)
        return value.get("name") != "a"

    strength = 3 if threshold == 0 else 1
    expected = plan_interactions(schema, strength, exhaustive_threshold=threshold, accept=accept)
    expected_calls = calls.copy()
    calls.clear()
    actual = plan_interactions(
        schema,
        strength,
        exhaustive_threshold=threshold,
        accept=accept,
        backend=BackendOptions(native_backend, limits=Limits(batch_size=7), verify=True),
    )
    assert list(actual.values) == list(expected.values)
    assert calls == expected_calls
    assert (actual.candidates, actual.interactions) == (expected.candidates, expected.interactions)
    if native_backend == "reference":
        assert actual.backend_report["batches"] == actual.backend_report["physical_cases"] == 0
    else:
        assert actual.backend_report["batches"] == (actual.candidates + 6) // 7
        assert actual.backend_report["physical_cases"] == actual.candidates


def test_explicit_exhaustive_uses_concrete_case_backend(native_backend: str) -> None:
    """
    Keep enumeration order and nested host fallbacks when compiling exhaustive validation.

    Args:
        native_backend (str): Physical native engine under test.

    Returns:
        None: Both enumeration modes return the same concrete values and real native work is recorded.
    """
    schema = schema_fixture()
    expected = list(enumerate_values(schema))
    report: dict[str, object] = {}
    actual = enumerate_values(schema, backend=BackendOptions(native_backend, verify=True), report=report)
    assert list(actual) == expected
    if native_backend == "reference":
        assert report == {}
    else:
        assert report["selected"] == native_backend
        assert int(str(report["physical_cases"])) > 0
        assert report["committed_cases"] == len(expected)


@pytest.mark.parametrize("batch_size", [1, 7, 256])
def test_planner_preserves_stream_and_callbacks(native_backend: str, batch_size: int) -> None:
    """
    Preserve first-valid selection, callback order and logical budgets under prefetch.

    Args:
        native_backend (str): Required compute engine.
        batch_size (int): Different speculative interval boundary.

    Returns:
        None: Results and effectful callback invocations exactly match serial planning.
    """
    schema = schema_fixture()
    calls: list[dict[str, object]] = []

    def accept(value: dict[str, object]) -> bool:
        """
        Retain an effectful ordered callback with a deterministic rejection.

        Args:
            value (dict[str, object]): Schema-valid candidate.

        Returns:
            bool: Whether this complete candidate is accepted.
        """
        calls.append(value)
        return value.get("name") != ""

    expected = plan_interactions(schema, 2, accept=accept, exhaustive_threshold=0)
    expected_calls = calls.copy()
    calls.clear()
    observed = plan_interactions(
        schema,
        2,
        accept=accept,
        exhaustive_threshold=0,
        backend=BackendOptions(native_backend, limits=Limits(batch_size=batch_size), verify=True),
    )
    assert list(observed.values) == list(expected.values)
    assert calls == expected_calls
    assert observed.candidates == expected.candidates
    assert observed.interactions == expected.interactions


@pytest.mark.parametrize("limit", [120, 150])
def test_budget_termination(native_backend: str, limit: int) -> None:
    """
    Compare incomplete planning and callback prefixes under the same logical limit.

    Args:
        native_backend (str): Required engine.
        limit (int): Completion budget near the selected fixture's search size.

    Returns:
        None: Native execution cannot bypass or consume the logical limit early.
    """
    outcomes = []
    for backend in ("reference", native_backend):
        try:
            plan = plan_interactions(schema_fixture(), 2, max_candidates=limit, exhaustive_threshold=0, backend=BackendOptions(backend))
            outcomes.append((list(plan.values), plan.candidates))
        except NonFiniteSchema as exc:
            outcomes.append(str(exc))
    assert outcomes[0] == outcomes[1]


@given(
    st.lists(st.sampled_from([State.FALSE, State.TRUE, State.UNKNOWN]), max_size=8), st.sampled_from([Opcode.AND, Opcode.OR, Opcode.ONE])
)
@settings(max_examples=100, deadline=None)
def test_boolean_unknown_laws(states: list[State], operation: Opcode) -> None:
    """
    Resolve unknowns by every Boolean completion to detect false certainty.

    Args:
        states (list[State]): Known and unknown operands.
        operation (Opcode): Pure Boolean combination.

    Returns:
        None: Every definitive kernel result agrees with all admissible completions.
    """
    nodes = tuple(Node(Opcode.CONSTANT, table=(state,)) for state in states)
    plan = Plan(digest({}), (), (*nodes, Node(operation, tuple(range(len(states))))), len(states))
    engine = prepare(plan, "reference")
    try:
        result = engine.evaluate((0,)).states[0]
    finally:
        engine.close()
    possible = set()
    for values in itertools.product(*[(False, True) if value == State.UNKNOWN else (value == State.TRUE,) for value in states]):
        possible.add(all(values) if operation == Opcode.AND else any(values) if operation == Opcode.OR else sum(values) == 1)
    if result != State.UNKNOWN:
        assert possible == {result == State.TRUE}


def test_plan_integrity_and_bounds() -> None:
    """
    Reject cycles, stale contexts, invalid offsets, overflow and coerced field types.

    Returns:
        None: All malformed plans fail before native buffer access.
    """
    schema = schema_fixture()
    plan = compile_plan(schema, factor_space(schema))
    assert load_plan(plan.encode(), plan.context_digest) == plan
    with pytest.raises(InvalidPlan, match="stale"):
        load_plan(plan.encode(), digest("other chart"))
    bad = json.loads(plan.encode())
    bad["root"] = str(bad["root"])
    with pytest.raises(InvalidPlan):
        load_plan(json.dumps(bad).encode(), plan.context_digest)
    with pytest.raises(InvalidPlan):
        evolve(plan, nodes=(Node(Opcode.NOT, (0,)),), root=0).validate()
    with pytest.raises(InvalidPlan):
        evolve(plan, factors=(Factor(("x",), 0, digest([])),)).validate()
    with pytest.raises(InvalidPlan, match="64-bit"):
        evolve(plan, factors=tuple(Factor((str(i),), 2, digest([])) for i in range(64))).validate()
    engine = prepare(plan, "reference")
    try:
        for ids in ((-1,), (plan.cardinality,), (True,)):
            with pytest.raises(InvalidPlan):
                engine.evaluate(ids)
    finally:
        engine.close()


def test_unsupported_fragments_keep_host_route() -> None:
    """
    Retain unsupported regex, collections and wide integers as explicit unknowns.

    Returns:
        None: Unknown inputs remain in the serial planner's candidate stream.
    """
    schema = schema_fixture()
    schema["allOf"] = [{"properties": {"name": {"pattern": "^a"}}}]
    plan = compile_plan(schema, factor_space(schema))
    assert plan.fallbacks
    engine = prepare(plan, "reference")
    try:
        assert State.UNKNOWN in engine.evaluate(tuple(range(plan.cardinality))).states
    finally:
        engine.close()

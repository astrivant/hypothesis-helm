"""
Check lattice laws, conservative branch transfer and differential agreement with real Helm.
"""

import itertools
import json
import shutil
from pathlib import Path
from textwrap import dedent

import pytest
from hypothesis import given
from hypothesis import strategies as st
from immutables import Map

from hypothesis_helm.charts.model import Chart
from hypothesis_helm.charts.rendering import render
from hypothesis_helm.compiler.asts.conditions import parse_condition
from hypothesis_helm.compiler.asts.lattice import Domain, Scalar, State
from hypothesis_helm.compiler.asts.templates import fold, lower, specialize, walk
from hypothesis_helm.compiler.passes.branches import analyze
from hypothesis_helm.compiler.passes.complexity import _resources, measure
from hypothesis_helm.compiler.passes.pruning import Pruner
from hypothesis_helm.schemas.model import ValuesModel

SCALARS: list[Scalar] = [True, False, "public", "private"]
DOMAINS = st.one_of(st.none(), st.frozensets(st.sampled_from(SCALARS))).map(Domain)
STATES = st.dictionaries(st.sampled_from([("mode",), ("enabled",)]), DOMAINS).map(lambda values: State(Map(values)))


@given(STATES, STATES, STATES)
def test_lattice_laws(a: State, b: State, c: State) -> None:
    """
    Verify merge and intersection obey lattice laws, including unknown and impossible states.

    Args:
        a (State): First generated environment.
        b (State): Second generated environment.
        c (State): Third generated environment.

    Returns:
        None: Joins and meets are associative, commutative, idempotent and satisfy absorption.
    """
    assert a.join(b) == b.join(a)
    assert a.meet(b) == b.meet(a)
    assert a.join(b.join(c)) == a.join(b).join(c)
    assert a.meet(b.meet(c)) == a.meet(b).meet(c)
    assert a.join(a) == a.meet(a) == a
    assert a.join(a.meet(b)) == a.meet(a.join(b)) == a
    assert a.join(State()) == State()
    assert a.meet(State()) == a
    assert a.join(State(reachable=False)) == a
    assert not a.meet(State(reachable=False)).reachable


def test_branch_narrowing_and_join() -> None:
    """
    Remove nested contradictions without leaking one branch's facts into later siblings.

    Returns:
        None: Nested impossible predicates disappear, while later alternatives remain reachable.
    """
    state = State(Map({("mode",): Domain(frozenset({"public", "private", "internal"}))}))
    program = lower(
        dedent("""
        {{ if eq .Values.mode "public" }}
          {{ if eq .Values.mode "private" }}{{ fail "dead" }}{{ end }}
        {{ else }}
          {{ if eq .Values.mode "public" }}{{ fail "also impossible" }}{{ end }}
        {{ end }}
        {{ if eq .Values.mode "private" }}private{{ end }}
    """)
    )
    result = analyze(program, state)
    assert result.state == state
    assert sum(node.kind == "if" for node in walk(result.nodes)) == 2
    assert not any("fail" in node.text for node in walk(result.nodes))
    assert sum(decision["action"] == "keep-false" for decision in result.decisions) == 2
    assert state.fields[("mode",)].values == frozenset({"public", "private", "internal"})


@pytest.mark.parametrize("barrier", ['set .Values "mode" "private"', 'include "helper" .', "tpl .Values.source ."])
def test_opaque_operations_clear_facts(barrier: str) -> None:
    """
    Retain a branch after an operation that could mutate values or execute unknown code.

    Args:
        barrier (str): Unsupported operation between a known state and a predicate.

    Returns:
        None: The old constant cannot justify removing a later branch.
    """
    state = State(Map({("mode",): Domain(frozenset({"public"}))}))
    result = analyze(lower("{{ " + barrier + ' }}{{ if eq .Values.mode "private" }}reachable{{ end }}'), state)
    assert result.decisions[-1]["action"] == "keep-both"
    assert result.state == State()


def test_schema_bounds_require_presence_and_preserve_unknown_types() -> None:
    """
    Avoid treating defaults, optional parents or unsupported truthiness as fixed inputs.

    Returns:
        None: Optional paths stay unknown and incompatible comparisons retain both alternatives.
    """
    model = ValuesModel.from_schema(
        {
            "type": "object",
            "required": ["mode"],
            "properties": {
                "mode": {"type": "string", "enum": ["public", "private"], "default": "public"},
                "optional": {"type": "object", "required": ["flag"], "properties": {"flag": {"const": True}}},
            },
        }
    )
    state = State.from_model(model)
    assert state.fields[("mode",)].values == frozenset({"public", "private"})
    assert ("optional", "flag") not in state.fields
    for expression in (".Values.mode", "eq .Values.mode true", "not .Values.optional.flag"):
        predicate = parse_condition(expression)
        assert predicate is not None
        assert state.assume(predicate, True) == state.assume(predicate, False) == state
    for expression in (
        'eq .Values.mode "pub\\u006cic"',
        "eq .Values.count 1",
        "and .Values.a .Values.b",
        'eq\u00a0.Values.mode "public"',
        "not .Values.enabled\u00a0",
    ):
        assert parse_condition(expression) is None


@pytest.fixture
def lattice_chart(tmp_path: Path) -> Chart:
    """
    Create a finite chart with contradictory branches, a later sibling and an unused field.

    Args:
        tmp_path (Path): Chart directory.

    Returns:
        Chart: Twelve valid inputs spanning string and Boolean predicates.
    """
    (tmp_path / "templates").mkdir()
    (tmp_path / "Chart.yaml").write_text(
        dedent("""
        apiVersion: v2
        name: lattice
        version: 1.0.0
    """)
    )
    (tmp_path / "values.yaml").write_text(
        dedent("""
        mode: public
        enabled: false
        unused: false
    """)
    )
    (tmp_path / "values.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["mode", "enabled", "unused"],
                "properties": {
                    "mode": {"type": "string", "enum": ["public", "private", "internal"]},
                    "enabled": {"type": "boolean"},
                    "unused": {"type": "boolean"},
                },
            }
        )
    )
    (tmp_path / "templates" / "config.yaml").write_text(
        dedent("""
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: example
        data:
          mode: "{{ .Values.mode }}"
          public: "{{ if eq .Values.mode "public" }}yes{{ if ne .Values.mode "public" }}{{ fail "dead" }}{{ end }}{{ else }}no{{ end }}"
          enabled: "{{ if .Values.enabled }}yes{{ if not .Values.enabled }}{{ fail "dead" }}{{ end }}{{ else }}no{{ end }}"
        {{ if eq .Values.mode "private" }}
        extra: {nested: {field: value}}
        {{ end }}
    """)
    )
    return Chart.load(tmp_path)


@pytest.mark.skipif(shutil.which("helm") is None, reason="requires Helm")
def test_lattice_compiler_matches_every_helm_input(lattice_chart: Chart) -> None:
    """
    Compare all finite inputs with real Helm and verify dependencies still affect complexity search.

    Args:
        lattice_chart (Chart): Complete finite native chart.

    Returns:
        None: Transformation preserves every output and identifies the larger private configuration.
    """
    model = ValuesModel.from_schema(lattice_chart.schema)
    compiler = Pruner(lattice_chart.path, lattice_chart.defaults, model)
    assert compiler.disabled is None
    program = compiler.programs["templates/config.yaml"]
    assert not any("fail" in node.text for node in walk(program))
    for mode, enabled, unused in itertools.product(("public", "private", "internal"), (False, True), (False, True)):
        values = {"mode": mode, "enabled": enabled, "unused": unused}
        resources = render(lattice_chart, values, stream=False)
        assert list(_resources(program, values, model)) == resources
        assert specialize(program, values, model).reason is None
        witness = compiler.candidate(values, values, "fixed")
        assert witness is not None
        reused = compiler.lookup(witness, int(unused))
        if unused:
            assert reused == resources
        else:
            assert reused is None
            compiler.remember(witness, 0, resources)
    assert compiler.report()["pruned_candidates"] == 6
    result = measure(lattice_chart)
    assert result["status"] == "compiled-maximum"
    maximizing = result["maximizing_values"]
    assert isinstance(maximizing, dict)
    assert maximizing["mode"] == "private"


def test_live_unsupported_branch_has_no_certificate(lattice_chart: Chart) -> None:
    """
    Preserve reachable opaque calls and reject an exact-equivalence witness for that input.

    Args:
        lattice_chart (Chart): Chart supplying a declared string domain.

    Returns:
        None: Only an established contradictory branch can hide an unsupported action.
    """
    model = ValuesModel.from_schema(lattice_chart.schema)
    result = analyze(fold(lower('{{ if eq .Values.mode "public" }}{{ fail "reachable" }}{{ end }}')), State.from_model(model))
    assert specialize(result.nodes, lattice_chart.defaults, model).reason is not None

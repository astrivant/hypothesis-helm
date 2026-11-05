"""
Verify potential output maxima, explicit uncertainty and mathematical size ceilings.
"""

import json
import shutil
from itertools import product
from pathlib import Path
from textwrap import dedent

import pytest

from hypothesis_helm.charts.inspection.audit import audit
from hypothesis_helm.charts.model import Chart
from hypothesis_helm.charts.testing.rendering import render
from hypothesis_helm.compiler.complexity import maximum_score, output_profile
from hypothesis_helm.compiler.passes.complexity import measure


@pytest.mark.parametrize("nodes", range(8))
def test_bound_is_attained_by_small_trees(nodes: int) -> None:
    """
    Enumerate all increasing parent assignments, independently checking the exact maximum.

    Args:
        nodes (int): Number of non-root nodes to enumerate.

    Returns:
        None: No tree exceeds the bound and at least one attains it.
    """
    scores = []
    for parents in product(*(range(index) for index in range(1, nodes + 1))):
        depths = [0]
        for parent in parents:
            depths.append(depths[parent] + 1)
        levels = depths[1:]
        breadth = max((levels.count(depth) for depth in levels), default=0)
        scores.append(breadth * max(levels, default=0))
    assert max(scores) == maximum_score(nodes)


def _chart(path: Path, *, opaque: bool = False) -> Chart:
    """
    Write a finite chart whose largest output is disabled by default.

    Args:
        path (Path): Destination chart directory.
        opaque (bool): Include an unsupported operation only in the enabled branch.

    Returns:
        Chart: Loaded chart containing a Boolean-controlled extra resource.
    """
    (path / "templates").mkdir()
    (path / "Chart.yaml").write_text("apiVersion: v2\nname: example\nversion: 0.1.0\n")
    (path / "values.yaml").write_text("enabled: false\n")
    (path / "values.schema.json").write_text(
        json.dumps(
            {"type": "object", "additionalProperties": False, "required": ["enabled"], "properties": {"enabled": {"type": "boolean"}}}
        )
    )
    source = dedent(
        """
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: always
        {{ if .Values.enabled }}
        ---
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: extra
        data:
          one: "1"
          two: "2"
        {{ end }}
        """
    )
    if opaque:
        source = source.replace('one: "1"', 'one: {{ printf "%s" "1" }}')
    (path / "templates/example.yaml").write_text(source)
    return Chart.load(path)


def test_audit_maximizes_outputs_across_disabled_branches(tmp_path: Path) -> None:
    """
    Score the largest allowed output instead of the default render or source tree.

    Args:
        tmp_path (Path): Destination for a known finite chart.

    Returns:
        None: Both configurations were examined and enabling the resource attains the maximum.
    """
    chart = _chart(tmp_path)
    report = audit(chart)["complexity"]
    assert isinstance(report, dict)
    assert report["status"] == "compiled-maximum"
    assert report["examined_configurations"] == 2
    assert report["maximizing_values"] == {"enabled": True}
    assert report["maximum_output"] == {"nodes": 13, "breadth": 7, "depth": 3, "score": 21, "size_ceiling": 49}
    assert report["maximum_score"] == 21


@pytest.mark.skipif(shutil.which("helm") is None, reason="Helm is not installed")
def test_compiled_maximum_matches_complete_helm_domain(tmp_path: Path) -> None:
    """
    Independently compare the compiler maximum against every actual Helm output.

    Args:
        tmp_path (Path): Destination for the finite chart.

    Returns:
        None: The same structural maximum is attained by native rendering.
    """
    chart = _chart(tmp_path)
    result = measure(chart)
    scores = [output_profile(render(chart, {"enabled": enabled}, stream=False))["score"] for enabled in (False, True)]
    assert scores[0] < scores[1] == result["maximum_score"]


def test_unknown_branch_never_becomes_an_exact_maximum(tmp_path: Path) -> None:
    """
    Retain supported evidence as a lower bound when another configuration is opaque.

    Args:
        tmp_path (Path): Destination for a chart with an opaque enabled branch.

    Returns:
        None: The default output cannot be mistaken for the chart's potential maximum.
    """
    result = measure(_chart(tmp_path, opaque=True))
    assert result["status"] == "unknown"
    assert result["maximum_score"] is None
    assert result["lower_bound"] == {"nodes": 5, "breadth": 3, "depth": 3, "score": 9, "size_ceiling": 9}
    assert "unsupported expression" in str(result["reason"])


def test_analysis_limit_does_not_truncate_the_allowed_domain(tmp_path: Path) -> None:
    """
    Refuse a domain larger than the analysis ceiling rather than reporting a sampled maximum.

    Args:
        tmp_path (Path): Destination for the finite chart.

    Returns:
        None: No current-state score substitutes for an unknown potential maximum.
    """
    result = measure(_chart(tmp_path), max_cases=1)
    assert result["status"] == "unknown"
    assert result["maximum_score"] is None
    assert result["lower_bound"] is None


def test_tree_profiles_reject_cycles_and_define_empty_output() -> None:
    """
    Give empty output a zero score and refuse infinitely expanded alias trees.

    Returns:
        None: Edge cases retain finite and explicit semantics.
    """
    assert output_profile([])["score"] == 0
    assert maximum_score(10**12) == (10**12 + 1) ** 2 // 4
    with pytest.raises(ValueError, match="nonnegative"):
        maximum_score(-1)
    cyclic: list[object] = []
    cyclic.append(cyclic)
    with pytest.raises(ValueError, match="cyclic"):
        output_profile(cyclic)


@pytest.mark.parametrize("width", [3, 10])
def test_topology_search_avoids_cartesian_enumeration(tmp_path: Path, width: int) -> None:
    """
    Maximize independent gated resources using small local tables and sound branch bounds.

    Args:
        tmp_path (Path): Destination for a chart with one Boolean gate per resource.
        width (int): Number of gates whose full Cartesian space is intentionally larger than the work budget.

    Returns:
        None: The maximum is established while most complete assignments are never evaluated.
    """
    chart = _chart(tmp_path)
    (tmp_path / "templates/example.yaml").unlink()
    names = [f"gate{index}" for index in range(width)]
    schema: dict[str, object] = {
        "type": "object",
        "additionalProperties": False,
        "required": names,
        "properties": {name: {"type": "boolean"} for name in names},
    }
    (tmp_path / "values.schema.json").write_text(json.dumps(schema))
    (tmp_path / "values.yaml").write_text("\n".join(f"{name}: false" for name in names) + "\n")
    for name in names:
        (tmp_path / "templates" / f"{name}.yaml").write_text(
            dedent(
                f"""
                {{{{ if .Values.{name} }}}}
                apiVersion: v1
                kind: ConfigMap
                metadata:
                  name: {name}
                {{{{ end }}}}
                """
            )
        )
    chart = Chart.load(tmp_path)
    result = measure(chart, max_cases=64)
    assert result["status"] == "compiled-maximum"
    assert result["candidate_configurations"] == 2**width
    assert result["maximum_score"] == 9 * width
    assert result["maximizing_values"] == dict.fromkeys(names, True)
    assert result["template_evaluations"] == 2 * width
    assert result["examined_configurations"] == 2
    assert result["pruned_configurations"] == 2**width - 2
    if width == 3 and shutil.which("helm"):
        scores = [
            output_profile(render(chart, dict(zip(names, values, strict=True)), stream=False))["score"]
            for values in product((False, True), repeat=width)
        ]
        assert max(scores) == result["maximum_score"]


def test_shared_gate_does_not_combine_incompatible_output_maxima(tmp_path: Path) -> None:
    """
    Preserve shared conditions when independently largest components cannot coexist.

    Args:
        tmp_path (Path): Chart containing two resources controlled by opposite states of one gate.

    Returns:
        None: The score is attained by one input, rather than a sum of impossible local maxima.
    """
    chart = _chart(tmp_path)
    (tmp_path / "templates/opposite.yaml").write_text(
        dedent(
            """
            {{ if .Values.enabled }}
            {{ else }}
            apiVersion: v1
            kind: ConfigMap
            metadata:
              name: opposite
            data:
              a: "a"
              b: "b"
              c: "c"
              d: "d"
            {{ end }}
            """
        )
    )
    result = measure(chart)
    assert result["status"] == "compiled-maximum"
    assert result["maximum_score"] == 21
    assert result["maximizing_values"] in ({"enabled": False}, {"enabled": True})
    if shutil.which("helm"):
        assert result["maximum_score"] == max(
            output_profile(render(chart, {"enabled": enabled}, stream=False))["score"] for enabled in (False, True)
        )


@pytest.mark.parametrize("lua", [False, True])
def test_component_bound_is_admissible_for_every_partial_assignment(lua: bool) -> None:
    """
    Independently enumerate compatible profiles to check that pruning bounds never underestimate.

    Args:
        lua (bool): Exercise the native kernel or the Python reference.

    Returns:
        None: Partial bounds cover every feasible score and complete assignments have exact bounds.
    """
    from hypothesis_helm.compiler.lua.bounds import BoundEvaluator
    from hypothesis_helm.compiler.passes.complexity import Component, OutputCase, bound

    components = (
        Component((0,), (OutputCase((0,), (), (1, 8)), OutputCase((1,), (), (1, 1, 1, 2)))),
        Component(
            (0, 1),
            (
                OutputCase((0, 0), (), (1, 2, 5)),
                OutputCase((0, 1), (), (1, 3)),
                OutputCase((1, 0), (), (1, 4)),
                OutputCase((1, 1), (), (1, 1, 1, 1, 1)),
            ),
        ),
    )
    evaluator = BoundEvaluator(components, max_memory_bytes=64 * 1024 * 1024) if lua else lambda assignment: bound(components, assignment)
    scores = {}
    for assignment in product(range(2), repeat=2):
        profiles = [
            next(case.levels for case in component.cases if case.choices == tuple(assignment[index] for index in component.factors))
            for component in components
        ]
        depth = max(map(len, profiles))
        levels = [sum(profile[level] if level < len(profile) else 0 for profile in profiles) for level in range(depth)]
        scores[assignment] = max(levels) * depth
    for partial in ({}, {0: 0}, {0: 1}, {1: 0}, {1: 1}):
        feasible = [score for choices, score in scores.items() if all(choices[index] == value for index, value in partial.items())]
        assert evaluator(partial) >= max(feasible)
    for choices, score in scores.items():
        assert evaluator(dict(enumerate(choices))) == score


def test_complexity_cli_accepts_chart_paths(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """
    Exercise typed command arguments and report the same maximum as the audit API.

    Args:
        tmp_path (Path): Destination for the finite chart.
        capsys (pytest.CaptureFixture[str]): Capture the CLI's JSON output.

    Returns:
        None: Chart and mathematical-size modes both emit their documented results.
    """
    from hypothesis_helm.compiler.passes.complexity import main

    _chart(tmp_path)
    assert main(["--chart", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["maximum_score"] == 21
    assert main(["--nodes", "13"]) == 0
    assert json.loads(capsys.readouterr().out) == {"nodes": 13, "size_ceiling": 49}


def test_root_enum_remains_an_atomic_supported_domain(tmp_path: Path) -> None:
    """
    Preserve whole-document constraints instead of inventing independent field choices.

    Args:
        tmp_path (Path): Destination for a chart constrained by a root enum.

    Returns:
        None: Branch-and-bound retains the exhaustive maximum for supported atomic schemas.
    """
    _chart(tmp_path)
    (tmp_path / "values.schema.json").write_text(json.dumps({"type": "object", "enum": [{"enabled": False}, {"enabled": True}]}))
    result = measure(Chart.load(tmp_path))
    assert result["status"] == "compiled-maximum"
    assert result["maximum_score"] == 21
    assert result["maximizing_values"] == {"enabled": True}

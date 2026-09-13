"""
Verify potential output maxima, explicit uncertainty and mathematical size ceilings.
"""

import json
import shutil
from itertools import product
from pathlib import Path
from textwrap import dedent

import pytest

from hypothesis_helm.charts.audit import audit
from hypothesis_helm.charts.model import Chart
from hypothesis_helm.charts.rendering import render
from hypothesis_helm.compiler.complexity import maximum_score, measure, output_profile


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

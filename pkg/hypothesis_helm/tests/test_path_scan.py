"""
Scans schedule unique paths after filtering and retain precise timeout evidence.
"""

import copy
from pathlib import Path
from textwrap import dedent

import pytest
from hypothesis import given, settings

from hypothesis_helm.charts.generate import ValuePath
from hypothesis_helm.charts.paths import check_paths, path_strategy
from hypothesis_helm.charts.runner import Chart


@pytest.fixture
def chart(tmp_path: Path) -> Chart:
    """
    Provide nested non-finite paths with valid supplied defaults.

    Args:
        tmp_path (Path): Isolated chart directory.

    Returns:
        Chart: Original schema and values with top-level and nested fields.
    """
    (tmp_path / "Chart.yaml").write_text(
        dedent("""
        apiVersion: v2
        name: paths
        version: 1.0.0
        """)
    )
    return Chart(
        tmp_path,
        {
            "type": "object",
            "properties": {
                "global": {"type": "object", "properties": {"configMaps": {"type": "string"}, "enabled": {"type": "boolean"}}},
                "service": {"type": "object", "properties": {"port": {"type": "integer"}}},
                "replicas": {"type": "integer"},
            },
        },
        {"global": {"configMaps": "ready", "enabled": True}, "service": {"port": 80}, "replicas": 1},
    )


@pytest.mark.parametrize("strategy", ["random", "linear", "shallow", "deep"])
def test_scan_visits_each_path_once(chart: Chart, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, strategy: str) -> None:
    """
    Visit the entire finite path inventory without mutating its original contract.

    Args:
        chart (Chart): Nested values fixture.
        tmp_path (Path): Artifact root.
        monkeypatch (pytest.MonkeyPatch): Substitute successful property execution.
        strategy (str): Requested traversal order.

    Returns:
        None: Each selected path has exactly one property result and no remaining work.
    """
    original = copy.deepcopy((chart.schema, chart.defaults))
    calls: list[dict[str, object]] = []

    def check(source: Chart, **kwargs: object) -> dict[str, object]:
        """
        Record a property invocation without repeating its already verified baseline.

        Args:
            source (Chart): Original chart under test.
            **kwargs (object): Property scheduling options.

        Returns:
            dict[str, object]: Successful bounded property outcome.
        """
        assert source is chart and kwargs["check_defaults"] is False
        calls.append(kwargs)
        return {"status": "passed", "attempts": 3}

    monkeypatch.setattr("hypothesis_helm.charts.paths.check_chart", check)
    monkeypatch.setattr("hypothesis_helm.charts.paths.render", lambda *args, **kwargs: [{"kind": "ConfigMap"}])
    result = check_paths(
        chart,
        budget=5,
        max_examples=3,
        seed=42,
        helm="helm",
        timeout=1,
        artifacts=tmp_path / "results",
        filtering=True,
        traversal_strategy=strategy,
    )
    traversal = result["traversal"]
    assert isinstance(traversal, dict)
    visited = [tuple(path) for path in traversal["visited_order"]]
    assert len(visited) == len(set(visited)) == len(calls) == 6
    assert traversal["remaining_paths"] == 0 and traversal["path_targets_complete"]
    if strategy in {"shallow", "deep"}:
        assert [len(path) for path in visited] == sorted(map(len, visited), reverse=strategy == "deep")
    assert (chart.schema, chart.defaults) == original
    assert result["coverage_complete"] is False


def test_timeout_retains_unique_seeded_prefix(chart: Chart, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Preserve the visited random prefix and all unvisited work when a property times out.

    Args:
        chart (Chart): Nested values fixture.
        tmp_path (Path): Separate report roots for each seed.
        monkeypatch (pytest.MonkeyPatch): Stop the third property deterministically.

    Returns:
        None: Repeated seeds reproduce the prefix; a changed seed changes its subset.
    """
    monkeypatch.setattr("hypothesis_helm.charts.paths.render", lambda *args, **kwargs: [{"kind": "ConfigMap"}])
    prefixes = []
    calls: list[dict[str, object]] = []
    for run, seed in enumerate((0, 0, 1)):
        calls.clear()

        def check(source: Chart, **kwargs: object) -> dict[str, object]:
            """
            Stop a scheduled property without turning a timeout into a chart failure.

            Args:
                source (Chart): Chart selected by the scheduler.
                **kwargs (object): Property options.

            Returns:
                dict[str, object]: Two successes followed by an incomplete property.
            """
            calls.append(kwargs)
            return {"status": "time-limit" if len(calls) == 3 else "passed", "attempts": 1}

        monkeypatch.setattr("hypothesis_helm.charts.paths.check_chart", check)
        result = check_paths(chart, budget=5, max_examples=1, seed=seed, helm="helm", timeout=1, artifacts=tmp_path / str(run))
        traversal = result["traversal"]
        assert isinstance(traversal, dict)
        visited = [tuple(path) for path in traversal["visited_order"]]
        remaining = [tuple(path) for path in traversal["remaining_order"]]
        assert len(visited) == 3 and len(set(visited + remaining)) == 6
        assert not set(visited).intersection(remaining)
        assert traversal["completed_paths"] == 2 and traversal["incomplete_paths"] == 1
        assert result["status"] == "time-limit" and traversal["path_targets_complete"] is False
        prefixes.append(visited)
    assert prefixes[0] == prefixes[1]
    assert set(prefixes[0]) != set(prefixes[2])


def test_path_candidates_exclude_tabs_in_context(chart: Chart) -> None:
    """
    Generate nested path values through the scan strategy without indentation tabs.

    Args:
        chart (Chart): Original nested configuration.

    Returns:
        None: Each candidate retains sibling defaults and excludes the tab alternative.
    """
    entry = ValuePath(("global", "configMaps"), {"type": "string", "enum": ["\t", "ready"]})

    @settings(max_examples=20, deadline=None, derandomize=True)
    @given(path_strategy(chart, entry, chart.schema))
    def check(values: dict[str, object]) -> None:
        """
        Inspect a generated path configuration before rendering.

        Args:
            values (dict[str, object]): Complete schema-valid candidate.

        Returns:
            None: The useful enum alternative is retained with its original context.
        """
        assert values == chart.defaults

    check()

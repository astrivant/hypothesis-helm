"""
Exercise a shared chart queue with real interpreters, Helm renders and bounded cleanup.
"""

import json
import os
import shutil
import sys
import time
from pathlib import Path
from textwrap import dedent

import pytest

from hypothesis_helm.charts.model import Chart
from hypothesis_helm.charts.paths import check_paths
from hypothesis_helm.cli import argument_parser
from hypothesis_helm.schemas.contracts import mapping, sequence


def fixture_chart(tmp_path: Path) -> Chart:
    """
    Write eight independent non-finite paths that all affect one valid ConfigMap.

    Args:
        tmp_path (Path): Chart directory.

    Returns:
        Chart: A chart suitable for real path workers.
    """
    (tmp_path / "Chart.yaml").write_text(
        dedent("""
        apiVersion: v2
        name: workers
        version: 1.0.0
        """)
    )
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates/config.yaml").write_text(
        dedent("""
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: workers
        data:
        {{- range $key, $value := .Values }}
          {{ $key }}: {{ $value | quote }}
        {{- end }}
        """)
    )
    defaults = {f"field{index}": index for index in range(8)}
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {key: {"type": "integer", "minimum": 0, "maximum": 100} for key in defaults},
    }
    (tmp_path / "values.yaml").write_text(json.dumps(defaults))
    (tmp_path / "values.schema.json").write_text(json.dumps(schema))
    return Chart.load(tmp_path)


def test_workers_share_one_chart_without_duplicate_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Dispatch every path once, including when more workers than paths are requested.

    Args:
        tmp_path (Path): Real Helm chart and output directory.
        monkeypatch (pytest.MonkeyPatch): Expose installed worker entry points.

    Returns:
        None: Separate processes finish ten examples per path and reconcile coverage.
    """
    monkeypatch.setenv("PATH", f"{Path(sys.executable).parent}:{os.environ['PATH']}")
    chart = fixture_chart(tmp_path)
    result = check_paths(
        chart, budget=30, max_examples=10, seed=0, helm="helm", timeout=5, artifacts=tmp_path / "results", jobs=12, filtering=True
    )
    traversal = mapping(result["traversal"])
    phases = [mapping(phase) for phase in sequence(result["phases"])]
    assert result["status"] == "passed"
    assert traversal["completed_paths"] == traversal["selected_paths"] == 8
    assert traversal["remaining_paths"] == traversal["incomplete_paths"] == 0
    assert len({tuple(sequence(phase["path"])) for phase in phases}) == 8
    assert len({phase["worker_pid"] for phase in phases}) > 1
    assert all(phase["attempts"] == 10 for phase in phases)
    assert result["attempts"] == 81
    for phase in phases:
        with pytest.raises(ProcessLookupError):
            os.kill(int(str(phase["worker_pid"])), 0)


def test_deadline_stops_workers_and_helm_children(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    End all active path processes under one budget and preserve their incomplete records.

    Args:
        tmp_path (Path): Shared chart and slow external Helm replacement.
        monkeypatch (pytest.MonkeyPatch): Supply the already verified baseline in the coordinator.

    Returns:
        None: The deadline is shared, queued paths remain unvisited, and descendants are joined.
    """
    monkeypatch.setenv("PATH", f"{Path(sys.executable).parent}:{os.environ['PATH']}")
    chart = fixture_chart(tmp_path)
    slow = tmp_path / "slow-helm"
    slow.write_text(
        dedent(f"""
            #!{sys.executable}
            import os
            import time
            from pathlib import Path
            Path(__file__ + '.' + str(os.getpid())).touch()
            time.sleep(60)
            """).lstrip()
    )
    slow.chmod(0o755)
    monkeypatch.setattr("hypothesis_helm.charts.paths.render", lambda *args, **kwargs: [{"kind": "ConfigMap"}])
    started = time.monotonic()
    result = check_paths(
        chart, budget=4, max_examples=10, seed=0, helm=str(slow), timeout=60, artifacts=tmp_path / "results", jobs=3, filtering=True
    )
    assert time.monotonic() - started < 15
    traversal = mapping(result["traversal"])
    assert result["status"] == "time-limit"
    assert traversal["visited_paths"] == traversal["incomplete_paths"] == 3
    assert traversal["remaining_paths"] == 5
    assert traversal["completed_paths"] == 0
    children = list(tmp_path.glob("slow-helm.*"))
    assert children
    for marker in children:
        with pytest.raises(ProcessLookupError):
            os.kill(int(marker.suffix[1:]), 0)
    for phase in sequence(result["phases"]):
        with pytest.raises(ProcessLookupError):
            os.kill(int(str(mapping(phase)["worker_pid"])), 0)


def test_repository_options_accept_path_workers() -> None:
    """
    Expose ten examples and a fixed worker count for local and remote repository tests.

    Returns:
        None: Both entry points accept the same per-chart worker configuration.
    """
    assert shutil.which("helm")
    for command, source in [("test", "."), ("scan", "https://example.org/charts.git")]:
        args = argument_parser().parse_args([command, source, "--jobs", "6"])
        assert args.jobs == 6 and args.max_examples == 10


def test_empty_chart_queue_starts_no_workers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Preserve the empty-work base case when a chart has no selected value paths.

    Args:
        tmp_path (Path): Empty values fixture and report directory.
        monkeypatch (pytest.MonkeyPatch): Supply a valid baseline without external rendering.

    Returns:
        None: The chart reports zero workers and no invented path work.
    """
    monkeypatch.setenv("PATH", f"{Path(sys.executable).parent}:{os.environ['PATH']}")
    chart = fixture_chart(tmp_path)
    chart.defaults = {}
    chart.schema = {"type": "object", "additionalProperties": False, "properties": {}}
    (chart.path / "templates/config.yaml").write_text("")
    monkeypatch.setattr("hypothesis_helm.charts.paths.render", lambda *args, **kwargs: [{"kind": "ConfigMap"}])
    result = check_paths(
        chart, budget=5, max_examples=10, seed=0, helm="helm", timeout=1, artifacts=tmp_path / "results", jobs=6, filtering=True
    )
    assert result["workers"] == 0 and result["status"] == "passed"
    assert mapping(result["traversal"])["visited_paths"] == 0
    assert result["attempts"] == 1


def test_fail_fast_stops_claiming_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Stop the shared queue when a worker reports a failure, retaining the failing input.

    Args:
        tmp_path (Path): Chart with a failure hidden by defaults.
        monkeypatch (pytest.MonkeyPatch): Make the installed worker executable discoverable.

    Returns:
        None: The coordinator keeps the failure and leaves the rest of the queue unstarted.
    """
    monkeypatch.setenv("PATH", f"{Path(sys.executable).parent}:{os.environ['PATH']}")
    chart = fixture_chart(tmp_path)
    template = chart.path / "templates/config.yaml"
    template.write_text(
        template.read_text()
        + dedent("""
        {{- range $key, $value := .Values }}
        {{- if ne (int $value) (int (trimPrefix "field" $key)) }}
        {{- fail "changed input rejected" }}
        {{- end }}
        {{- end }}
        """)
    )
    result = check_paths(
        chart,
        budget=30,
        max_examples=10,
        seed=0,
        helm="helm",
        timeout=5,
        artifacts=tmp_path / "results",
        jobs=2,
        filtering=True,
        fail_fast=True,
    )
    assert result["status"] == "failed"
    assert mapping(result["traversal"])["remaining_paths"]
    assert any(mapping(phase)["status"] == "failed" for phase in sequence(result["phases"]))
    for phase in sequence(result["phases"]):
        with pytest.raises(ProcessLookupError):
            os.kill(int(str(mapping(phase)["worker_pid"])), 0)

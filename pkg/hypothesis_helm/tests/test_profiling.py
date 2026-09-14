"""
Verify call-context conservation, failure cleanup, and profiling in native benchmark workers.
"""

import json
import os
import shutil
import sys
import time
from pathlib import Path
from unittest.mock import Mock

import pytest

from hypothesis_helm.benchmarking.charts.generator import generate
from hypothesis_helm.benchmarking.execution.profiling import PROFILE_DIRECTORY, StackProfiler, capture
from hypothesis_helm.benchmarking.execution.runner import measure
from hypothesis_helm.benchmarking.reporting.flamegraph import layout, merge, render_profiles
from hypothesis_helm.schemas.contracts import mapping, sequence


def test_capture_preserves_distinct_callers_and_recursion(tmp_path: Path) -> None:
    """
    Retain true calling contexts and conserve measured time through flame-graph layout.

    Args:
        tmp_path (Path): Raw profile output directory.

    Returns:
        None: Shared callees remain distinct by caller and recursive frames remain nested.
    """

    def leaf(depth: int) -> None:
        if depth:
            leaf(depth - 1)
        else:
            time.sleep(0.002)

    def left() -> None:
        leaf(1)

    def right() -> None:
        leaf(0)

    def entry() -> int:
        left()
        right()
        return 42

    assert capture(entry, tmp_path, "coordinator") == 42
    assert sys.getprofile() is None
    profile = mapping(json.loads(next(tmp_path.glob("coordinator-*.json")).read_text()))
    frames = merge([profile])
    callees = [frame for frame in frames if frame.label.endswith(".leaf)")]
    assert len(callees) == 3
    assert any(frames[frame.parent].label.endswith(".leaf)") for frame in callees)
    parents = {frames[frame.parent].label.rsplit(".", 1)[-1] for frame in callees}
    assert {"left)", "right)", "leaf)"} == parents
    positions = {index: (left, width, depth) for index, left, width, depth in layout(frames)}
    assert positions[0][1] == pytest.approx(float(str(profile["captured_seconds"])))
    assert positions[0][1] >= 0.004
    for parent in range(len(frames)):
        children = [index for index, frame in enumerate(frames) if frame.parent == parent]
        assert positions[parent][1] == pytest.approx(frames[parent].self_seconds + sum(positions[index][1] for index in children))
        previous_right = positions[parent][0]
        for index in sorted(children, key=lambda index: positions[index][0]):
            offset, width, depth = positions[index]
            assert offset >= previous_right - 1e-9
            assert offset + width <= sum(positions[parent][:2]) + 1e-9
            assert depth == positions[parent][2] + 1
            previous_right = offset + width


def test_capture_failure_and_limits(tmp_path: Path) -> None:
    """
    Save raised entries and charge bounded-tree overflow to retained ancestors.

    Args:
        tmp_path (Path): Failed-entry output directory.

    Returns:
        None: Exceptions propagate, hooks are removed, and limits do not discard time.
    """

    def fail() -> None:
        raise ValueError("original failure")

    with pytest.raises(ValueError, match="original failure"):
        capture(fail, tmp_path, "worker")
    assert sys.getprofile() is None
    profile = mapping(json.loads(next(tmp_path.glob("worker-*.json")).read_text()))
    assert profile["status"] == "raised"
    assert not list(tmp_path.glob("*.tmp"))
    ticks = iter([0.0, 1.0, 2.0, 3.0])
    boundary = sys._getframe().f_back
    assert boundary is not None
    profiler = StackProfiler(boundary, timer=lambda: next(ticks), max_nodes=1)
    profiler.event(sys._getframe(), "call", None)
    document = profiler.finish()
    assert len(sequence(document["frames"])) == 1
    assert document["truncated_events"] == 1
    assert document["captured_seconds"] == 2.0
    assert document["elapsed_seconds"] == 3.0


@pytest.mark.integration
@pytest.mark.skipif(shutil.which("helm") is None, reason="requires real Helm")
def test_profiles_are_captured_in_multiple_worker_processes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Profile two spawned renderer workers and merge their time without coordinator waits.

    Args:
        tmp_path (Path): Generated chart, captures, and plot directories.
        monkeypatch (pytest.MonkeyPatch): Enable profiling only for this benchmark invocation.

    Returns:
        None: Worker identities, assigned inputs, and aggregate figure widths agree.
    """
    chart = tmp_path / "chart"
    generate(chart, input_complexity=4, mean_value=0, stddev=1, output_bins=4)
    profiles = tmp_path / "profiles"
    monkeypatch.setenv(PROFILE_DIRECTORY, str(profiles))
    result = measure(chart, 4, 2, True, seed=0, multiplicity=1, time_limit=30, helm="helm", shard=None)
    assert result["status"] == "passed"
    assert result["completed"] == 4
    documents = [mapping(json.loads(path.read_text())) for path in profiles.glob("worker-*.json")]
    pids = {document["pid"] for document in documents}
    assert len(documents) == len(pids) == 2
    assert os.getpid() not in pids
    assert sum(int(str(mapping(document["metadata"])["assigned"])) for document in documents) == 4
    capture(lambda: time.sleep(0.002), profiles, "coordinator")
    report = render_profiles(profiles, tmp_path / "plots")
    assert report["worker_processes"] == 2
    figures = [mapping(item) for item in sequence(report["figures"])]
    combined = next(item for item in figures if item["name"] == "workers-combined")
    assert float(str(combined["captured_seconds"])) == pytest.approx(
        sum(float(str(document["captured_seconds"])) for document in documents)
    )
    for figure in figures:
        assert (tmp_path / "plots" / str(figure["png"])).read_bytes().startswith(b"\x89PNG")
        assert "<svg" in (tmp_path / "plots" / str(figure["svg"])).read_text()


def test_invalid_profile_parent_is_rejected() -> None:
    """
    Reject cyclic or forward references instead of drawing fabricated call stacks.

    Returns:
        None: A malformed frame tree produces an actionable error.
    """
    with pytest.raises(ValueError, match="follow their parents"):
        merge([{"format": "hypothesis-helm-profile-v1", "frames": [{"label": "root", "parent": 0, "self_seconds": 1, "calls": 1}]}])


def test_lost_hook_marks_partial_capture(tmp_path: Path) -> None:
    """
    Avoid attributing an unobserved tail to the last recorded function.

    Args:
        tmp_path (Path): Interrupted profile destination.

    Returns:
        None: Losing the hook makes capture incompleteness explicit.
    """

    def stop_hook() -> None:
        sys.setprofile(None)
        time.sleep(0.01)

    capture(stop_hook, tmp_path, "worker")
    profile = mapping(json.loads(next(tmp_path.glob("worker-*.json")).read_text()))
    assert profile["capture_complete"] is False
    assert float(str(profile["elapsed_seconds"])) - float(str(profile["captured_seconds"])) >= 0.01


def test_ci_process_id_collisions_stay_separate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Keep captures from different machines distinct when their operating-system PIDs match.

    Args:
        tmp_path (Path): Combined CI artifact directory.
        monkeypatch (pytest.MonkeyPatch): Avoid redrawing figures while checking process ownership.

    Returns:
        None: Two worker identities yield separate views plus one combined view.
    """
    for identity in ("first-machine", "second-machine"):
        document = {
            "format": "hypothesis-helm-profile-v1",
            "role": "worker",
            "pid": 42,
            "process_id": identity,
            "truncated_events": 0,
            "capture_complete": True,
            "frames": [{"label": "profiled entry", "parent": -1, "self_seconds": 1.0, "calls": 1}],
        }
        (tmp_path / f"worker-42-{identity}.json").write_text(json.dumps(document))
    monkeypatch.setattr("hypothesis_helm.benchmarking.reporting.flamegraph.plot", Mock(return_value=1.0))
    result = render_profiles(tmp_path, tmp_path / "plots")
    assert result["worker_processes"] == 2
    figures = [mapping(item) for item in sequence(result["figures"])]
    assert len(figures) == 3
    assert len({str(item["png"]) for item in figures}) == 3

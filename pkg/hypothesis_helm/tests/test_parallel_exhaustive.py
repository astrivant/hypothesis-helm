"""
Verify bounded exhaustive rendering, deterministic evidence and complete process cleanup.
"""

import json
import os
import sys
import threading
import time
from pathlib import Path

import pytest

from hypothesis_helm.benchmarking.charts.generator import generate
from hypothesis_helm.charts.exhaustive import ExhaustiveRenders
from hypothesis_helm.charts.model import Chart
from hypothesis_helm.charts.rendering import RenderFailure
from hypothesis_helm.charts.runner import check_chart
from hypothesis_helm.execution.processes import Processes
from hypothesis_helm.schemas.replay import Replay


def scheduler(chart: Chart, values: list[dict[str, object]], jobs: int = 3) -> ExhaustiveRenders:
    """
    Construct a bounded test scheduler with a generous shared deadline.

    Args:
        chart (Chart): Generated local chart.
        values (list[dict[str, object]]): Ordered input cases.
        jobs (int): Concurrent render ceiling.

    Returns:
        ExhaustiveRenders: Scheduler with no work started before its context is entered.
    """
    return ExhaustiveRenders(
        chart, values, jobs, time.perf_counter() + 30, helm="helm", timeout=30, release="test", namespace="default", kube_version=None
    )


def test_parallel_matches_serial_and_validates_on_coordinator(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Keep finite coverage and hash accounting identical while actual Helm invocations overlap.

    Args:
        tmp_path (Path): Real finite Helm chart.
        monkeypatch (pytest.MonkeyPatch): Barrier proving three concurrently active workers.

    Returns:
        None: Parallelism preserves validated outputs and leaves shared validation on the main thread.
    """
    from hypothesis_helm.charts import exhaustive, rendering

    generate(tmp_path, input_complexity=3, output_bins=4)
    chart = Chart.load(tmp_path)
    serial = check_chart(chart, exhaustive=True, jobs=1)
    original = rendering.render_output
    barrier = threading.Barrier(3, timeout=10)
    arrived = 0
    lock = threading.Lock()

    def overlapping(chart: Chart, values: dict[str, object], **kwargs: object) -> str:
        """
        Require the first three pending renders to be running at the same time.

        Args:
            chart (Chart): Prepared chart.
            values (dict[str, object]): Generated input.
            **kwargs (object): Scheduler-owned Helm execution options.

        Returns:
            str: Real Helm output from the bounded worker.
        """
        nonlocal arrived
        with lock:
            first = arrived < 3
            arrived += 1
        if first:
            barrier.wait()
        return original(
            chart,
            values,
            processes=kwargs["processes"] if isinstance(kwargs["processes"], Processes) else None,
        )

    def validate_on_main(manifests: str, timeout: float) -> None:
        """
        Assert that downstream validation never runs on a prefetch thread.

        Args:
            manifests (str): Raw Helm output.
            timeout (float): Remaining validation ceiling.

        Returns:
            None: Coordinator ownership is established.
        """
        assert threading.current_thread() is threading.main_thread()

    monkeypatch.setattr(exhaustive, "render_output", overlapping)
    monkeypatch.setattr(rendering, "validate", validate_on_main)
    parallel = check_chart(chart, exhaustive=True, jobs=3)
    assert parallel["status"] == serial["status"] == "passed"
    assert parallel["coverage_complete"] is serial["coverage_complete"] is True
    assert parallel["attempts"] == serial["attempts"]
    assert parallel["render_hashes"] == serial["render_hashes"]
    evidence = parallel["parallel_execution"]
    assert isinstance(evidence, dict)
    assert evidence["workers"] == 3 and evidence["unverified_scheduled_renders"] == 0


def test_prefetch_is_bounded_and_preserves_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Construct only a worker-sized window even when the replayable space is enormous.

    Args:
        tmp_path (Path): Small chart used as scheduler context.
        monkeypatch (pytest.MonkeyPatch): Deterministic worker results without external processes.

    Returns:
        None: The first five results retain their input order and only seven values are constructed.
    """
    generate(tmp_path, input_complexity=1)
    created: list[int] = []

    def value(index: int) -> dict[str, object]:
        """
        Record exactly which replay indices were materialized.

        Args:
            index (int): Requested input index.

        Returns:
            dict[str, object]: Fresh input dictionary.
        """
        created.append(index)
        return {"index": index}

    monkeypatch.setattr("hypothesis_helm.charts.exhaustive.render_output", lambda chart, values, **kwargs: str(values["index"]))
    pool = scheduler(Chart.load(tmp_path), [])
    pool.values = Replay(10**9, value)
    pool.workers = 3
    with pool:
        for index, (values, future) in enumerate(pool):
            assert future.result() == str(index) and values["index"] == index
            if index == 4:
                break
    assert created == list(range(7))
    with scheduler(Chart.load(tmp_path), []) as empty:
        assert list(empty) == [] and empty.pool is None


def test_failure_cleans_up_other_process_trees(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Stop siblings and their descendants when one prefetched render fails.

    Args:
        tmp_path (Path): Chart and child-process ownership records.
        monkeypatch (pytest.MonkeyPatch): Workers that launch long-lived process trees.

    Returns:
        None: All recorded child and grandchild processes have been joined or terminated before returning.
    """
    generate(tmp_path / "chart", input_complexity=1)
    markers = [tmp_path / f"child-{index}.json" for index in (1, 2)]

    def run(chart: Chart, values: dict[str, object], **kwargs: object) -> str:
        """
        Fail the first input once both sibling process trees exist.

        Args:
            chart (Chart): Generated chart.
            values (dict[str, object]): Ordered scheduler input.
            **kwargs (object): Per-render process ownership.

        Returns:
            str: Unused output from a sibling stopped during cancellation.
        """
        index = int(str(values["index"]))
        if index == 0:
            deadline = time.monotonic() + 10
            while not all(path.exists() for path in markers):
                assert time.monotonic() < deadline
                time.sleep(0.01)
            raise RenderFailure("first input failed")
        owner = kwargs["processes"]
        assert isinstance(owner, Processes)
        code = (
            "import subprocess,sys,time,os,json; from pathlib import Path; "
            "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)']); "
            "Path(sys.argv[1]).write_text(json.dumps([os.getpid(),child.pid])); time.sleep(30)"
        )
        return owner.run([sys.executable, "-c", code, str(markers[index - 1])], capture_output=True, timeout=30).stdout

    monkeypatch.setattr("hypothesis_helm.charts.exhaustive.render_output", run)
    pool = scheduler(Chart.load(tmp_path / "chart"), [{"index": index} for index in range(3)])
    with pytest.raises(RenderFailure, match="first input failed"), pool:
        for _, future in pool:
            future.result(timeout=15)
    for marker in markers:
        for pid in json.loads(marker.read_text()):
            with pytest.raises(ProcessLookupError):
                os.kill(pid, 0)
    assert not pool.owners
    assert not any(thread.name.startswith("exhaustive-helm") for thread in threading.enumerate())


def test_parallel_timeout_is_incomplete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Do not count prefetched but unverified outputs as completed coverage after the shared deadline.

    Args:
        tmp_path (Path): Finite chart.
        monkeypatch (pytest.MonkeyPatch): Slow workers bound to owned child processes.

    Returns:
        None: The timeout preserves remaining work and joins every worker.
    """
    generate(tmp_path, input_complexity=4)

    def slow(chart: Chart, values: dict[str, object], **kwargs: object) -> str:
        """
        Keep Helm work outstanding until the coordinator reaches its deadline.

        Args:
            chart (Chart): Prepared chart.
            values (dict[str, object]): Input values.
            **kwargs (object): Scheduler-owned subprocess manager.

        Returns:
            str: Output after the process is stopped by scheduler cleanup.
        """
        owner = kwargs["processes"]
        assert isinstance(owner, Processes)
        return owner.run([sys.executable, "-c", "import time;time.sleep(30)"], capture_output=True, timeout=30).stdout

    monkeypatch.setattr("hypothesis_helm.charts.exhaustive.render_output", slow)
    report = check_chart(Chart.load(tmp_path), exhaustive=True, jobs=3, time_limit=0.3)
    assert report["status"] == "time-limit" and report["coverage_complete"] is False
    evidence = report["parallel_execution"]
    assert isinstance(evidence, dict) and evidence["unverified_scheduled_renders"] > 0
    assert not any(thread.name.startswith("exhaustive-helm") for thread in threading.enumerate())


@pytest.mark.parametrize("mode", ["--filter", "--exhaustive"])
def test_cli_stream_remains_json_lines(tmp_path: Path, capfd: pytest.CaptureFixture[str], mode: str) -> None:
    """
    Keep parallel output suitable for a per-resource downstream validator pipeline.

    Args:
        tmp_path (Path): Finite chart and optional generated-suite workspace.
        capfd (pytest.CaptureFixture[str]): Capture stdout separately from diagnostics.
        mode (str): Existing filtering or new parallel exhaustive execution.

    Returns:
        None: Stdout contains complete JSON manifests only, while the report remains on stderr.
    """
    from hypothesis_helm.cli import main

    generate(tmp_path / "chart", input_complexity=4, output_bins=4)
    jobs = "8" if mode == "--exhaustive" else "1"
    assert main(["test", str(tmp_path / "chart"), mode, "--jobs", jobs, "--shard", "none", "--output", "json"]) == 0
    output = capfd.readouterr()
    resources = [json.loads(line) for line in output.out.splitlines()]
    assert resources and all(resource["kind"] == "ConfigMap" for resource in resources)
    assert '"status": "passed"' in output.err
    if mode == "--exhaustive":
        assert '"workers": 8' in output.err

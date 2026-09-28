"""
Exercise a shared chart queue with real interpreters, Helm renders and bounded cleanup.
"""

import json
import os
import shutil
import signal
import sys
import time
from collections.abc import Iterable
from concurrent.futures import Future, wait
from pathlib import Path
from textwrap import dedent

import pytest

from hypothesis_helm.charts.model import Chart
from hypothesis_helm.charts.testing.paths import check_paths
from hypothesis_helm.cli import argument_parser
from hypothesis_helm.environment import refresh_env
from hypothesis_helm.exceptions.execution import TimeLimitReached
from hypothesis_helm.execution.planning.partition import digest
from hypothesis_helm.execution.workers.path_queue import main as worker_main
from hypothesis_helm.integrations.sharding import Shard
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
    # Worker evidence changes while Helm loads this fixture; it is not chart input.
    (tmp_path / ".helmignore").write_text("results/\n")
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
    refresh_env()
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


@pytest.mark.parametrize("jobs", [1, 3])
def test_missing_chart_stops_queue_without_counterexamples(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, jobs: int) -> None:
    """
    Stop serial and parallel paths when the prepared source vanishes during a render.

    Args:
        tmp_path (Path): Chart, fake Helm executable and result records.
        monkeypatch (pytest.MonkeyPatch): Supply the verified baseline and worker executable path.
        jobs (int): Serial or shared-queue execution.

    Returns:
        None: Lost input is an execution error, no shrinking occurs, and every owned worker exits.
    """
    monkeypatch.setenv("PATH", f"{Path(sys.executable).parent}:{os.environ['PATH']}")
    refresh_env()
    chart = fixture_chart(tmp_path)
    binary = tmp_path / "disappearing-helm"
    binary.write_text(
        dedent(f"""
        #!{sys.executable}
        import os
        import sys
        from pathlib import Path
        source = Path(sys.argv[3])
        (source / ("invocation-" + str(os.getpid()))).touch()
        (source / "Chart.yaml").unlink(missing_ok=True)
        sys.stderr.write("Error: unable to detect chart: Chart.yaml: no such file or directory")
        sys.exit(1)
        """).lstrip()
    )
    binary.chmod(0o755)
    monkeypatch.setattr("hypothesis_helm.charts.testing.paths.render", lambda *args, **kwargs: [{"kind": "ConfigMap"}])
    started = time.monotonic()
    result = check_paths(
        chart, budget=30, max_examples=10, seed=0, helm=str(binary), timeout=10, artifacts=tmp_path / "results", jobs=jobs, filtering=False
    )
    assert time.monotonic() - started < 20
    assert result["status"] == "error"
    assert result["error_kind"] == "execution"
    assert "Chart source unavailable" in str(result["error"])
    assert 1 <= len(list(tmp_path.glob("invocation-*"))) <= jobs
    assert mapping(result["traversal"])["completed_paths"] == 0
    assert not list((tmp_path / "results").rglob("observed-failure.json"))
    for phase in sequence(result["phases"]):
        item = mapping(phase)
        assert not item.get("code")
        if "worker_pid" in item:
            with pytest.raises(ProcessLookupError):
                os.kill(int(str(item["worker_pid"])), 0)


@pytest.mark.parametrize("claimed_status", [None, "cancelled", "passed"])
@pytest.mark.parametrize("shard", [None, Shard(1, 2)])
def test_queue_error_preserves_path_accounting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, claimed_status: str | None, shard: Shard | None
) -> None:
    """
    Preserve a queue-wide error without treating worker startup as a visited values path.

    Args:
        tmp_path (Path): Chart and saved traversal report.
        monkeypatch (pytest.MonkeyPatch): Return deterministic worker outcomes at the queue boundary.
        claimed_status (str | None): One recovered path's outcome, or no claims before worker startup fails.
        shard (Shard | None): Optional CI partition whose ownership evidence must remain valid.

    Returns:
        None: Diagnostics survive alongside accurate visited, completed and remaining path counts.
    """
    chart = fixture_chart(tmp_path)
    monkeypatch.setattr("hypothesis_helm.charts.testing.paths.render", lambda *args, **kwargs: [{"kind": "ConfigMap"}])
    planned: list[object] = []
    error = "Chart source unavailable: prepared source was removed"

    def failed_queue(context: dict[str, object], directory: Path, workers: int) -> list[dict[str, object]]:
        """
        Reproduce source loss before or after a claim independently of worker timing.

        Args:
            context (dict[str, object]): Ordered paths owned by this scan instance.
            directory (Path): Reserved worker queue directory.
            workers (int): Requested parallel workers.

        Returns:
            list[dict[str, object]]: Any claimed path followed by a pathless execution diagnostic.
        """
        planned.extend(mapping(item)["path"] for item in sequence(context["paths"]))
        assert planned
        records: list[dict[str, object]] = []
        if claimed_status is not None:
            records.append(
                {
                    "kind": "value-path",
                    "phase": "claimed path",
                    "path": planned[0],
                    "status": claimed_status,
                    "attempts": int(claimed_status == "passed"),
                }
            )
        records.append(
            {
                "kind": "execution",
                "phase": "execution",
                "status": "error",
                "error_kind": "execution",
                "failure_type": "ChartUnavailable",
                "error": error,
                "attempts": 0,
            }
        )
        return records

    monkeypatch.setattr("hypothesis_helm.execution.workers.path_queue.execute", failed_queue)
    result = check_paths(
        chart,
        budget=30,
        max_examples=10,
        seed=0,
        helm="helm",
        timeout=5,
        artifacts=tmp_path / "results",
        jobs=3,
        filtering=False,
        shard=shard,
    )
    visited = int(claimed_status is not None)
    completed = int(claimed_status == "passed")
    assert result["status"] == "error" and result["error_kind"] == "execution"
    assert result["error"] == error and result["coverage_complete"] is False
    assert mapping(result["baseline"])["status"] == "passed"
    assert result["attempts"] == 1 + completed
    traversal = mapping(result["traversal"])
    assert traversal["selected_paths"] == len(planned)
    assert traversal["visited_paths"] == visited
    assert traversal["completed_paths"] == completed
    assert traversal["incomplete_paths"] == visited - completed
    assert traversal["remaining_paths"] == len(planned) - visited
    assert traversal["visited_order"] == planned[:visited]
    assert traversal["remaining_order"] == planned[visited:]
    assert traversal["path_targets_complete"] is False
    phases = sequence(result["phases"])
    assert len(phases) == visited + 1
    assert mapping(phases[-1])["error"] == error and "path" not in mapping(phases[-1])
    assert not list((tmp_path / "results").rglob("observed-failure.json"))
    if shard is not None:
        partition = mapping(result["work_partition"])
        assert partition["visited"] == [digest(path) for path in planned[:visited]]
        assert partition["completed"] == [digest(path) for path in planned[:completed]]
        assert partition["complete"] is False
    saved = mapping(json.loads((tmp_path / "results/report.json").read_text()))
    assert saved["status"] == "error" and saved["traversal"] == traversal


@pytest.mark.parametrize("stop_signal", [signal.SIGALRM, signal.SIGINT, signal.SIGTERM])
def test_deadline_stops_workers_and_helm_children(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stop_signal: int) -> None:
    """
    End all active path processes under one budget and preserve their incomplete records.

    Args:
        tmp_path (Path): Shared chart and slow external Helm replacement.
        monkeypatch (pytest.MonkeyPatch): Supply a verified baseline and expire the timer after every child starts.
        stop_signal (int): Deadline, interactive interruption or CI termination signal.

    Returns:
        None: The deadline is shared, queued paths remain unvisited, and descendants are joined.
    """
    monkeypatch.setenv("PATH", f"{Path(sys.executable).parent}:{os.environ['PATH']}")
    refresh_env()
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
    monkeypatch.setattr("hypothesis_helm.charts.testing.paths.render", lambda *args, **kwargs: [{"kind": "ConfigMap"}])
    expired_at: float | None = None

    def expire_after_children_start(
        futures: Iterable[Future[int]], timeout: float | None = None
    ) -> tuple[set[Future[int]], set[Future[int]]]:
        """
        Deliver the real deadline signal after all three slow Helm children exist.

        Args:
            futures (Iterable[Future[int]]): Workers being awaited by the queue.
            timeout (float | None): Original polling or cleanup wait.

        Returns:
            tuple[set[Future[int]], set[Future[int]]]: Completed and pending futures unless the deadline interrupts polling.
        """
        nonlocal expired_at
        result = wait(futures, timeout=timeout)
        if expired_at is None and len(list(tmp_path.glob("slow-helm.*"))) == 3:
            expired_at = time.monotonic()
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.raise_signal(stop_signal)
        return result

    monkeypatch.setattr("hypothesis_helm.execution.workers.path_queue.wait", expire_after_children_start)
    # Startup can exceed four seconds during parallel suite execution. The budget is
    # a startup watchdog; the handshake above triggers expiry at the state under test.
    result = check_paths(
        chart, budget=60, max_examples=10, seed=0, helm=str(slow), timeout=60, artifacts=tmp_path / "results", jobs=3, filtering=True
    )
    assert expired_at is not None, "Workers never reached the cleanup scenario before the startup watchdog expired"
    assert time.monotonic() - expired_at < 15
    traversal = mapping(result["traversal"])
    assert result["status"] == ("time-limit" if stop_signal == signal.SIGALRM else "interrupted")
    assert traversal["visited_paths"] == traversal["incomplete_paths"] == 3
    assert traversal["remaining_paths"] == 5
    assert traversal["completed_paths"] == 0
    children = list(tmp_path.glob("slow-helm.*"))
    assert len(children) == 3
    for marker in children:
        with pytest.raises(ProcessLookupError):
            os.kill(int(marker.suffix[1:]), 0)
    for phase in sequence(result["phases"]):
        with pytest.raises(ProcessLookupError):
            os.kill(int(str(mapping(phase)["worker_pid"])), 0)
    for log in (tmp_path / "results").rglob("worker-*.log"):
        assert "Traceback (most recent call last)" not in log.read_text()


@pytest.mark.parametrize("stop_signal", [signal.SIGINT, signal.SIGTERM])
@pytest.mark.parametrize("coordinated", [False, True])
def test_worker_interrupt_distinguishes_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stop_signal: int, coordinated: bool
) -> None:
    """
    Handle signals during worker preparation without reporting shutdown as a chart failure.

    Args:
        tmp_path (Path): Internal queue and cancellation markers.
        monkeypatch (pytest.MonkeyPatch): Signal the worker while preparing chart analysis.
        stop_signal (int): Interactive or CI termination signal.
        coordinated (bool): Whether the coordinator already requested cleanup.

    Returns:
        None: Only an independent interrupt marks the entire queue as interrupted.
    """
    (tmp_path / "context.json").write_text(json.dumps({"deadline": time.monotonic() + 30}))
    if coordinated:
        (tmp_path / "stop").touch()

    def interrupt(directory: Path, context: dict[str, object]) -> int:
        """
        Signal startup before the inner path loop installs any handlers.

        Args:
            directory (Path): Shared worker queue.
            context (dict[str, object]): Prepared chart data.

        Returns:
            int: Unreachable when cancellation unwinds correctly.
        """
        signal.raise_signal(stop_signal)
        pytest.fail("Worker ignored cancellation")

    monkeypatch.setattr("hypothesis_helm.execution.workers.path_queue._run_queue", interrupt)
    assert worker_main([str(tmp_path)]) == (0 if coordinated else 130)
    assert (tmp_path / "stop").exists()
    assert (tmp_path / "interrupted").exists() is not coordinated


def test_worker_preparation_obeys_shared_deadline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Bound worker preparation before a path is claimed without a spurious interruption.

    Args:
        tmp_path (Path): Queue with the chart's absolute deadline.
        monkeypatch (pytest.MonkeyPatch): Replace preparation with a blocking operation.

    Returns:
        None: The worker exits normally at the deadline with no fabricated finding or path.
    """
    (tmp_path / "context.json").write_text(json.dumps({"deadline": time.monotonic() + 0.2}))

    def prepare(directory: Path, context: dict[str, object]) -> int:
        """
        Model expensive worker-local analysis before the first queue claim.

        Args:
            directory (Path): Shared queue directory.
            context (dict[str, object]): Prepared inputs.

        Returns:
            int: Error if the shared deadline fails to interrupt startup.
        """
        time.sleep(10)
        return 1

    monkeypatch.setattr("hypothesis_helm.execution.workers.path_queue._run_queue", prepare)
    started = time.monotonic()
    assert worker_main([str(tmp_path)]) == 0
    assert time.monotonic() - started < 5
    assert not (tmp_path / "interrupted").exists()
    assert not (tmp_path / "execution-error.json").exists()
    assert not list(tmp_path.glob("started-*.json"))


def test_deadline_before_first_path_keeps_all_paths_unvisited(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Report a deadline during startup without inventing visited or incomplete path work.

    Args:
        tmp_path (Path): Discovered chart and report artifacts.
        monkeypatch (pytest.MonkeyPatch): Expire the execution budget at the queue boundary.

    Returns:
        None: All eight paths remain unvisited after a successful baseline and startup timeout.
    """
    chart = fixture_chart(tmp_path)
    monkeypatch.setattr("hypothesis_helm.charts.testing.paths.render", lambda *args, **kwargs: [{"kind": "ConfigMap"}])

    def expire(context: dict[str, object], directory: Path, workers: int) -> list[dict[str, object]]:
        """
        Simulate budget expiry before any path has been claimed.

        Args:
            context (dict[str, object]): Prepared chart and complete path inventory.
            directory (Path): Reserved queue directory.
            workers (int): Requested concurrent workers.

        Returns:
            list[dict[str, object]]: No records are returned because the deadline interrupts startup.
        """
        assert workers == 3
        assert len(sequence(context["paths"])) == 8
        raise TimeLimitReached()

    monkeypatch.setattr("hypothesis_helm.execution.workers.path_queue.execute", expire)
    result = check_paths(
        chart, budget=60, max_examples=10, seed=0, helm="helm", timeout=60, artifacts=tmp_path / "results", jobs=3, filtering=True
    )
    assert result["status"] == "time-limit"
    assert mapping(result["baseline"])["status"] == "passed"
    traversal = mapping(result["traversal"])
    assert traversal["visited_paths"] == traversal["incomplete_paths"] == traversal["completed_paths"] == 0
    assert traversal["selected_paths"] == traversal["remaining_paths"] == 8
    assert not traversal["path_targets_complete"]
    assert result["phases"] == []


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
    refresh_env()
    chart = fixture_chart(tmp_path)
    chart.defaults = {}
    chart.schema = {"type": "object", "additionalProperties": False, "properties": {}}
    (chart.path / "templates/config.yaml").write_text("")
    monkeypatch.setattr("hypothesis_helm.charts.testing.paths.render", lambda *args, **kwargs: [{"kind": "ConfigMap"}])
    result = check_paths(
        chart, budget=5, max_examples=10, seed=0, helm="helm", timeout=1, artifacts=tmp_path / "results", jobs=6, filtering=True
    )
    assert result["workers"] == 0 and result["status"] == "passed"
    assert mapping(result["traversal"])["visited_paths"] == 0
    assert result["attempts"] == 1


@pytest.mark.parametrize("jobs", [1, 2])
def test_returned_interrupt_stops_scheduling(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, jobs: int) -> None:
    """
    Preserve cancellation even when a runner returns it instead of raising an exception.

    Args:
        tmp_path (Path): Chart and partial artifacts.
        monkeypatch (pytest.MonkeyPatch): Return an interrupted path or stop before the first worker claim.
        jobs (int): Serial path iteration or parallel queue boundary.

    Returns:
        None: No later path runs and an empty interrupted queue cannot be reported as passed.
    """
    chart = fixture_chart(tmp_path)
    monkeypatch.setattr("hypothesis_helm.charts.testing.paths.render", lambda *args, **kwargs: [{"kind": "ConfigMap"}])
    calls = []

    def cancelled(*args: object, **kwargs: object) -> dict[str, object]:
        """
        Model a chart runner that records and returns its interruption.

        Args:
            *args (object): Prepared chart.
            **kwargs (object): Path execution options.

        Returns:
            dict[str, object]: Partial chart result.
        """
        calls.append(kwargs)
        return {"status": "interrupted", "attempts": 0}

    def empty_queue(context: dict[str, object], directory: Path, workers: int) -> list[dict[str, object]]:
        """
        Model cancellation after launching workers but before a path is claimed.

        Args:
            context (dict[str, object]): Shared execution settings.
            directory (Path): Queue marker directory.
            workers (int): Requested workers.

        Returns:
            list[dict[str, object]]: Empty partial work list with a separate cancellation marker.
        """
        directory.mkdir()
        (directory / "interrupted").touch()
        return []

    monkeypatch.setattr("hypothesis_helm.charts.testing.paths.check_chart", cancelled)
    monkeypatch.setattr("hypothesis_helm.execution.workers.path_queue.execute", empty_queue)
    result = check_paths(
        chart, budget=30, max_examples=10, seed=0, helm="helm", timeout=5, artifacts=tmp_path / "results", jobs=jobs, filtering=True
    )
    assert result["status"] == "interrupted"
    assert len(calls) == (1 if jobs == 1 else 0)
    assert mapping(result["traversal"])["remaining_paths"] == (7 if jobs == 1 else 8)


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
    refresh_env()
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

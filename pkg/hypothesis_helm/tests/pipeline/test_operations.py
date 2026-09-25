"""
Verify dependency scheduling and process ownership above the complete refresh workflow.
"""

import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from textwrap import dedent

import pytest
from hypothesis_helm_benchmarking.refresh.plan import STUDIES, Refresh
from pipeline import Operation, OperationQueue

from hypothesis_helm.execution.runtime.processes import Processes
from hypothesis_helm.execution.runtime.signals import DeferredSignals, Termination
from hypothesis_helm.tests import PACKAGES_ROOT


def queue(operations: list[Operation], directory: Path, workers: int = 3) -> OperationQueue:
    """
    Construct a real process queue confined to the test workspace.

    Args:
        operations (list[Operation]): Test operation graph.
        directory (Path): Working directory and persistent journal.
        workers (int): Maximum independent command workers.

    Returns:
        OperationQueue: Queue with native process ownership and suppressed progress messages.
    """
    return OperationQueue(
        operations,
        workers=workers,
        directory=directory,
        cwd=directory,
        environment=dict(os.environ),
        owner_factory=Processes,
        cancellation_scope=Termination,
        critical_scope=DeferredSignals,
        notify=lambda _: None,
    )


def test_inventory_covers_refresh_and_publication_barriers() -> None:
    """
    Require every study and supporting operation to reach the final publication gate.

    Returns:
        None: Every required refresh operation is reachable from the final barrier.
    """
    operations = Refresh(Path(".cache/refresh/refresh-1234")).operations()
    by_name = {operation.name: operation for operation in operations}

    def ancestors(name: str) -> set[str]:
        """
        Compute prerequisites without relying on the declaration's textual order.

        Args:
            name (str): Operation whose dependencies are followed.

        Returns:
            set[str]: Transitive prerequisite names.
        """
        return {parent for direct in by_name[name].requires for parent in {direct, *ancestors(direct)}}

    assert STUDIES
    assert len(STUDIES) == len(set(STUDIES))
    assert set(by_name) - {"publication-finished"} == ancestors("publication-finished")
    assert set(STUDIES) <= ancestors("topologies")
    assert set(STUDIES) <= ancestors("profile")
    assert {"flamegraphs", "publish", "verify-topologies", "update-benchmarks"} <= ancestors("bitnami")
    assert "bitnami-finalize" in ancestors("prometheus")
    assert all(by_name[name].exclusive for name in (*STUDIES, "profile", "bitnami", "prometheus"))


@pytest.mark.parametrize("damage", ["duplicate", "cycle", "missing"])
def test_inventory_rejects_invalid_dependencies(tmp_path: Path, damage: str) -> None:
    """
    Reject invalid inventories before producing logs or launching commands.

    Args:
        tmp_path (Path): Empty workspace.
        damage (str): Broken graph relationship.

    Returns:
        None: Validation fails without side effects.
    """
    command = (sys.executable, "-c", "raise AssertionError('must not run')")
    operations = [Operation("a", command, ("b",))]
    operations.append(Operation("a" if damage == "duplicate" else "b", command, ("a",) if damage == "cycle" else ("absent",)))
    with pytest.raises(ValueError):
        queue(operations, tmp_path)
    assert not list(tmp_path.iterdir())


def test_independent_workers_overlap_and_exclusive_work_waits(tmp_path: Path) -> None:
    """
    Exercise parallel readiness with a cross-process barrier and exclusive timing operation.

    Args:
        tmp_path (Path): Native worker handshake files and journal.

    Returns:
        None: Both workers overlap and no command overlaps the exclusive operation.
    """
    script = dedent(
        """
        import sys, time
        from pathlib import Path
        name = sys.argv[1]
        Path(name).touch()
        deadline = time.monotonic() + 5
        while not all(Path(item).exists() for item in ('a', 'b')):
            assert time.monotonic() < deadline, 'workers did not overlap'
            time.sleep(.01)
        Path(name + '-done').touch()
        """
    )
    operations = [Operation(name, (sys.executable, "-c", script, name)) for name in ("a", "b")]
    operations.append(Operation("timed", (sys.executable, "-c", "pass"), exclusive=True))
    records = queue(operations, tmp_path, 2).run()
    assert all(record["status"] == "completed" for record in records.values())
    assert float(str(records["timed"]["started_epoch"])) >= max(float(str(records[name]["finished_epoch"])) for name in ("a", "b"))
    assert len(json.loads((tmp_path / "operations.json").read_text())["operations"]) == 3
    assert not any(thread.name.startswith("pipeline-worker") for thread in threading.enumerate())


@pytest.mark.parametrize("mode", ["failure", "timeout"])
def test_failure_and_timeout_join_grandchildren(tmp_path: Path, mode: str) -> None:
    """
    Stop process trees and block dependent publication on failure or an operation deadline.

    Args:
        tmp_path (Path): PID evidence and operation logs.
        mode (str): Native failure or parent communication timeout.

    Returns:
        None: No child, grandchild, or command thread survives the failed queue.
    """
    child = dedent(
        """
        import os, subprocess, sys, time
        from pathlib import Path
        grandchild = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
        Path('pids').write_text(f'{os.getpid()} {grandchild.pid}')
        try:
            grandchild.wait()
        except KeyboardInterrupt:
            grandchild.wait()
        """
    )
    fail = dedent(
        """
        import time
        from pathlib import Path
        deadline = time.monotonic() + 10
        while not Path('pids').exists():
            assert time.monotonic() < deadline
            time.sleep(.01)
        raise SystemExit(7)
        """
    )
    operations = [Operation("child", (sys.executable, "-c", child), timeout=0.3 if mode == "timeout" else None)]
    if mode == "failure":
        operations.append(Operation("fail", (sys.executable, "-c", fail)))
    operations.append(Operation("publish", (sys.executable, "-c", "raise AssertionError()"), tuple(item.name for item in operations)))
    scheduler = queue(operations, tmp_path)
    with pytest.raises(RuntimeError if mode == "failure" else subprocess.TimeoutExpired):
        scheduler.run()
    for pid in (tmp_path / "pids").read_text().split():
        with pytest.raises(ProcessLookupError):
            os.kill(int(pid), 0)
    assert scheduler.records["publish"]["status"] == "blocked"
    assert not scheduler.owners
    assert not any(thread.name.startswith("pipeline-worker") for thread in threading.enumerate())


def test_cleanup_failure_does_not_skip_other_owners(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Retain a failed owner while stopping and joining every other registered worker.

    Args:
        tmp_path (Path): Queue journal directory.
        monkeypatch (pytest.MonkeyPatch): Controlled lifecycle errors without leaking native children.

    Returns:
        None: Both owners receive cleanup even when the first cleanup raises.
    """
    barrier = threading.Barrier(2, timeout=5)
    stopped: list[Processes] = []

    def execute(self: OperationQueue, operation: Operation, owner: Processes) -> int:
        """
        Hold both operations until their ownership registrations exist.

        Args:
            self (OperationQueue): Active scheduler.
            operation (Operation): Current descriptor.
            owner (Processes): Registered owner.

        Returns:
            int: A native-style nonzero exit.
        """
        barrier.wait()
        return 7

    def stop(self: Processes) -> None:
        """
        Fail cleanup for one owner while recording all attempted releases.

        Args:
            self (Processes): Worker owner.

        Returns:
            None: The first owner always raises to test retained ownership.
        """
        stopped.append(self)
        if self is stopped[0]:
            raise RuntimeError("cleanup failure")

    monkeypatch.setattr(OperationQueue, "execute", execute)
    monkeypatch.setattr(Processes, "stop", stop)
    scheduler = queue([Operation(name, ("unused",)) for name in ("a", "b")], tmp_path)
    with pytest.raises(ExceptionGroup, match="cleanup"):
        scheduler.run()
    assert len({id(owner) for owner in stopped}) == 2
    assert len(scheduler.owners) == 1
    assert not any(thread.name.startswith("pipeline-worker") for thread in threading.enumerate())


def test_empty_workflow_finishes_without_workers(tmp_path: Path) -> None:
    """
    Keep an empty operation inventory a valid completed base case.

    Args:
        tmp_path (Path): Empty journal directory.

    Returns:
        None: No operation is scheduled and no worker survives.
    """
    assert queue([], tmp_path).run() == {}


def test_submission_failure_preserves_registered_owner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Keep ownership registered before a worker submission can raise.

    Args:
        tmp_path (Path): Failed-start journal directory.
        monkeypatch (pytest.MonkeyPatch): Inject a worker-pool startup error.

    Returns:
        None: The registered owner is stopped even when no future is returned.
    """
    from unittest.mock import Mock

    import pipeline.operations

    pool = Mock()
    pool.submit.side_effect = RuntimeError("cannot start worker")
    monkeypatch.setattr(pipeline.operations, "ThreadPoolExecutor", Mock(return_value=pool))
    owner = Mock(spec=Processes)
    scheduler = queue([Operation("a", ("unused",))], tmp_path)
    scheduler.owner_factory = lambda: owner
    with pytest.raises(RuntimeError, match="cannot start worker"):
        scheduler.run()
    owner.stop.assert_called_once()
    pool.shutdown.assert_called_once_with(wait=True, cancel_futures=True)
    assert scheduler.records["a"]["status"] == "cancelled"
    assert not scheduler.owners


def test_interrupt_joins_running_operations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Propagate cancellation only after every registered worker has finished cleanup.

    Args:
        tmp_path (Path): Interrupted workflow journal.
        monkeypatch (pytest.MonkeyPatch): Raise cancellation at the coordinator's result boundary.

    Returns:
        None: An interrupted result blocks downstream work and releases both owners.
    """
    barrier = threading.Barrier(2, timeout=5)
    stopped: set[int] = set()

    def execute(self: OperationQueue, operation: Operation, owner: Processes) -> int:
        """
        Return an interrupt while another worker is already owned.

        Args:
            self (OperationQueue): Active queue.
            operation (Operation): Current operation.
            owner (Processes): Registered owner.

        Returns:
            int: Zero for the sibling; the interrupting operation raises.
        """
        barrier.wait()
        if operation.name == "interrupt":
            raise KeyboardInterrupt()
        return 0

    monkeypatch.setattr(OperationQueue, "execute", execute)
    monkeypatch.setattr(Processes, "stop", lambda self: stopped.add(id(self)))
    scheduler = queue(
        [
            Operation("interrupt", ("unused",)),
            Operation("sibling", ("unused",)),
            Operation("publish", ("unused",), ("interrupt", "sibling")),
        ],
        tmp_path,
    )
    with pytest.raises(KeyboardInterrupt):
        scheduler.run()
    assert len(stopped) == 2
    assert not scheduler.owners
    assert scheduler.records["publish"]["status"] == "blocked"
    assert not any(thread.name.startswith("pipeline-worker") for thread in threading.enumerate())


@pytest.mark.parametrize("exit_code", [0, 7])
def test_operation_output_streams_before_exit(tmp_path: Path, exit_code: int) -> None:
    """
    Deliver both streams while children wait for acknowledgement, then flush final partial lines.

    Args:
        tmp_path (Path): Child acknowledgements and untouched raw log files.
        exit_code (int): Native exit status to preserve after forwarding output.

    Returns:
        None: Concurrent output reaches only the coordinator before command completion.
    """
    script = dedent(
        """
        import sys, time
        from pathlib import Path
        name, code = sys.argv[1:]
        print('stdout ready')
        print('stderr ready', file=sys.stderr)
        deadline = time.monotonic() + 10
        while not Path('release').exists():
            if time.monotonic() > deadline:
                raise RuntimeError('output was not forwarded while running')
            time.sleep(.01)
        print('final partial line', end='')
        raise SystemExit(int(code))
        """
    )
    names = ("left", "right") if exit_code == 0 else ("failed",)
    operations = [Operation(name, (sys.executable, "-c", script, name, str(exit_code))) for name in names]
    scheduler = queue(operations, tmp_path)
    messages: list[str] = []
    coordinator = threading.get_ident()

    def notify(message: str) -> None:
        """
        Release children only after all stdout and stderr diagnostics reach the coordinator.

        Args:
            message (str): Scheduling event or labeled child output.

        Returns:
            None: Every running child receives the shared acknowledgement.
        """
        assert threading.get_ident() == coordinator
        messages.append(message)
        if all(f"[{name}] {stream} ready" in messages for name in names for stream in ("stdout", "stderr")):
            (tmp_path / "release").touch()

    scheduler.notify = notify
    if exit_code:
        with pytest.raises(RuntimeError, match="exited 7"):
            scheduler.run()
    else:
        scheduler.run()
    for name in names:
        assert messages.count(f"[{name}] stdout ready") == 1
        assert messages.count(f"[{name}] stderr ready") == 1
        assert messages.count(f"[{name}] final partial line") == 1
        assert (tmp_path / "logs" / f"{name}.log").read_bytes() == b"stdout ready\nstderr ready\nfinal partial line"
        if not exit_code:
            complete = next(index for index, message in enumerate(messages) if f"Completed {name} " in message)
            assert messages.index(f"[{name}] final partial line") < complete
    assert not scheduler.outputs
    assert not scheduler.owners


def test_operation_output_retains_bytes_and_bounds_partial_lines(tmp_path: Path) -> None:
    """
    Handle split UTF-8, carriage returns, invalid bytes and long output without changing its log.

    Args:
        tmp_path (Path): Binary operation log.

    Returns:
        None: Terminal decoding is incremental and pending output is bounded.
    """
    from pipeline.output import OperationOutput

    messages: list[str] = []
    path = tmp_path / "operation.log"
    output = OperationOutput(path, "operation", messages.append)
    with path.open("ab", buffering=0) as writer:
        writer.write(b"\xc3")
        output.drain()
        assert not messages
        writer.write(b"\xa9\nprogress\rnext\r\ninvalid:\xff\n")
        output.drain()
        assert messages == ["[operation] é", "[operation] progress", "[operation] next", "[operation] invalid:�"]
        writer.write(b"x" * 200000)
        output.drain()
        assert len(output.pending) < 8192
        assert output.reader.tell() < path.stat().st_size
    output.close()
    assert "".join(message.removeprefix("[operation] ") for message in messages[4:]) == "x" * 200000
    assert path.read_bytes() == b"\xc3\xa9\nprogress\rnext\r\ninvalid:\xff\n" + b"x" * 200000
    assert output.reader.closed
    output.close()


def test_logging_failure_still_joins_children(tmp_path: Path) -> None:
    """
    Preserve raw logs and release process ownership if the terminal sink stops accepting output.

    Args:
        tmp_path (Path): Interrupted operation journal and raw log.

    Returns:
        None: A logging exception cannot leave command threads or child owners running.
    """
    scheduler = queue([Operation("child", (sys.executable, "-u", "-c", "import time; print('ready'); time.sleep(30)"))], tmp_path)

    def notify(message: str) -> None:
        """
        Simulate a closed terminal only after the command starts writing.

        Args:
            message (str): Coordinator notification.

        Returns:
            None: Child output raises a broken-pipe failure.
        """
        if message.startswith("[child]"):
            raise BrokenPipeError("terminal closed")

    scheduler.notify = notify
    with pytest.raises((BrokenPipeError, BaseExceptionGroup)):
        scheduler.run()
    assert "ready" in (tmp_path / "logs/child.log").read_text()
    assert not scheduler.outputs
    assert not scheduler.owners
    assert not any(thread.name.startswith("pipeline-worker") for thread in threading.enumerate())


@pytest.mark.skipif(shutil.which("parallel") is None, reason="requires GNU Parallel")
def test_repository_diagnostics_reach_queue_before_chart_exit(tmp_path: Path) -> None:
    """
    Forward nested scan diagnostics through tee and GNU Parallel without corrupting result JSON.

    Args:
        tmp_path (Path): Isolated chart recipe, recording executable and scan data.

    Returns:
        None: Live stderr is both saved and forwarded, and the failed chart still fails the queue.
    """
    recipes = PACKAGES_ROOT / "hypothesis_helm_benchmarking/refresh/recipes"
    scan = tmp_path / "scan"
    (scan / "jobs").mkdir(parents=True)
    (scan / "charts.txt").write_bytes(b"example-chart\0")
    shutil.copyfile(recipes / "repository-chart.sh", scan / "chart.sh")
    binary = tmp_path / "bin"
    binary.mkdir()
    executable = binary / "hypothesis-helm"
    executable.write_text(
        dedent(
            """
            #!/usr/bin/env bash
            printf 'chart diagnostic\n' >&2
            for ((attempt = 0; attempt < 500; attempt++)); do
                if [[ -f release ]]; then
                    mkdir -p scan/runs
                    printf '{"chart":"example-chart"}\n' >scan/runs/scan.json
                    printf 'Results saved: scan/runs/scan.json\n'
                    exit 7
                fi
                sleep .01
            done
            exit 99
            """
        ).lstrip()
    )
    executable.chmod(0o755)
    scheduler = queue([Operation("repository", ("bash", str(recipes / "repository-run.sh"), "scan"), timeout=10)], tmp_path)
    scheduler.environment["PATH"] = f"{binary}{os.pathsep}{os.environ['PATH']}"
    messages: list[str] = []

    def notify(message: str) -> None:
        """
        Allow the scan to finish only after its diagnostic traverses the complete execution stack.

        Args:
            message (str): Coordinator output from the repository operation.

        Returns:
            None: Receipt of the live diagnostic acknowledges the blocked chart process.
        """
        messages.append(message)
        if message == "[repository] chart diagnostic":
            (tmp_path / "release").touch()

    scheduler.notify = notify
    with pytest.raises(RuntimeError, match="Operation repository exited"):
        scheduler.run()
    assert (tmp_path / "release").exists()
    assert json.loads((scan / "jobs/1.json").read_text()) == {"chart": "example-chart"}
    assert (scan / "jobs/1.err").read_text() == "chart diagnostic\n"
    assert (scan / "jobs/1.out").read_text() == "Results saved: scan/runs/scan.json\n"
    assert not any('"chart"' in message for message in messages)
    columns, row = (scan / "joblog.tsv").read_text().splitlines()
    assert dict(zip(columns.split("\t"), row.split("\t"), strict=True))["Exitval"] == "7"
    assert not scheduler.outputs
    assert not scheduler.owners

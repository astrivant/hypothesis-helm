"""
Verify dependency scheduling and process ownership above the complete refresh workflow.
"""

import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from textwrap import dedent

import pytest
from workgraph import Operation, OperationQueue

from hypothesis_helm.benchmarking.refresh.plan import STUDIES, Refresh
from hypothesis_helm.execution.processes import Processes
from hypothesis_helm.execution.signals import DeferredSignals, Termination


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
    operations = Refresh(Path("benchmarks/runs/refresh-1234")).operations()
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

    assert len(STUDIES) == 15
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
    assert not any(thread.name.startswith("workgraph-worker") for thread in threading.enumerate())


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
    assert not any(thread.name.startswith("workgraph-worker") for thread in threading.enumerate())


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
    assert not any(thread.name.startswith("workgraph-worker") for thread in threading.enumerate())


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

    import workgraph.operations

    pool = Mock()
    pool.submit.side_effect = RuntimeError("cannot start worker")
    monkeypatch.setattr(workgraph.operations, "ThreadPoolExecutor", Mock(return_value=pool))
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
    assert not any(thread.name.startswith("workgraph-worker") for thread in threading.enumerate())

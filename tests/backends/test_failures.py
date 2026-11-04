"""
Exercise native failure ownership, bounded retries and stale result rejection deterministically.
"""

from __future__ import annotations

from threading import Event

import pytest
from attrs import evolve
from hypothesis_helm.compiler.backends import scheduler
from hypothesis_helm.compiler.backends.engine import Batch, prepare
from hypothesis_helm.compiler.backends.model import Factor, Limits, Node, Opcode, Plan, State, digest
from hypothesis_helm.compiler.backends.scheduler import BackendOptions, Report, Scheduler, Worker
from hypothesis_helm.exceptions.backends import BackendError, BackendUnavailable


def program() -> Plan:
    """
    Provide an eight-case pure plan without chart or external process dependencies.

    Returns:
        Plan: Bounded stable predicate fixture.
    """
    return Plan(
        digest({}),
        (Factor(("value",), 8, digest(list(range(8)))),),
        (Node(Opcode.CONSTANT, table=(State.TRUE,)),),
        0,
        limits=Limits(batch_size=8),
    )


class AllocationLimited:
    """
    Model deterministic memory pressure without allocating or sleeping.
    """

    def __init__(self, plan: Plan, backend: str) -> None:
        """
        Record owned lifetime and attempted candidate intervals.

        Args:
            plan (Plan): Input plan, unused by this pure test engine.
            backend (str): Requested test route.

        Returns:
            None: Initializes fresh task-owned test state.
        """
        self.closed = False
        self.calls: list[tuple[int, ...]] = []

    def evaluate(self, ids: tuple[int, ...]) -> Batch:
        """
        Fail allocations above two rows and complete smaller pure retries.

        Args:
            ids (tuple[int, ...]): Requested candidate interval.

        Returns:
            Batch: Stable results for the admitted smaller interval.
        """
        self.calls.append(ids)
        if len(ids) > 2:
            raise MemoryError("injected bounded allocation failure")
        return Batch(ids, (State.TRUE,) * len(ids), 0.0)

    def close(self) -> None:
        """
        Mark owned resource cleanup for the assertions.

        Returns:
            None: The test engine is closed.
        """
        self.closed = True


def test_oom_splits_only_pure_work(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Require ordered idempotent results and bounded retry accounting after OOM.

    Args:
        monkeypatch (pytest.MonkeyPatch): Scoped engine substitution.

    Returns:
        None: All cases survive splitting once, with the worker closed afterward.
    """
    monkeypatch.setattr(scheduler, "Worker", AllocationLimited)
    report = Report("gpu", "gpu")
    runner = Scheduler(program(), BackendOptions("gpu"), report)
    worker = runner.worker
    try:
        result = list(runner.candidates((index,) for index in range(8)))
        assert [number for _, number, _ in result] == list(range(8))
        assert report.retries == 3
        assert report.physical_cases == 8
        assert report.committed_cases == 0
    finally:
        runner.close()
    assert isinstance(worker, AllocationLimited) and worker.closed


def test_unavailable_needs_explicit_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Refuse a silent backend switch and retain all cases under explicit fallback.

    Args:
        monkeypatch (pytest.MonkeyPatch): Scoped startup failure injection.

    Returns:
        None: Missing hardware never becomes a successful GPU result.
    """

    def unavailable(plan: Plan, backend: str) -> Worker:
        """
        Simulate a permanent unavailable device.

        Args:
            plan (Plan): Current program.
            backend (str): Requested route.

        Returns:
            Worker: Never returned for this unavailable fixture.
        """
        raise BackendUnavailable("injected missing device")

    monkeypatch.setattr(scheduler, "Worker", unavailable)
    with pytest.raises(BackendUnavailable):
        Scheduler(program(), BackendOptions("gpu"), Report("gpu", "gpu"))
    report = Report("gpu", "gpu")
    runner = Scheduler(program(), BackendOptions("gpu", "reference"), report)
    try:
        result = list(runner.candidates((index,) for index in range(8)))
        assert [number for _, number, _ in result] == list(range(8))
        assert all(state == State.UNKNOWN for _, _, state in result)
        assert report.selected == "reference"
        assert report.physical_cases == 0
    finally:
        runner.close()


def test_memory_admission_precedes_native_calls() -> None:
    """
    Reject oversized scratch and outputs before allocating device memory.

    Returns:
        None: Input remains uncommitted when a request exceeds its memory budget.
    """
    plan = evolve(program(), limits=Limits(memory_bytes=128, batch_size=8))
    engine = prepare(plan, "reference")
    try:
        with pytest.raises(MemoryError):
            engine.evaluate(tuple(range(8)))
    finally:
        engine.close()


@pytest.mark.parametrize("fault", ["plan", "fence", "sequence", "truncated", "reordered", "cancelled"])
def test_receipt_fences(monkeypatch: pytest.MonkeyPatch, fault: str) -> None:
    """
    Reject late, duplicate, wrong-plan and incomplete worker results before commit.

    Args:
        monkeypatch (pytest.MonkeyPatch): Scoped private transport substitution.
        fault (str): Receipt violation under test.

    Returns:
        None: No invalid worker output is accepted.
    """
    worker = object.__new__(Worker)
    worker.plan = program()
    worker.fence = 0
    worker.sequence = 0
    worker.stopped = Event()
    parent, child = scheduler.multiprocessing.get_context("spawn").Pipe()
    worker.connection = parent
    ids = (0, 1)
    receipt = Batch(ids[::-1] if fault == "reordered" else ids, (State.TRUE,) if fault == "truncated" else (State.TRUE, State.TRUE), 0.0)

    def receive() -> object:
        """
        Return a deterministic violating receipt after admission.

        Returns:
            object: Transport payload with one explicit lifecycle fault.
        """
        if fault == "cancelled":
            worker.stopped.set()
        return (
            "done",
            digest("different") if fault == "plan" else worker.plan.identity,
            1 if fault == "fence" else 0,
            0 if fault == "sequence" else 1,
            receipt,
        )

    monkeypatch.setattr(worker, "receive", receive)
    try:
        with pytest.raises(BackendError):
            worker.evaluate(ids)
    finally:
        parent.close()
        child.close()

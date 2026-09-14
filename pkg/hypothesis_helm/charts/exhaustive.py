"""
Prefetch a bounded window of Helm processes while one coordinator verifies their outputs.
"""

from collections import deque
from collections.abc import Iterator, Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from threading import Lock
from time import perf_counter
from types import TracebackType
from typing import Self

from hypothesis_helm.charts.model import Chart
from hypothesis_helm.charts.rendering import render_output
from hypothesis_helm.execution.processes import Processes
from hypothesis_helm.execution.signals import DeferredSignals, Termination
from hypothesis_helm.reporting.budget import TimeLimitReached

type RenderTask = tuple[dict[str, object], Future[str]]


class ExhaustiveRenders:
    """
    Own parallel Helm children, preserving seed order and a single chart deadline.
    """

    def __init__(
        self,
        chart: Chart,
        values: Sequence[dict[str, object]],
        jobs: int,
        deadline: float,
        *,
        helm: str,
        timeout: float,
        release: str,
        namespace: str,
        kube_version: str | None,
    ) -> None:
        """
        Prepare a scheduler without creating threads or processes until entered.

        Args:
            chart (Chart): Prepared chart shared read-only by Helm children.
            values (Sequence[dict[str, object]]): Deterministically replayable input sequence.
            jobs (int): Maximum concurrently pending renders.
            deadline (float): Shared perf_counter deadline, including coordinator validation.
            helm (str): Helm executable.
            timeout (float): Per-render ceiling within the shared deadline.
            release (str): Fixed release name.
            namespace (str): Fixed namespace.
            kube_version (str | None): Optional Kubernetes capability version.
        """
        self.chart = chart
        self.values = values
        self.workers = min(jobs, len(values))
        self.deadline = deadline
        self.helm, self.timeout = helm, timeout
        self.release, self.namespace, self.kube_version = release, namespace, kube_version
        self.pool: ThreadPoolExecutor | None = None
        self.owners: dict[int, Processes] = {}
        self.lock = Lock()
        self.stopping = False
        self.submitted = 0
        self.finished = 0
        self.termination = Termination()

    def __enter__(self) -> Self:
        """
        Establish cancellation ownership before launching any work.

        Returns:
            Self: Active scheduler, including an empty-domain scheduler with no pool.
        """
        try:
            with DeferredSignals():
                self.termination.__enter__()
                if self.workers:
                    self.pool = ThreadPoolExecutor(max_workers=self.workers, thread_name_prefix="exhaustive-helm")
        except BaseException as exc:
            self.__exit__(type(exc), exc, exc.__traceback__)
            raise
        return self

    def execute(self, values: dict[str, object]) -> str:
        """
        Own one Helm process until it has been joined, including interrupted communication.

        Args:
            values (dict[str, object]): One pending input, constructed only within the active window.

        Returns:
            str: Raw YAML; validation and shared hash bookkeeping remain on the coordinator.
        """
        owner = Processes()
        with self.lock:
            if self.stopping or perf_counter() >= self.deadline:
                raise TimeLimitReached()
            self.owners[id(owner)] = owner
        try:
            return render_output(
                self.chart,
                values,
                helm=self.helm,
                timeout=min(self.timeout, max(0.000001, self.deadline - perf_counter())),
                release=self.release,
                namespace=self.namespace,
                kube_version=self.kube_version,
                processes=owner,
            )
        finally:
            # Keep the owner registered if cleanup fails so close can retry it.
            owner.stop()
            with self.lock:
                self.owners.pop(id(owner))
                self.finished += 1

    def __iter__(self) -> Iterator[RenderTask]:
        """
        Yield in the original seeded order, keeping at most one window of values and raw outputs.

        Yields:
            RenderTask: Input and its pending Helm result.
        """
        if self.pool is None:
            return
        pending: deque[RenderTask] = deque()
        position = 0
        while position < len(self.values) or pending:
            while len(pending) < self.workers and position < len(self.values):
                if perf_counter() >= self.deadline:
                    raise TimeLimitReached()
                values = self.values[position]
                pending.append((values, self.pool.submit(self.execute, values)))
                self.submitted += 1
                position += 1
            yield pending.popleft()

    def __exit__(self, kind: type[BaseException] | None, error: BaseException | None, traceback: TracebackType | None) -> None:
        """
        Stop every owned process and join all worker threads before leaving any exit path.

        Args:
            kind (type[BaseException] | None): Original exception type.
            error (BaseException | None): Original failure or cancellation.
            traceback (TracebackType | None): Original traceback.

        Returns:
            None: Cleanup failures are retained without skipping another owner's cleanup.
        """
        failures: list[BaseException] = []
        try:
            with DeferredSignals():
                with self.lock:
                    self.stopping = True
                    owners = list(self.owners.values())
                for owner in owners:
                    try:
                        owner.stop()
                    except BaseException as exc:
                        failures.append(exc)
                if self.pool is not None:
                    try:
                        self.pool.shutdown(wait=True, cancel_futures=True)
                    except BaseException as exc:
                        failures.append(exc)
        finally:
            self.termination.__exit__(kind, error, traceback)
        if failures:
            raise BaseExceptionGroup("Exhaustive worker cleanup failed", ([error] if error is not None else []) + failures)

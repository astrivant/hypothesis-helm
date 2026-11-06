"""
Bound speculative pure work while the existing coordinator commits in reference order.
"""

from __future__ import annotations

import itertools
import logging
import multiprocessing
import time
from collections.abc import Generator, Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from multiprocessing.connection import Connection
from threading import Event

from attrs import define, field, frozen

from hypothesis_helm.compiler.backends.engine import Batch, Engine, prepare
from hypothesis_helm.compiler.backends.model import Limits, Plan, State
from hypothesis_helm.exceptions.backends import BackendError, BackendUnavailable

__all__ = ("DEFAULT_BACKEND", "BackendOptions", "Report", "Scheduler", "Worker")

LOGGER = logging.getLogger(__name__)

type Candidate = tuple[tuple[int, ...], int, State]


@frozen
class BackendOptions:
    """
    Select an explicit engine without changing candidate selection or oracle policy.

    Attributes:
        name (str): reference, cpu-vector or gpu.
        fallback (str): error or explicitly permitted reference fallback on engine failure.
        limits (Limits): Compilation and double-buffer admission limits.
        verify (bool): Compare every result against authoritative host schema validation.
    """

    name: str = "reference"
    fallback: str = "error"
    limits: Limits = Limits()
    verify: bool = False

    def __attrs_post_init__(self) -> None:
        """
        Reject ambiguous runtime selection before starting processes.

        Returns:
            None: Options have a known selection and failure policy.
        """
        if self.name not in {"reference", "cpu-vector", "gpu"} or self.fallback not in {"error", "reference"}:
            raise ValueError("invalid execution backend or fallback policy")


DEFAULT_BACKEND = BackendOptions()


@define
class Report:
    """
    Separate speculative compute, logical input checks and committed selection.

    Attributes:
        requested (str): User-selected backend.
        selected (str): Effective compute route.
        plan_digest (str): Exact plan identity, when compilation succeeded.
        device (str): Physical GPU kind, CPU or reference route, when initialized.
        physical_cases (int): Completed pure evaluations, including speculative extras.
        logical_cases (int): Candidates consumed by the ordered host coordinator.
        committed_cases (int): Accepted complete configurations; never completed renders.
        unknown_cases (int): Consumed predicates requiring host schema validation.
        mismatches (int): Observed disagreements, each fatal to this plan.
        retries (int): Bounded OOM split retries.
        batches (int): Completed worker requests.
        compute_seconds (float): Transfer-inclusive worker evaluation time.
        fallback_reasons (dict[str, int]): Bounded reason counters without input values.
    """

    requested: str
    selected: str
    plan_digest: str = ""
    device: str = ""
    physical_cases: int = 0
    logical_cases: int = 0
    committed_cases: int = 0
    unknown_cases: int = 0
    mismatches: int = 0
    retries: int = 0
    batches: int = 0
    compute_seconds: float = 0.0
    fallback_reasons: dict[str, int] = field(factory=dict)

    def export(self) -> dict[str, object]:
        """
        Produce bounded report data without chart values or device credentials.

        Returns:
            dict[str, object]: Current compute and selection counters.
        """
        return {
            name: getattr(self, name)
            for name in (
                "requested",
                "selected",
                "plan_digest",
                "device",
                "physical_cases",
                "logical_cases",
                "committed_cases",
                "unknown_cases",
                "mismatches",
                "retries",
                "batches",
                "compute_seconds",
                "fallback_reasons",
            )
        }


def _worker(connection: Connection[object, object], plan: Plan, backend: str) -> None:
    """
    Isolate native compilation and device failures in one exclusively owned process.

    Args:
        connection (Connection[object, object]): Private parent/child channel, never an untrusted plan loader.
        plan (Plan): Parent-validated immutable program.
        backend (str): Requested native engine.

    Returns:
        None: Closes buffers and the private channel before process exit.
    """
    engine: Engine | None = None
    try:
        engine = prepare(plan, backend)
        connection.send(("ready", plan.identity, engine.device))
        while True:
            packet = connection.recv()
            if packet is None:
                break
            if not isinstance(packet, tuple) or len(packet) != 4:
                raise BackendError("invalid worker request")
            fence, sequence, ids, choices = packet
            try:
                batch = engine.evaluate(ids, choices)
                connection.send(("done", plan.identity, fence, sequence, batch))
            except MemoryError:
                connection.send(("oom", plan.identity, fence, sequence, None))
            except Exception as exc:
                if getattr(exc, "code", None) == 2:
                    connection.send(("oom", plan.identity, fence, sequence, None))
                else:
                    raise
    except BackendUnavailable:
        connection.send(("unavailable",))
    except (EOFError, BrokenPipeError):
        pass
    except Exception as exc:
        # The native boundary must quarantine driver/compiler failures without leaking payloads.
        connection.send(("failed", type(exc).__name__))
    finally:
        if engine is not None:
            engine.close()
        connection.close()


class Worker:
    """
    Enforce request deadlines and fence stale results from a single native worker.
    """

    def __init__(self, plan: Plan, backend: str) -> None:
        """
        Start one spawned worker without inheriting a parent device context.

        Args:
            plan (Plan): Validated immutable program.
            backend (str): Explicit compute backend.

        """
        self.plan = plan
        self.fence = 0
        self.sequence = 0
        self.stopped = Event()
        context = multiprocessing.get_context("spawn")
        self.connection, child = context.Pipe()
        self.process = context.Process(target=_worker, args=(child, plan, backend), name="hypothesis-helm-backend")
        self.process.start()
        child.close()
        try:
            ready = self.receive()
            valid_devices = {"reference": {"reference"}, "cpu-vector": {"cpu"}, "gpu": {"cuda", "mps"}}
            if (
                not isinstance(ready, tuple)
                or len(ready) != 3
                or ready[:2] != ("ready", plan.identity)
                or not isinstance(ready[2], str)
                or ready[2] not in valid_devices[backend]
            ):
                raise BackendUnavailable("requested backend could not initialize")
            self.device = ready[2]
        except BaseException:
            self.close()
            raise

    def receive(self) -> object:
        """
        Wait interruptibly within the declared worker deadline.

        Returns:
            object: Trusted child protocol packet requiring receipt validation.
        """
        deadline = time.monotonic() + self.plan.limits.timeout
        while not self.stopped.is_set():
            if self.connection.poll(min(0.1, max(0.0, deadline - time.monotonic()))):
                try:
                    return self.connection.recv()
                except EOFError as exc:
                    raise BackendError("backend worker exited before its receipt") from exc
            if time.monotonic() >= deadline or not self.process.is_alive():
                raise BackendError("backend worker deadline or process failure")
        raise BackendError("backend work cancelled")

    def evaluate(self, ids: tuple[int, ...], choices: tuple[tuple[int, ...], ...] = ()) -> Batch:
        """
        Admit and accept one uniquely sequenced result for the current cancellation fence.

        Args:
            ids (tuple[int, ...]): Immutable ordered assignments.
            choices (tuple[tuple[int, ...], ...]): Explicit dictionary rows for wide domains.

        Returns:
            Batch: Matching live receipt with exactly one state per assignment.
        """
        if self.stopped.is_set():
            raise BackendError("backend work cancelled")
        self.sequence += 1
        fence, sequence = self.fence, self.sequence
        self.connection.send((fence, sequence, ids, choices))
        packet = self.receive()
        # The child reports only a bounded exception class, never its payload.
        if (
            isinstance(packet, tuple)
            and len(packet) == 2
            and packet[0] == "failed"
            and isinstance(packet[1], str)
            and len(packet[1]) <= 64
            and packet[1].isidentifier()
        ):
            raise BackendError(f"backend worker failed ({packet[1]})")
        if not isinstance(packet, tuple) or len(packet) != 5 or packet[1:4] != (self.plan.identity, fence, sequence):
            raise BackendError("backend returned an invalid, duplicate or stale receipt")
        if packet[0] == "oom":
            raise MemoryError("backend allocation failed")
        result = packet[4]
        if (
            packet[0] != "done"
            or self.stopped.is_set()
            or self.fence != fence
            or not isinstance(result, Batch)
            or result.ids != ids
            or len(result.states) != len(ids)
            or any(not isinstance(state, State) for state in result.states)
        ):
            raise BackendError("backend returned incomplete or stale output")
        return result

    def close(self) -> None:
        """
        Fence late output and join only the owned worker within a bounded shutdown.

        Returns:
            None: No native work or owned child process remains.
        """
        if self.stopped.is_set():
            return
        self.stopped.set()
        self.fence += 1
        if self.process.is_alive():
            try:
                self.connection.send(None)
            except (BrokenPipeError, EOFError, OSError):
                pass
        self.process.join(timeout=2)
        if self.process.is_alive():
            self.process.terminate()
            self.process.join(timeout=2)
            if self.process.is_alive():
                self.process.kill()
                self.process.join()
        self.connection.close()


class Scheduler:
    """
    Double-buffer pure evaluation; leave callbacks and coverage in the calling thread.
    """

    def __init__(self, plan: Plan, options: BackendOptions, report: Report) -> None:
        """
        Prepare one worker and a single bounded orchestration thread.

        Args:
            plan (Plan): Immutable finite program.
            options (BackendOptions): Explicit failure and execution policies.
            report (Report): Run-owned compute counters.

        """
        self.plan = plan
        self.options = options
        self.report = report
        self.worker: Engine | None = None
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="backend-admission")
        self.closed = False
        report.plan_digest = plan.identity
        try:
            self.worker = Worker(plan, options.name)
            report.device = self.worker.device
        except BackendError:
            self.pool.shutdown(wait=True)
            if options.fallback != "reference":
                raise
            self.fallback("unavailable")

    def fallback(self, reason: str) -> None:
        """
        Quarantine native work and record the explicitly selected host fallback.

        Args:
            reason (str): Bounded non-sensitive classification.

        Returns:
            None: Subsequent input predicates require authoritative host validation.
        """
        if self.worker is not None:
            self.worker.close()
            self.worker = None
        self.report.selected = "reference"
        self.report.fallback_reasons[reason] = self.report.fallback_reasons.get(reason, 0) + 1
        LOGGER.warning("Backend fallback: %s -> reference (%s)", self.options.name, reason)

    def evaluate(self, ids: tuple[int, ...], attempt: int = 0) -> Batch:
        """
        Retry only pure work with bounded OOM splitting and explicit failure policy.

        Args:
            ids (tuple[int, ...]): Ordered assignments.
            attempt (int): Current split depth, bounded to three retries per branch.

        Returns:
            Batch: Complete ordered results or explicit host-required states.
        """
        if self.worker is None:
            return Batch(ids, (State.UNKNOWN,) * len(ids), 0.0)
        try:
            result = self.worker.evaluate(ids)
        except MemoryError as exc:
            if attempt < 3 and len(ids) > 1:
                self.report.retries += 1
                middle = len(ids) // 2
                left = self.evaluate(ids[:middle], attempt + 1)
                right = self.evaluate(ids[middle:], attempt + 1)
                return Batch(ids, left.states + right.states, left.seconds + right.seconds)
            if self.options.fallback == "error":
                raise BackendError("backend exhausted bounded allocation retries") from exc
            self.fallback("memory-budget")
            return Batch(ids, (State.UNKNOWN,) * len(ids), 0.0)
        except (BackendError, OSError) as exc:
            if self.options.fallback == "error":
                raise BackendError("backend failed; no results from this attempt were committed") from exc
            self.fallback("worker-failure")
            return Batch(ids, (State.UNKNOWN,) * len(ids), 0.0)
        self.report.physical_cases += len(ids)
        self.report.batches += 1
        self.report.compute_seconds += result.seconds
        return result

    @contextmanager
    def ordered(self, rows: Iterable[tuple[int, ...]]) -> Iterator[Iterator[Candidate]]:
        """
        Cancel native work immediately when the host callback or coordinator fails.

        Args:
            rows (Iterable[tuple[int, ...]]): Current target's ordered completions.

        Yields:
            Iterator[Candidate]: Owned ordered candidate stream.
        """
        stream = self.candidates(rows)
        # A streaming implementation must retain deterministic cleanup of its
        # speculative tail, even if the host stops at its first accepted case.
        if not isinstance(stream, Generator):
            raise BackendError("backend candidates must own a closeable generator")
        try:
            yield stream
        except BaseException:
            self.close()
            raise
        finally:
            stream.close()

    def candidates(self, rows: Iterable[tuple[int, ...]]) -> Iterator[Candidate]:
        """
        Yield reference-order completions with at most two admitted pure batches.

        Args:
            rows (Iterable[tuple[int, ...]]): Consecutive reference completion ordinals for one target.

        Yields:
            Candidate: Factor choices, compact ID and predicate result.
        """
        iterator = iter(rows)

        def batch() -> tuple[tuple[tuple[int, ...], ...], tuple[int, ...]]:
            """
            Pack one bounded consecutive interval without constructing values documents.

            Returns:
                tuple[tuple[tuple[int, ...], ...], tuple[int, ...]]: Rows and compact identities.
            """
            selected = tuple(itertools.islice(iterator, self.plan.limits.batch_size))
            numbers = []
            for row in selected:
                number = 0
                for factor, choice in zip(self.plan.factors, row, strict=True):
                    number = number * factor.radix + choice
                numbers.append(number)
            return selected, tuple(numbers)

        current, ids = batch()
        if self.worker is None:
            for row in itertools.chain(current, iterator):
                number = 0
                for factor, choice in zip(self.plan.factors, row, strict=True):
                    number = number * factor.radix + choice
                yield row, number, State.UNKNOWN
            return
        pending = self.pool.submit(self.evaluate, ids) if current else None
        try:
            while pending is not None:
                result = pending.result()
                next_rows, next_ids = batch()
                pending = self.pool.submit(self.evaluate, next_ids) if next_rows else None
                for row, number, state in zip(current, result.ids, result.states, strict=True):
                    if self.closed:
                        raise BackendError("cancelled work cannot be committed")
                    yield row, number, state
                current = next_rows
        finally:
            # A target's speculative tail never crosses into the next coverage epoch.
            if pending is not None:
                if self.closed:
                    pending.cancel()
                else:
                    pending.result()

    def close(self) -> None:
        """
        Cancel admission, release the worker and join the owned orchestration thread.

        Returns:
            None: All task-owned execution resources are reclaimed.
        """
        if not self.closed:
            self.closed = True
            if self.worker is not None:
                self.worker.close()
            self.pool.shutdown(wait=True, cancel_futures=True)

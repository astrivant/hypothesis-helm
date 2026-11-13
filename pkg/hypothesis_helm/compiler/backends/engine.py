"""
Own optional native runtimes, immutable plan buffers and bounded ordered results.
"""

from __future__ import annotations

import importlib
import logging
import time
from collections.abc import Callable
from typing import Protocol

import numpy as np
from attrs import frozen
from numpy.typing import NDArray

from hypothesis_helm.compiler.backends.kernel import evaluate_lane
from hypothesis_helm.compiler.backends.model import INT64_MAX, Plan, State
from hypothesis_helm.exceptions.backends import BackendError, BackendUnavailable, InvalidPlan

__all__ = ("Batch", "Engine", "Prepared", "prepare")

LOGGER = logging.getLogger(__name__)
Array = NDArray[np.int64]


@frozen
class Batch:
    """
    Return ordered pure results with transfer-inclusive timing and provenance.

    Attributes:
        ids (tuple[int, ...]): Input assignment IDs in unchanged order.
        states (tuple[State, ...]): Exact or unknown input predicates.
        seconds (float): Packing, execution, synchronization and decoding duration.
    """

    ids: tuple[int, ...]
    states: tuple[State, ...]
    seconds: float


class Engine(Protocol):
    """
    Own preparation and compute buffers without chart, callback or coverage authority.

    Attributes:
        device (str): Observed device kind or host route.
    """

    device: str

    def evaluate(self, ids: tuple[int, ...], choices: tuple[tuple[int, ...], ...] = ()) -> Batch:
        """
        Evaluate one admitted batch synchronously and preserve ordering.

        Args:
            ids (tuple[int, ...]): Compact assignment IDs or stable row sequence IDs.
            choices (tuple[tuple[int, ...], ...]): Validated dictionary indices for row encoding.

        Returns:
            Batch: Completed predicate results, not completed chart tests.
        """
        ...

    def close(self) -> None:
        """
        Release only this engine's owned allocations.

        Returns:
            None: Further evaluation is prohibited.
        """
        ...


class Prepared:
    """
    Share bounded packing and decoding between reference, CPU and GPU adapters.
    """

    def __init__(self, plan: Plan, backend: str) -> None:
        """
        Validate before creating native arrays or loading optional compilers.

        Args:
            plan (Plan): Immutable validated program.
            backend (str): Explicit reference, cpu-vector or gpu selection.

        """
        plan.validate()
        self.plan = plan
        self.closed = False
        self.backend = backend
        self.device = "cpu" if backend == "cpu-vector" else "reference"
        entries: list[int] = []
        rows: list[tuple[int, int, int, int]] = []
        for node in plan.nodes:
            values = node.table or node.operands
            rows.append((int(node.op), len(entries), len(values), node.factor))
            entries.extend(values)
        self.nodes = np.asarray(rows, dtype=np.int64)
        self.entries = np.asarray(entries, dtype=np.int64)
        stride = 1
        factors = []
        for factor in reversed(plan.factors):
            factors.append((factor.radix, stride))
            stride = stride * factor.radix if plan.encoding == "mixed-radix-i64" else 1
        self.factors = np.asarray(list(reversed(factors)), dtype=np.int64).reshape((-1, 2))
        self.plan_bytes = self.nodes.nbytes + self.entries.nbytes + self.factors.nbytes
        self.native: Callable[[Array, Array, Array, Array, Array, Array, Array, int], None] | None = None
        self.gpu: Engine | None = None
        if self.plan_bytes * 2 >= plan.limits.memory_bytes:
            raise InvalidPlan("plan buffers exceed memory admission limit")
        if backend == "cpu-vector":
            try:
                numba = importlib.import_module("numba")
                lane_kernel = numba.njit(cache=False, fastmath=False)(evaluate_lane)

                def cpu_kernel(
                    ids: Array, nodes: Array, entries: Array, factors: Array, choices: Array, scratch: Array, output: Array, root: int
                ) -> None:
                    """
                    Execute a packed batch with a single nopython call.

                    Args:
                        ids (Array): Ordered assignments.
                        nodes (Array): Immutable graph.
                        entries (Array): Graph operands.
                        factors (Array): Mixed-radix dictionary metadata.
                        choices (Array): Explicit indices or zero-width compact mode.
                        scratch (Array): Per-lane scratch.
                        output (Array): Caller-owned result states.
                        root (int): Result node.

                    Returns:
                        None: Writes only scratch and output.
                    """
                    for lane in range(len(ids)):
                        output[lane] = lane_kernel(ids[lane], lane, nodes, entries, factors, choices, scratch, root)

                self.native = numba.njit(cache=False, fastmath=False, nogil=True)(cpu_kernel)
            except ImportError as exc:
                raise BackendUnavailable("cpu-vector requires hypothesis-helm[cpu]") from exc
        elif backend == "gpu":
            try:
                module = importlib.import_module("hypothesis_helm.compiler.backends.gpu")
                self.gpu = module.TensorEngine(self)
                self.device = self.gpu.device
            except ImportError as exc:
                raise BackendUnavailable("gpu requires hypothesis-helm[gpu] and a physical CUDA or Metal device") from exc
        elif backend != "reference":
            raise ValueError("execution backend must be reference, cpu-vector or gpu")

    def evaluate(self, ids: tuple[int, ...], choices: tuple[tuple[int, ...], ...] = ()) -> Batch:
        """
        Check all indices and byte estimates before invoking native code.

        Args:
            ids (tuple[int, ...]): Ordered nonnegative assignment or row IDs.
            choices (tuple[tuple[int, ...], ...]): Explicit dictionary indices for row encoding.

        Returns:
            Batch: Synchronized, checked results in input order.
        """
        if self.closed:
            raise BackendError("backend is closed")
        if len(ids) > self.plan.limits.batch_size or any(
            type(value) is not int or not 0 <= value < (self.plan.cardinality if self.plan.encoding == "mixed-radix-i64" else INT64_MAX)
            for value in ids
        ):
            raise InvalidPlan("invalid assignment ID or batch size")
        if self.plan.encoding == "dictionary-rows":
            if len(choices) != len(ids) or any(
                len(row) != len(self.plan.factors)
                or any(
                    type(value) is not int or not 0 <= value < factor.radix for value, factor in zip(row, self.plan.factors, strict=True)
                )
                for row in choices
            ):
                raise InvalidPlan("invalid dictionary row width or choice index")
        elif choices:
            raise InvalidPlan("compact-ID plans do not accept dictionary rows")
        # Tensor operations need temporary vectors in addition to graph scratch and input rows.
        temporary_vectors = 16 if self.gpu is not None else 0
        required = self.plan_bytes * 2 + len(ids) * (len(self.nodes) + len(self.factors) + 2 + temporary_vectors) * 8 * 2
        if required > self.plan.limits.memory_bytes:
            raise MemoryError("batch exceeds configured host/device buffer budget")
        if self.gpu is not None:
            return self.gpu.evaluate(ids, choices)
        started = time.monotonic()
        scratch = np.empty((len(ids), len(self.nodes)), dtype=np.int64)
        output = np.empty(len(ids), dtype=np.int64)
        packed = np.asarray(ids, dtype=np.int64)
        rows = np.asarray(choices, dtype=np.int64).reshape((len(ids), len(self.factors) if choices else 0))
        if self.native is not None:
            self.native(packed, self.nodes, self.entries, self.factors, rows, scratch, output, self.plan.root)
        else:
            for lane, number in enumerate(ids):
                output[lane] = evaluate_lane(number, lane, self.nodes, self.entries, self.factors, rows, scratch, self.plan.root)
        return Batch(ids, tuple(State(int(value)) for value in output), time.monotonic() - started)

    def close(self) -> None:
        """
        Release plan references and GPU allocations without resetting a shared device.

        Returns:
            None: Repeated closure is safe.
        """
        if self.gpu is not None:
            self.gpu.close()
            self.gpu = None
        self.closed = True


def prepare(plan: Plan, backend: str) -> Engine:
    """
    Prepare an explicit engine and log bounded capability diagnostics.

    Args:
        plan (Plan): Immutable finite plan.
        backend (str): Explicit reference, cpu-vector or gpu selection.

    Returns:
        Engine: Owned adapter requiring close after use.
    """
    LOGGER.info("Preparing backend=%s nodes=%d factors=%d", backend, len(plan.nodes), len(plan.factors))
    return Prepared(plan, backend)

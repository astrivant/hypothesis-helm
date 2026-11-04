"""
Keep plan arrays resident in one owned CUDA context and synchronize bounded batches.
"""

from __future__ import annotations

import importlib
import time
from typing import TYPE_CHECKING

import numpy as np

from hypothesis_helm.compiler.backends.engine import Array, Batch
from hypothesis_helm.compiler.backends.kernel import evaluate_lane
from hypothesis_helm.compiler.backends.model import State
from hypothesis_helm.environment import env
from hypothesis_helm.exceptions.backends import BackendUnavailable

if TYPE_CHECKING:
    from hypothesis_helm.compiler.backends.engine import Prepared

__all__ = ("CudaEngine",)

# The extension has no typing metadata. Keep its dynamic API confined to this adapter.
cuda = importlib.import_module("numba.cuda")
lane_kernel = cuda.jit(device=True, fastmath=False)(evaluate_lane)


def batch_kernel(
    ids: Array, nodes: Array, entries: Array, factors: Array, choices: Array, scratch: Array, output: Array, root: int
) -> None:
    """
    Execute one disjoint candidate per CUDA lane using validated integer buffers.

    Args:
        ids (Array): Ordered assignment IDs.
        nodes (Array): Resident graph rows.
        entries (Array): Resident table/operand entries.
        factors (Array): Resident radix/stride pairs.
        choices (Array): Explicit factor indices or zero-width compact mode.
        scratch (Array): Disjoint per-lane state rows.
        output (Array): One state per candidate.
        root (int): Root node index.

    Returns:
        None: Each live lane writes only its own scratch and output.
    """
    lane = cuda.grid(1)
    if lane < len(ids):
        output[lane] = lane_kernel(ids[lane], lane, nodes, entries, factors, choices, scratch, root)


compiled_batch = cuda.jit(fastmath=False)(batch_kernel)


class CudaEngine:
    """
    Retain immutable graph tables while limiting temporary allocations per batch.
    """

    def __init__(self, prepared: Prepared) -> None:
        """
        Require a real CUDA device and upload admitted immutable arrays once.

        Args:
            prepared (Prepared): Validated host buffers and allocation limits.

        """
        if env.get("NUMBA_ENABLE_CUDASIM") == "1" or not cuda.is_available():
            raise BackendUnavailable("gpu requires a physical CUDA device; simulation is not GPU validation")
        self.prepared = prepared
        self.nodes = cuda.to_device(prepared.nodes)
        self.entries = cuda.to_device(prepared.entries)
        self.factors = cuda.to_device(prepared.factors)

    def evaluate(self, ids: tuple[int, ...], choices: tuple[tuple[int, ...], ...] = ()) -> Batch:
        """
        Include transfers and device synchronization in the reported stage time.

        Args:
            ids (tuple[int, ...]): Validated ordered assignments.
            choices (tuple[tuple[int, ...], ...]): Explicit indices for row-encoded plans.

        Returns:
            Batch: Synchronized predicate results in input order.
        """
        started = time.monotonic()
        if not ids:
            return Batch((), (), 0.0)
        plan = self.prepared.plan
        device_ids = cuda.to_device(np.asarray(ids, dtype=np.int64))
        rows = np.asarray(choices, dtype=np.int64).reshape((len(ids), len(plan.factors) if choices else 0))
        device_choices = cuda.to_device(rows)
        scratch = cuda.device_array((len(ids), len(plan.nodes)), dtype=np.int64)
        output = cuda.device_array(len(ids), dtype=np.int64)
        compiled_batch[(len(ids) + 127) // 128, 128](
            device_ids, self.nodes, self.entries, self.factors, device_choices, scratch, output, plan.root
        )
        host = output.copy_to_host()
        cuda.synchronize()
        return Batch(ids, tuple(State(int(value)) for value in host), time.monotonic() - started)

    def close(self) -> None:
        """
        Drop owned buffers; the worker process owns final context cleanup.

        Returns:
            None: No shared device reset or unrelated process termination occurs.
        """
        self.nodes = self.entries = self.factors = None

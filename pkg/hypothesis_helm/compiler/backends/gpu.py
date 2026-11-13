"""
Evaluate bounded predicate graphs on a physical device using PyTorch tensors.
"""

from __future__ import annotations

import importlib
import time
from typing import TYPE_CHECKING

import numpy as np

from hypothesis_helm.compiler.backends.engine import Batch
from hypothesis_helm.compiler.backends.model import Opcode, State
from hypothesis_helm.environment import env
from hypothesis_helm.exceptions.backends import BackendUnavailable

if TYPE_CHECKING:
    from hypothesis_helm.compiler.backends.engine import Prepared

__all__ = ("TensorEngine",)

# Confine PyTorch's optional, dynamically loaded API to the device adapter.
torch = importlib.import_module("torch")


class TensorEngine:
    """
    Retain immutable lookup tables and compute ordered integer states on a GPU.
    """

    def __init__(self, prepared: Prepared) -> None:
        """
        Select a physical CUDA or Metal device and stage the admitted tables.

        Args:
            prepared (Prepared): Validated host buffers and allocation limits.

        Raises:
            BackendUnavailable: No supported physical device is available, or Metal fallback is enabled.
        """
        if torch.cuda.is_available():
            self.device = "cuda"
        elif torch.backends.mps.is_available() and env.get("PYTORCH_ENABLE_MPS_FALLBACK") != "1":
            self.device = "mps"
        else:
            raise BackendUnavailable("gpu requires a physical CUDA or Metal device without CPU fallback")
        self.prepared = prepared
        self.entries = torch.as_tensor(prepared.entries, dtype=torch.int64, device=self.device)

    def evaluate(self, ids: tuple[int, ...], choices: tuple[tuple[int, ...], ...] = ()) -> Batch:
        """
        Execute each graph node over the admitted batch and synchronize its results.

        Args:
            ids (tuple[int, ...]): Validated ordered assignment or row IDs.
            choices (tuple[tuple[int, ...], ...]): Explicit indices for row-encoded plans.

        Returns:
            Batch: Transfer-inclusive, ordered predicate states.

        Raises:
            MemoryError: The device cannot allocate the admitted batch.
        """
        started = time.monotonic()
        if not ids:
            return Batch((), (), 0.0)
        plan = self.prepared.plan
        try:
            numbers = torch.as_tensor(np.asarray(ids, dtype=np.int64), device=self.device)
            rows = torch.as_tensor(
                np.asarray(choices, dtype=np.int64).reshape((len(ids), len(plan.factors) if choices else 0)), device=self.device
            )
            scratch = torch.empty((len(plan.nodes), len(ids)), dtype=torch.int64, device=self.device)
            for index, node in enumerate(plan.nodes):
                # Each node consumes only earlier rows, preserving the validated graph order.
                if node.op == Opcode.CONSTANT:
                    scratch[index].fill_(int(node.table[0]))
                elif node.op == Opcode.LOOKUP:
                    factor = self.prepared.factors[node.factor]
                    selected = (
                        rows[:, node.factor]
                        if choices
                        else torch.remainder(torch.div(numbers, int(factor[1]), rounding_mode="floor"), int(factor[0]))
                    )
                    offset = int(self.prepared.nodes[index, 1])
                    scratch[index].copy_(self.entries[offset : offset + len(node.table)][selected])
                elif node.op == Opcode.NOT:
                    value = scratch[node.operands[0]]
                    scratch[index].copy_(torch.where(value == 2, 2, 1 - value))
                elif node.op == Opcode.ONE:
                    # Two definite truths decide ONE even when other operands are unknown.
                    true_count = torch.zeros(len(ids), dtype=torch.int64, device=self.device)
                    unknown = torch.zeros(len(ids), dtype=torch.bool, device=self.device)
                    for operand in node.operands:
                        value = scratch[operand]
                        true_count.add_(value == 1)
                        unknown.logical_or_(value == 2)
                    result = torch.where(true_count > 1, 0, torch.where(unknown, 2, (true_count == 1).to(torch.int64)))
                    scratch[index].copy_(result)
                else:
                    # A decisive false or true must survive later unknown operands.
                    conjunction = node.op == Opcode.AND
                    result = torch.full((len(ids),), 1 if conjunction else 0, dtype=torch.int64, device=self.device)
                    for operand in node.operands:
                        value = scratch[operand]
                        if conjunction:
                            result = torch.where(value == 0, 0, torch.where((value == 2) & (result != 0), 2, result))
                        else:
                            result = torch.where(value == 1, 1, torch.where((value == 2) & (result != 1), 2, result))
                    scratch[index].copy_(result)
            result = scratch[plan.root].cpu().tolist()
        except torch.OutOfMemoryError as exc:
            raise MemoryError("GPU allocation failed") from exc
        return Batch(ids, tuple(State(value) for value in result), time.monotonic() - started)

    def close(self) -> None:
        """
        Release this engine's buffers without resetting the shared device.

        Returns:
            None: Owned references are dropped.
        """
        self.entries = None

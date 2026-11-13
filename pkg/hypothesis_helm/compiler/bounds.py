"""
Evaluate component-wise complexity bounds with bounded NumPy buffers.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

if TYPE_CHECKING:
    from hypothesis_helm.compiler.passes.complexity import Component

__all__ = ("BoundEvaluator",)

Array = NDArray[np.int64]
INT64_MAX = int(np.iinfo(np.int64).max)
INT64_MIN = int(np.iinfo(np.int64).min)


class BoundEvaluator:
    """
    Reuse packed component tables and retain exact Python bounds as a fallback.
    """

    def __init__(self, components: Sequence[Component], *, max_memory_bytes: int) -> None:
        """
        Retain immutable evidence and defer array allocation until a second query.

        Args:
            components (Sequence[Component]): Complete component evidence.
            max_memory_bytes (int): Positive budget for estimated NumPy buffers.

        Raises:
            ValueError: The buffer budget is not positive.
        """
        if max_memory_bytes < 1:
            raise ValueError("compiler.max_bound_memory_bytes must be positive")
        self.components = tuple(components)
        self.max_memory_bytes = max_memory_bytes
        self.evaluate: Callable[[dict[int, int]], int] | None = None
        self.numpy_calls = 0
        self.python_calls = 0
        self.fallback_reason: str | None = None
        self.root_bound: int | None = None

    def prepare(self) -> None:
        """
        Pack valid component cases once after checking the integer and buffer bounds.

        Returns:
            None: A reusable evaluator is installed, or Python remains authoritative.
        """
        from hypothesis_helm.compiler.passes.complexity import bound

        # An unrestricted bound dominates every partial assignment. It also proves
        # that each nonnegative fixed-width sum and final product can fit in int64.
        upper = self.root_bound if self.root_bound is not None else bound(self.components, {})
        if not self.components or upper < 0:
            self.fallback_reason = "no packable component cases"
            return
        if upper > INT64_MAX:
            self.fallback_reason = "bound exceeds NumPy's exact integer range"
            return

        row_count = 0
        depth = 0
        factor_counts: dict[int, int] = {}
        for component in self.components:
            if len(set(component.factors)) != len(component.factors):
                self.fallback_reason = "component repeats a factor"
                return
            valid = [case for case in component.cases if case.resources is not None]
            if not valid:
                self.fallback_reason = "component has no valid cases"
                return
            row_count += len(valid)
            for factor in component.factors:
                factor_counts[factor] = factor_counts.get(factor, 0) + len(valid)
            for case in valid:
                if len(case.choices) != len(component.factors) or any(
                    not isinstance(value, int) or value < INT64_MIN or value > INT64_MAX for value in case.choices
                ):
                    self.fallback_reason = "component choices exceed NumPy's exact integer range"
                    return
                if any(not isinstance(value, int) or value < 0 or value > INT64_MAX for value in case.levels):
                    self.fallback_reason = "component levels are outside the nonnegative integer domain"
                    return
                depth = max(depth, len(case.levels))

        # Include resident arrays, the masked table, grouped maxima, assignment
        # masks and index temporaries before making any potentially large allocation.
        entries = sum(factor_counts.values())
        estimated = (
            16 * row_count * depth
            + 8 * len(self.components) * depth
            + 16 * entries
            + 24 * row_count
            + 16 * len(self.components)
            + 8 * depth
        )
        if estimated > self.max_memory_bytes:
            self.fallback_reason = "NumPy buffers exceed the configured memory budget"
            return

        starts = np.empty(len(self.components), dtype=np.int64)
        depths = np.empty(row_count, dtype=np.int64)
        levels = np.zeros((row_count, depth), dtype=np.int64)
        # Factors used by every component already follow row order and need no index gather.
        indices = {factor: np.empty(count, dtype=np.int64) for factor, count in factor_counts.items() if count != row_count}
        values = {factor: np.empty(count, dtype=np.int64) for factor, count in factor_counts.items()}
        offsets = dict.fromkeys(factor_counts, 0)
        row = 0
        for index, component in enumerate(self.components):
            starts[index] = row
            for case in component.cases:
                if case.resources is None:
                    continue
                depths[row] = len(case.levels)
                levels[row, : len(case.levels)] = case.levels
                for factor, choice in zip(component.factors, case.choices, strict=True):
                    offset = offsets[factor]
                    if factor in indices:
                        indices[factor][offset] = row
                    values[factor][offset] = choice
                    offsets[factor] = offset + 1
                row += 1

        def evaluate(assigned: dict[int, int]) -> int:
            """
            Reduce matching rows by component without changing the pruning bound.

            Args:
                assigned (dict[int, int]): Fixed factor choices for one search branch.

            Returns:
                int: Exact reference bound, or -1 when any component is impossible.
            """
            matching = np.ones(row_count, dtype=np.bool_)
            for factor, choice in assigned.items():
                if factor not in values:
                    continue
                selected = indices.get(factor)
                if choice < INT64_MIN or choice > INT64_MAX:
                    if selected is None:
                        matching.fill(False)
                    else:
                        matching[selected] = False
                elif selected is None:
                    np.logical_and(matching, values[factor] == choice, out=matching)
                else:
                    matching[selected] = matching[selected] & (values[factor] == choice)
            # Every segment has at least one stored row; a fully filtered segment is impossible.
            if not np.logical_or.reduceat(matching, starts).all():
                return -1
            actual_depth = int(np.maximum.reduceat(np.where(matching, depths, 0), starts).max())
            if actual_depth == 0:
                return 0
            maxima = np.maximum.reduceat(np.where(matching[:, None], levels, 0), starts, axis=0)
            totals: Array = maxima.sum(axis=0, dtype=np.int64)
            return int(totals[:actual_depth].max()) * actual_depth

        self.evaluate = evaluate

    def __call__(self, assigned: dict[int, int]) -> int:
        """
        Compute an exact bound and fall back when array preparation or allocation fails.

        Args:
            assigned (dict[int, int]): Shared factor choices fixed by the search branch.

        Returns:
            int: The Python reference bound, including -1 for an impossible component.
        """
        from hypothesis_helm.compiler.passes.complexity import bound

        if self.python_calls and self.fallback_reason is None:
            try:
                if self.evaluate is None:
                    self.prepare()
                if self.evaluate is not None:
                    result = self.evaluate(assigned)
                    self.numpy_calls += 1
                    return result
            except (MemoryError, OverflowError) as error:
                self.fallback_reason = type(error).__name__
                self.evaluate = None
        self.python_calls += 1
        result = bound(self.components, assigned)
        if not assigned:
            self.root_bound = result
        return result

    def report(self) -> dict[str, object]:
        """
        Report actual backend use and bounded fallback diagnostics.

        Returns:
            dict[str, object]: NumPy and Python counts with the configured buffer budget.
        """
        return {
            "engine": "numpy" if self.numpy_calls else "python",
            "numpy_calls": self.numpy_calls,
            "python_calls": self.python_calls,
            "fallback_reason": self.fallback_reason,
            "max_memory_bytes": self.max_memory_bytes,
        }

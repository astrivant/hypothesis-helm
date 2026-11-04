"""
Evaluate total finite Boolean programs with an integer kernel on the CPU.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

__all__ = ("evaluate_lane",)


def evaluate_lane(
    number: int,
    lane: int,
    nodes: NDArray[np.int64],
    entries: NDArray[np.int64],
    factors: NDArray[np.int64],
    choices: NDArray[np.int64],
    scratch: NDArray[np.int64],
    root: int,
) -> int:
    """
    Decode one compact assignment and evaluate its bounded topological predicate graph.

    Operations are total and effect-free. AND/OR short circuit result decoding;
    unknown branches cannot erase an already decisive result. No floating-point
    arithmetic, hashing, callbacks or dynamic allocation occurs inside a lane.

    Args:
        number (int): Validated nonnegative mixed-radix assignment ID.
        lane (int): Disjoint scratch row owned by this candidate.
        nodes (NDArray[np.int64]): Opcode, entry offset, count and factor index rows.
        entries (NDArray[np.int64]): Validated operand indices or finite truth tables.
        factors (NDArray[np.int64]): Radix and right-product stride rows.
        choices (NDArray[np.int64]): Explicit factor indices, or zero columns for compact IDs.
        scratch (NDArray[np.int64]): Bounded caller-owned per-lane intermediate states.
        root (int): Validated result node.

    Returns:
        int: FALSE=0, TRUE=1 or UNKNOWN=2; never chart execution success.
    """
    for index in range(len(nodes)):
        op = nodes[index, 0]
        offset = nodes[index, 1]
        count = nodes[index, 2]
        factor = nodes[index, 3]
        if op == 0:
            result = entries[offset]
        elif op == 1:
            choice = choices[lane, factor] if choices.shape[1] else (number // factors[factor, 1]) % factors[factor, 0]
            result = entries[offset + choice]
        elif op == 4:
            value = scratch[lane, entries[offset]]
            result = 2 if value == 2 else 1 - value
        else:
            true_count = 0
            unknown = False
            result = 1 if op == 2 else 0
            for position in range(count):
                value = scratch[lane, entries[offset + position]]
                if op == 2 and value == 0:
                    result = 0
                    break
                if op == 3 and value == 1:
                    result = 1
                    break
                true_count += 1 if value == 1 else 0
                unknown = unknown or value == 2
            else:
                if op == 5:
                    result = 0 if true_count > 1 else 2 if unknown else int(true_count == 1)
                elif unknown:
                    result = 2
        scratch[lane, index] = result
    return int(scratch[lane, root])

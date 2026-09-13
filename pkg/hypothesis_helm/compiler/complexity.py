"""
Bound the largest rendered manifest tree across a chart's allowed values.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence


def maximum_score(nodes: int) -> int:
    """
    Bound breadth times depth for any tree with N nodes below its synthetic root.

    A deepest path uses D nodes; the other B-1 nodes on its widest level require
    distinct nodes. Thus B+D-1 <= N and B*D <= floor((N+1)^2/4).

    Args:
        nodes (int): Number of non-root nodes, including containers and leaves.

    Returns:
        int: Exact maximum across unrestricted trees of this size; zero for an empty tree.
    """
    if nodes < 0:
        raise ValueError("node count must be nonnegative")
    return (nodes + 1) ** 2 // 4 if nodes else 0


def output_profile(resources: Sequence[object], *, node_limit: int = 100000) -> dict[str, int]:
    """
    Score the rendered forest, counting resource roots, field values and array entries.

    Keys label edges rather than adding extra nodes. Scalars count once regardless
    of text length. Aliases are expanded by occurrence; cyclic output is unsupported.

    Args:
        resources (Sequence[object]): Parsed manifest documents, excluding empty documents.
        node_limit (int): Maximum output nodes inspected before declining analysis.

    Returns:
        dict[str, int]: Measured size, breadth, depth, score and unrestricted size ceiling.
    """
    counts: Counter[int] = Counter()
    pending: list[tuple[object, int, frozenset[int]]] = [(resource, 1, frozenset()) for resource in resources]
    visited = 0
    while pending:
        value, depth, ancestors = pending.pop()
        visited += 1
        if visited > node_limit:
            raise ValueError("manifest tree exceeds the complexity node limit")
        counts[depth] += 1
        if isinstance(value, (dict, list)):
            if id(value) in ancestors:
                raise ValueError("cyclic YAML aliases have no finite expanded tree")
            children = value.values() if isinstance(value, dict) else value
            pending.extend((child, depth + 1, ancestors | {id(value)}) for child in children)
    depth = max(counts, default=0)
    breadth = max(counts.values(), default=0)
    return {"nodes": visited, "breadth": breadth, "depth": depth, "score": breadth * depth, "size_ceiling": maximum_score(visited)}

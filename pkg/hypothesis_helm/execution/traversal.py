"""
Order value-path work reproducibly without changing the selected test population.
"""

import hashlib
import json
from collections.abc import Callable, Sequence
from typing import TypeVar

from hypothesis_helm.schemas.contracts import configuration_key

STRATEGIES = ("random", "linear", "shallow", "deep")
ALGORITHM = "seeded-path-priority-v1"
T = TypeVar("T")


def order_paths(  # noqa: UP047 - pinned pydocstyle 6 cannot parse PEP 695 function type parameters.
    items: Sequence[T],
    path: Callable[[T], tuple[str | int, ...]],
    *,
    strategy: str = "random",
    seed: int = 0,
    identity: Callable[[T], str] | None = None,
) -> list[T]:
    """
    Schedule paths by seeded priority, original order, or increasing/decreasing depth.

    Random priorities depend on path identity rather than collection position, so
    sharding and cached exclusions preserve the relative order of remaining paths.
    Depth ties retain collection order. The caller's sequence is never mutated.

    Args:
        items (Sequence[T]): Selected work, in its original linear order.
        path (Callable[[T], tuple[str | int, ...]]): Typed YAML path for each item.
        strategy (str): Random, linear, shallow, or deep traversal.
        seed (int): Existing invocation seed, including zero and negative integers.
        identity (Callable[[T], str] | None): Optional disambiguator for shared paths.

    Returns:
        list[T]: Every selected item exactly once, in the requested traversal order.
    """
    if strategy not in STRATEGIES:
        raise ValueError(f"traversal_strategy must be one of {', '.join(STRATEGIES)}")
    if strategy == "linear":
        return list(items)
    if strategy in {"shallow", "deep"}:
        direction = 1 if strategy == "shallow" else -1
        return sorted(items, key=lambda item: direction * len(path(item)))

    def priority(item: T) -> bytes:
        """
        Derive a stable random priority without consuming the generation RNG.

        Args:
            item (T): One selected path test.

        Returns:
            bytes: Seeded digest used solely for execution ordering.
        """
        encoded = json.dumps([ALGORITHM, seed, path(item), identity(item) if identity else ""], ensure_ascii=True)
        return hashlib.sha256(encoded.encode()).digest()

    return sorted(items, key=priority)


def order_configurations(
    values: Sequence[dict[str, object]],
    effective: Callable[[dict[str, object]], dict[str, object]],
    defaults: dict[str, object],
    *,
    strategy: str = "random",
    seed: int = 0,
) -> list[dict[str, object]]:
    """
    Reorder retained finite cases using their identity or changed-field depth.

    Unlike path properties, joint configurations necessarily revisit fields.
    Shallow prioritizes the shallowest changed field, deep the deepest changed
    field; ties retain planner order. The baseline is scheduled separately.

    Args:
        values (Sequence[dict[str, object]]): Unique finite cases after all selection filters.
        effective (Callable[[dict[str, object]], dict[str, object]]): Merge an override with defaults.
        defaults (dict[str, object]): Fixed baseline for comparing changed field depth.
        strategy (str): Random, linear, shallow, or deep traversal.
        seed (int): Reproducible configuration-order seed.

    Returns:
        list[dict[str, object]]: The same retained configurations in execution order.
    """
    if strategy in {"random", "linear"}:
        return order_paths(values, lambda value: (), strategy=strategy, seed=seed, identity=configuration_key)
    if strategy not in STRATEGIES:
        raise ValueError(f"traversal_strategy must be one of {', '.join(STRATEGIES)}")

    def depths(value: object, baseline: object, depth: int = 0) -> list[int]:
        """
        Find changed leaf or container depths without flattening dotted YAML keys.

        Args:
            value (object): Current effective subtree.
            baseline (object): Original subtree at the same position.
            depth (int): Number of YAML path segments traversed.

        Returns:
            list[int]: Depths of changes, including added or removed containers.
        """
        if type(value) is type(baseline) and value == baseline:
            return []
        if isinstance(value, dict) and isinstance(baseline, dict):
            result = []
            for key in value.keys() | baseline.keys():
                if key not in value or key not in baseline:
                    result.append(depth + 1)
                else:
                    result.extend(depths(value[key], baseline[key], depth + 1))
            return result
        if isinstance(value, list) and isinstance(baseline, list) and len(value) == len(baseline):
            return [item for left, right in zip(value, baseline, strict=True) for item in depths(left, right, depth + 1)]
        return [depth]

    def priority(value: dict[str, object]) -> int:
        """
        Rank a joint configuration by its relevant changed-field depth.

        Args:
            value (dict[str, object]): Retained configuration override.

        Returns:
            int: Ascending shallow rank or descending deep rank.
        """
        changed = depths(effective(value), defaults) or [0]
        return min(changed) if strategy == "shallow" else -max(changed)

    return sorted(values, key=priority)

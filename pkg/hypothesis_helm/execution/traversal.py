"""
Order value-path work reproducibly without changing the selected test population.
"""

import hashlib
import json
from collections.abc import Callable, Sequence
from typing import TypeVar

from hypothesis_helm.schemas.contracts import configuration_key
from hypothesis_helm.schemas.replay import select

STRATEGIES = ("random", "linear", "root-first", "leaf-first")
ALGORITHM = "seeded-path-priority-v1"
T = TypeVar("T")


def validate_strategy(strategy: str) -> str:
    """
    Validate the requested traversal spelling without compatibility aliases.

    Args:
        strategy (str): Requested traversal name.

    Returns:
        str: Canonical name used in scheduling, reports, and worker environments.
    """
    if strategy not in STRATEGIES:
        raise ValueError(f"traversal_strategy must be one of {', '.join(STRATEGIES)}")
    return strategy


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
        strategy (str): Random, linear, root-first, or leaf-first traversal.
        seed (int): Existing invocation seed, including zero and negative integers.
        identity (Callable[[T], str] | None): Optional disambiguator for shared paths.

    Returns:
        list[T]: Every selected item exactly once, in the requested traversal order.
    """
    strategy = validate_strategy(strategy)
    if strategy == "linear":
        return list(items)
    if strategy in {"root-first", "leaf-first"}:
        direction = 1 if strategy == "root-first" else -1
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
) -> Sequence[dict[str, object]]:
    """
    Reorder retained finite cases using their identity or changed-field depth.

    Unlike path properties, joint configurations necessarily revisit fields.
    Root-first prioritizes the shallowest changed field, leaf-first the deepest changed
    field; ties retain planner order. The baseline is scheduled separately.

    Args:
        values (Sequence[dict[str, object]]): Unique finite cases after all selection filters.
        effective (Callable[[dict[str, object]], dict[str, object]]): Merge an override with defaults.
        defaults (dict[str, object]): Fixed baseline for comparing changed field depth.
        strategy (str): Random, linear, root-first, or leaf-first traversal.
        seed (int): Reproducible configuration-order seed.

    Returns:
        Sequence[dict[str, object]]: The same retained configurations in execution order.
    """
    strategy = validate_strategy(strategy)
    if strategy == "linear":
        return values
    if strategy == "random":
        return select(
            values,
            order_paths(
                range(len(values)), lambda index: (), strategy=strategy, seed=seed, identity=lambda index: configuration_key(values[index])
            ),
        )

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
        return min(changed) if strategy == "root-first" else -max(changed)

    return select(values, sorted(range(len(values)), key=lambda index: priority(values[index])))

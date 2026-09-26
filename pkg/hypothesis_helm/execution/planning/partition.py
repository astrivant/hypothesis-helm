"""Record deterministic ownership of work within each recursively discovered chart."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence

from attrs import define, field

from hypothesis_helm.integrations.sharding import Shard

__all__ = ("Partition", "digest")


def digest(value: object) -> str:
    """
    Hash portable JSON evidence independently of workspace paths.

    Args:
        value (object): JSON-compatible selection or configuration.

    Returns:
        str: SHA-256 digest of its canonical serialization.
    """
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@define
class Partition:
    """
    Keep inventory, ownership and execution evidence separate.

    Attributes:
        shard (Shard): This process's partition coordinates.
        units (dict[str, str]): Work identifiers mapped to ownership keys; a failure region shares one key.
        initial (list[str]): Globally retained work before conditional failure expansion.
        visited (list[str]): Assigned units whose execution was entered.
        completed (list[str]): Assigned units which returned or produced a chart finding.
    """

    shard: Shard
    units: dict[str, str]
    initial: list[str]
    visited: list[str] = field(factory=list)
    completed: list[str] = field(factory=list)

    def owns(self, unit: str) -> bool:
        """
        Determine ownership without depending on traversal order or local worker count.

        Args:
            unit (str): Work identifier in the common inventory.

        Returns:
            bool: Whether this shard owns the unit's entire failure region.
        """
        return self.shard.includes(self.units[unit])

    def report(self) -> dict[str, object]:
        """
        Export self-contained evidence for offline aggregation.

        Returns:
            dict[str, object]: Selection and completion data, including valid empty partitions.
        """
        selected = [unit for unit in self.initial if self.owns(unit)]
        return {
            "index": self.shard.index,
            "total": self.shard.total,
            "units": self.units,
            "initial": self.initial,
            "inventory_digest": digest([self.units, self.initial]),
            "selected": selected,
            "visited": self.visited,
            "completed": self.completed,
            "complete": set(selected) <= set(self.completed) and set(self.visited) == set(self.completed),
        }

    @classmethod
    def paths(cls, shard: Shard, paths: Sequence[Sequence[str | int]]) -> Partition:
        """
        Assign each retained path property to exactly one shard.

        Args:
            shard (Shard): Current partition coordinates.
            paths (Sequence[Sequence[str | int]]): Unique paths after input filtering and sampling.

        Returns:
            Partition: Order-independent ownership with stable path identifiers.
        """
        keys = [digest(list(path)) for path in paths]
        return cls(shard, dict(zip(keys, keys, strict=True)), keys)

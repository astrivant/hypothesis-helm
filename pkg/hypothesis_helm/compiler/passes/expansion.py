"""
Schedule omitted members of failed symbolic regions without inferring their test outcomes.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

from attrs import define, field

from hypothesis_helm.compiler.passes.topology import trim_topology
from hypothesis_helm.schemas.contracts import configuration_key


@define
class FailureExpansion:
    """
    Track a finite selection and add untested region members after an observed failure.

    Attributes:
        groups (dict[str, list[int]]): Ordered member indices for supported symbolic regions.
        membership (dict[int, str]): Region identity for each classified input.
        scheduled (set[int]): Inputs already selected or scheduled for expansion.
        added (list[int]): Additional inputs in deterministic scheduling order.
    """

    groups: dict[str, list[int]]
    membership: dict[int, str]
    scheduled: set[int]
    added: list[int] = field(factory=list)

    @classmethod
    def build(
        cls,
        chart: Path,
        defaults: dict[str, object],
        values: Sequence[dict[str, object]],
        effective: Sequence[dict[str, object]],
        selected: list[int],
        *,
        fixed_names: bool = True,
    ) -> FailureExpansion:
        """
        Classify the existing finite plan with the same partitioner used by topology trimming.

        Args:
            chart (Path): Chart templates supplying the static regions.
            defaults (dict[str, object]): Fixed chart defaults.
            values (Sequence[dict[str, object]]): Distinct finite overrides including the baseline.
            effective (Sequence[dict[str, object]]): Corresponding merged values.
            selected (list[int]): Indices retained before expansion.
            fixed_names (bool): Whether renderer names meet the static partition contract.

        Returns:
            FailureExpansion: Scheduler that leaves unsupported inputs unclassified.
        """
        identities: dict[str, str] = {}
        trim_topology(
            chart,
            defaults,
            values,
            effective,
            0,
            0,
            fixed_names=fixed_names,
            memberships=identities,
        )
        membership = {
            index: identities[configuration_key(value)] for index, value in enumerate(values) if configuration_key(value) in identities
        }
        groups: dict[str, list[int]] = defaultdict(list)
        for index, identity in membership.items():
            groups[identity].append(index)
        return cls(dict(groups), membership, set(selected))

    def failed(self, index: int) -> list[int]:
        """
        Schedule every omitted member of this region once after a real test failure.

        Args:
            index (int): Index of the input whose execution failed.

        Returns:
            list[int]: Newly scheduled indices; no outcomes are inferred from membership.
        """
        identity = self.membership.get(index)
        added = [member for member in self.groups.get(identity, []) if member not in self.scheduled] if identity is not None else []
        self.scheduled.update(added)
        self.added.extend(added)
        return added

"""
Select reproducible random subsets with explicit sample floors and protected cases.
"""

import hashlib
import math
from collections.abc import Callable, Sequence
from typing import TypeVar

from attrs import frozen

from hypothesis_helm.schemas.replay import select as select_indices

T = TypeVar("T")
ENVIRONMENT = "HYPOTHESIS_HELM_SAMPLING"
REPORT = "HYPOTHESIS_HELM_SAMPLING_REPORT"


@frozen
class Sampling:
    """
    Configure optional sampling without claiming a bug-recall guarantee.

    Attributes:
        percent (float): Percentage of eligible cases to retain; 100 disables sampling.
        minimum (int): Minimum retained sample, or all cases when fewer exist.
        aggressive (bool): Request per-chart calibrated selection after ordinary filtering.
        calibration (str | None): Optional replacement for the packaged calibration evidence.
    """

    percent: float = 100.0
    minimum: int = 128
    aggressive: bool = False
    calibration: str | None = None

    def __attrs_post_init__(self) -> None:
        """
        Reject invalid percentages and floors before planning or execution.

        Returns:
            None: Sampling settings are finite and positive.
        """
        if not math.isfinite(self.percent) or not 0 < self.percent <= 100:
            raise ValueError("--sample-random must be greater than 0 and at most 100 (percentage retained)")
        if type(self.minimum) is not int or self.minimum < 1:
            raise ValueError("--sample-min-cases must be a positive integer")

    def select(  # noqa: UP047 - pinned pydocstyle cannot parse PEP 695 type parameters.
        self,
        values: Sequence[T],
        key: Callable[[T], str],
        seed: int,
        *,
        protected: set[str] | None = None,
        fields: Callable[[T], set[str]] | None = None,
        minimum_fields: int = 0,
    ) -> tuple[Sequence[T], dict[str, object]]:
        """
        Sample without replacement, preserving input order and mandatory representatives.

        Args:
            values (Sequence[T]): Eligible cases after preceding filters.
            key (Callable[[T], str]): Unique stable identity independent of traversal and shard.
            seed (int): Reproducible selection seed.
            protected (set[str] | None): Identities that must survive sampling.
            fields (Callable[[T], set[str]] | None): Distinct changed paths exercised by a case.
            minimum_fields (int): Minimum distinct paths across the retained cases.

        Returns:
            tuple[Sequence[T], dict[str, object]]: Selected cases and explicit omission statistics.
        """
        if minimum_fields < 0 or (minimum_fields and fields is None):
            raise ValueError("a field floor requires nonnegative coverage and a path mapping")
        identities = [key(value) for value in values]
        if len(set(identities)) != len(identities):
            raise ValueError("sampling requires unique case identities")
        required = set(identities) & (protected or set())
        count = min(len(values), max(self.minimum, math.ceil(len(values) * self.percent / 100), len(required)))
        selected = values
        if count < len(values):
            ranked = sorted(
                (identity for identity in identities if identity not in required),
                key=lambda identity: (hashlib.sha256(f"sample-v1:{seed}:{identity}".encode()).digest(), identity),
            )
            retained = required | set(ranked[: count - len(required)])
            if fields is not None and minimum_fields:
                by_key = {identity: index for index, identity in enumerate(identities)}
                covered: set[str] = set()
                for identity in retained:
                    covered.update(fields(values[by_key[identity]]))
                for identity in ranked[count - len(required) :]:
                    if len(covered) >= minimum_fields:
                        break
                    retained.add(identity)
                    covered.update(fields(values[by_key[identity]]))
                count = len(retained)
            selected = select_indices(values, [index for index, identity in enumerate(identities) if identity in retained])
        report: dict[str, object] = {
            "algorithm": "sha256-identity-sample-v1",
            "percent": self.percent,
            "minimum": self.minimum,
            "seed": seed,
            "eligible": len(values),
            "retained": count,
            "omitted": len(values) - count,
            "protected": len(required),
            "applied": count < len(values),
            "bug_recall_guaranteed": False,
        }
        if fields is not None:
            covered_fields: set[str] = set()
            for value in selected:
                covered_fields.update(fields(value))
            selected_fields = len(covered_fields)
            report.update(minimum_fields=minimum_fields, selected_fields=selected_fields, field_floor_met=selected_fields >= minimum_fields)
        return selected, report


DEFAULT_SAMPLING = Sampling()

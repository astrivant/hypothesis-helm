"""
Partition properties deterministically across independent runner instances.
"""

import argparse
import hashlib
from collections.abc import Mapping

from attrs import frozen


@frozen
class CIProvider:
    """
    Describe the environment keys and indexing convention for a CI provider.

    Attributes:
        name (str): Human-readable provider name used in diagnostics.
        index_key (str): Environment key containing this job's index.
        total_key (str): Environment key containing the number of jobs.
        index_base (int): Provider's first job index, zero or one.
        allow_missing_single_index (bool): Accept a missing index when total is one.
    """

    name: str
    index_key: str
    total_key: str
    index_base: int = 0
    allow_missing_single_index: bool = False


@frozen
class CircleCI(CIProvider):
    """
    Configure CircleCI's zero-based parallel job coordinates.

    Attributes:
        name (str): CircleCI display name.
        index_key (str): Environment key for the job index.
        total_key (str): Environment key for the job count.
    """

    name: str = "CircleCI"
    index_key: str = "CIRCLE_NODE_INDEX"
    total_key: str = "CIRCLE_NODE_TOTAL"


@frozen
class GitLabCI(CIProvider):
    """
    Configure GitLab's one-based coordinates and nonparallel job defaults.

    Attributes:
        name (str): GitLab display name.
        index_key (str): Environment key for the job index.
        total_key (str): Environment key for the job count.
        index_base (int): One-based job indexing.
        allow_missing_single_index (bool): Accept GitLab's total-only nonparallel jobs.
    """

    name: str = "GitLab CI"
    index_key: str = "CI_NODE_INDEX"
    total_key: str = "CI_NODE_TOTAL"
    index_base: int = 1
    allow_missing_single_index: bool = True


@frozen
class GitHubActions(CIProvider):
    """
    Configure the zero-based GitHub strategy coordinates exported by the action.

    Attributes:
        name (str): GitHub Actions display name.
        index_key (str): Environment key for the job index.
        total_key (str): Environment key for the job count.
    """

    name: str = "GitHub Actions"
    index_key: str = "HYPOTHESIS_HELM_JOB_INDEX"
    total_key: str = "HYPOTHESIS_HELM_JOB_TOTAL"


CI_PROVIDERS: tuple[CIProvider, ...] = (CircleCI(), GitLabCI(), GitHubActions())


@frozen
class Shard:
    """
    Identify one partition of a property suite.

    Attributes:
        index (int): One-based shard index.
        total (int): Number of independent shards.
    """

    index: int
    total: int

    def __attrs_post_init__(self) -> None:
        """
        Reject invalid shard coordinates.

        Returns:
            None: The index is within the positive shard count.
        """
        if not 1 <= self.index <= self.total:
            raise ValueError("shard must satisfy 1 <= INDEX <= TOTAL")

    @property
    def name(self) -> str:
        """
        Return a filesystem-safe identifier for this shard.

        Returns:
            str: Stable artifact directory name.
        """
        return f"{self.index}-of-{self.total}"

    def includes(self, nodeid: str) -> bool:
        """
        Assign a relative pytest node ID to exactly one shard.

        Args:
            nodeid (str): Test identifier relative to the generated suite root.

        Returns:
            bool: Whether this shard owns the property.
        """
        digest = hashlib.sha256(nodeid.encode("utf-8")).digest()
        return int.from_bytes(digest, "big") % self.total == self.index - 1


def parse_shard(value: str) -> Shard:
    """
    Parse a one-based INDEX/TOTAL shard selector.

    Args:
        value (str): Command-line shard coordinates.

    Returns:
        Shard: Validated shard assignment.
    """
    try:
        index, total = value.split("/")
        return Shard(int(index), int(total))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("shard must be INDEX/TOTAL with 1 <= INDEX <= TOTAL") from exc


def parse_shard_option(value: str) -> Shard | str:
    """
    Accept an explicit partition or automatic and disabled detection modes.

    Args:
        value (str): CLI shard option.

    Returns:
        Shard | str: Explicit coordinates, auto, or none.
    """
    return value if value in ("auto", "none") else parse_shard(value)


def resolve_shard(selector: Shard | str, environment: Mapping[str, str]) -> tuple[Shard | None, str]:
    """
    Resolve explicit coordinates or a unique CI environment into a shard.

    Args:
        selector (Shard | str): Explicit coordinates, auto, or none.
        environment (Mapping[str, str]): Environment containing CI node coordinates.

    Returns:
        tuple[Shard | None, str]: Selected partition and the detection source.
    """
    if isinstance(selector, Shard):
        return selector, "explicit"
    if selector == "none":
        return None, "disabled"
    if selector != "auto":
        raise ValueError("shard must be auto, none, or INDEX/TOTAL")
    candidates: list[tuple[Shard | None, str]] = []
    for provider in CI_PROVIDERS:
        index_text = environment.get(provider.index_key, "")
        total_text = environment.get(provider.total_key, "")
        if not index_text and not total_text:
            continue
        # GitLab sets CI_NODE_TOTAL=1 even when CI_NODE_INDEX is absent.
        if provider.allow_missing_single_index and not index_text and total_text == "1":
            candidates.append((None, provider.name))
            continue
        if not index_text or not total_text:
            raise ValueError(f"{provider.name} shard detection requires both {provider.index_key} and {provider.total_key}")
        try:
            index, total = int(index_text), int(total_text)
            shard = Shard(index + (1 - provider.index_base), total)
        except ValueError as exc:
            raise ValueError(f"invalid {provider.name} shard coordinates in {provider.index_key}/{provider.total_key}") from exc
        candidates.append((None if total == 1 else shard, provider.name))
    if len(candidates) > 1:
        raise ValueError("ambiguous CI shard environment; use --shard INDEX/TOTAL or --shard none")
    return candidates[0] if candidates else (None, "local")

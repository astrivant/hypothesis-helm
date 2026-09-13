"""
Compare rendered manifest bundles using process-local, successful-validation hash sets.
"""

import hashlib
import json
import logging
import os
from collections.abc import Callable, Sequence
from pathlib import Path
from threading import RLock
from uuid import uuid4

from attrs import define, field

LOGGER = logging.getLogger(__name__)
STATISTICS_DIRECTORY = "HYPOTHESIS_HELM_RENDER_HASH_STATISTICS"
ALGORITHM = "sha256-canonical-json-v1"


def render_digest(resources: Sequence[object]) -> bytes:
    """
    Hash a complete parsed render, preserving document and array order.

    Args:
        resources (Sequence[object]): Parsed resource documents from one Helm invocation.

    Returns:
        bytes: SHA-256 digest independent of YAML formatting and mapping key order.
    """
    payload = json.dumps(list(resources), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()
    return hashlib.sha256(payload).digest()


@define
class RenderHashes:
    """
    Retain fixed-size digests and reuse only completed successful manifest validation.

    Attributes:
        scope (str): Local lifetime of this index.
        observed (int): Parsed render bundles presented for validation.
        cache_hits (int): Validations reused from a matching successful entry.
        seen (set[bytes]): Output digests observed in this process.
        validated (set[bytes]): Successful output-and-validation-context digests.
        lock (RLock): Serializes check, validation and successful insertion.
    """

    scope: str = "process-local"
    observed: int = 0
    cache_hits: int = 0
    seen: set[bytes] = field(factory=set, repr=False)
    validated: set[bytes] = field(factory=set, repr=False)
    lock: RLock = field(factory=RLock, repr=False)

    def check(self, resources: Sequence[object], context: str, validate: Callable[[], None]) -> None:
        """
        Validate unseen output in this context, committing its digest only after success.

        Args:
            resources (Sequence[object]): Complete parsed manifest bundle.
            context (str): Validation configuration, including schema identity and timeout.
            validate (Callable[[], None]): Resource-envelope and optional Kubernetes checks.

        Returns:
            None: Validation passes or the original failure propagates uncached.
        """
        digest = render_digest(resources)
        validation_key = hashlib.sha256(ALGORITHM.encode() + b"\0" + digest + b"\0" + context.encode()).digest()
        with self.lock:
            self.observed += 1
            self.seen.add(digest)
            if validation_key in self.validated:
                self.cache_hits += 1
                return
            validate()
            self.validated.add(validation_key)

    def snapshot(self) -> dict[str, object]:
        """
        Report counts without exporting hashes or manifest contents.

        Returns:
            dict[str, object]: Observed, unique and repeated output plus validation reuse.
        """
        with self.lock:
            return {
                "algorithm": ALGORITHM,
                "scope": self.scope,
                "observed_bundles": self.observed,
                "unique_bundles": len(self.seen),
                "duplicate_bundles": self.observed - len(self.seen),
                "validation_cache_hits": self.cache_hits,
                "validated_entries": len(self.validated),
            }

    def log_summary(self) -> None:
        """
        Log output reuse separately from input-configuration coverage.

        Returns:
            None: Hash counts and their local scope appear in run diagnostics.
        """
        stats = self.snapshot()
        LOGGER.info(
            "Render hashes (%s): %s observed, %s unique, %s duplicate bundles; %s successful validations reused",
            stats["scope"],
            stats["observed_bundles"],
            stats["unique_bundles"],
            stats["duplicate_bundles"],
            stats["validation_cache_hits"],
        )


_PROCESS_HASHES = RenderHashes()


def process_hashes() -> RenderHashes:
    """
    Return the current worker's in-memory hash index.

    Returns:
        RenderHashes: Index shared by renders within this Python process.
    """
    return _PROCESS_HASHES


def reset_process_hashes() -> None:
    """
    Begin a pytest session without inheriting a previous session's validation results.

    Returns:
        None: Subsequent worker renders use a fresh index.
    """
    global _PROCESS_HASHES
    _PROCESS_HASHES = RenderHashes()


def save_process_statistics(directory: Path) -> None:
    """
    Export only scalar counters for aggregation by the parent runner.

    Args:
        directory (Path): Run-specific temporary statistics directory.

    Returns:
        None: Hashes stay in memory; a process-specific counter file is written atomically.
    """
    stats = process_hashes().snapshot()
    if not stats["observed_bundles"]:
        return
    process_hashes().log_summary()
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{os.getpid()}.json"
    temporary = destination.with_suffix(f".{uuid4().hex}.tmp")
    temporary.write_text(json.dumps(stats) + "\n")
    temporary.replace(destination)


def summarize_process_statistics(directory: Path) -> dict[str, object]:
    """
    Sum worker counters without implying that independent hash sets were shared.

    Args:
        directory (Path): Temporary per-process counter directory.

    Returns:
        dict[str, object]: Worker-local totals; global output uniqueness remains unknown.
    """
    totals = dict.fromkeys(("observed_bundles", "unique_bundles", "duplicate_bundles", "validation_cache_hits"), 0)
    workers = 0
    for path in directory.glob("*.json"):
        try:
            stats = json.loads(path.read_text())
            if not isinstance(stats, dict) or stats.get("algorithm") != ALGORITHM:
                raise ValueError("incompatible render statistics")
            if any(type(stats.get(key)) is not int or stats[key] < 0 for key in totals):
                raise ValueError("invalid render counters")
        except (OSError, ValueError):
            LOGGER.warning("Ignoring invalid render statistics: %s", path)
            continue
        for key in totals:
            totals[key] += stats[key]
        workers += 1
    return {
        "algorithm": ALGORITHM,
        "scope": "worker-process-local",
        "workers_reporting": workers,
        "observed_bundles": totals["observed_bundles"],
        "worker_unique_bundles": totals["unique_bundles"],
        "global_unique_bundles": None,
        "duplicate_bundles": totals["duplicate_bundles"],
        "validation_cache_hits": totals["validation_cache_hits"],
    }

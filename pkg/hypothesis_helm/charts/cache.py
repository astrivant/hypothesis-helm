"""
Reuse completed repository chart tests only after Git and content verification.
"""

import argparse
import hashlib
import json
import logging
import os
import shutil
import time
from pathlib import Path

from attrs import define, field

from hypothesis_helm.charts.changes import chart_changed
from hypothesis_helm.execution.cache import fingerprint, merge_outcomes, read_outcomes

LOGGER = logging.getLogger(__name__)
RETENTION_SECONDS = 21 * 24 * 60 * 60


@define
class ChartCache:
    """
    Own one prepared chart's content key and pre-execution cache snapshot.

    Attributes:
        path (Path | None): Result file, or None when reuse is disabled.
        key (str): Digest of chart bytes, settings, implementation and Helm binary.
        baseline (dict[str, str]): Prior outcomes used for conflict-aware publication.
        reusable (bool): Whether an unchanged chart has a fresh completed success.
        reason (str): Human-readable explanation of the cache decision.
    """

    path: Path | None = None
    key: str = ""
    baseline: dict[str, str] = field(factory=dict)
    reusable: bool = False
    reason: str = "cache disabled"

    @classmethod
    def prepare(cls, chart: Path, original: Path, args: argparse.Namespace, changes: dict[str, object]) -> "ChartCache":
        """
        Hash the isolated chart after dependency preparation and selected-values loading.

        Args:
            chart (Path): Prepared chart including dependency archives and selected values.
            original (Path): Original chart directory used for the Git comparison.
            args (argparse.Namespace): Effective execution options.
            changes (dict[str, object]): Git base and changed paths.

        Returns:
            ChartCache: Cache decision; uncertain validation inputs always force execution.
        """
        if getattr(args, "no_cache", False):
            return cls()
        if any(getattr(args, name, None) is not None for name in ("export_minimal_values", "export_topological_graph")):
            return cls(reason="requested exports require execution")
        # External schema trees and validators have independent lifetimes and caches.
        if os.environ.get("HYPOTHESIS_HELM_CONFORMITY"):
            return cls(reason="external validation requires fresh execution")
        ignored = {
            "directory",
            "chart",
            "artifact_dir",
            "report",
            "cache_dir",
            "base_ref",
            "scan_deadline",
            "scan_timeout",
            "clone_timeout",
            "progress",
            "debug",
            "verbose",
            "command",
        }
        settings = json.dumps({key: value for key, value in vars(args).items() if key not in ignored}, sort_keys=True, default=str)
        try:
            digest = hashlib.sha256(fingerprint(chart, args.seed, settings, "repository").encode())
            binary = shutil.which(args.helm)
            if binary is None:
                return cls(reason="Helm binary unavailable for cache verification")
            digest.update(hashlib.sha256(Path(binary).read_bytes()).digest())
            calibration = getattr(args, "sampling_calibration", None)
            if calibration:
                digest.update(Path(calibration).read_bytes())
            # .Files can read arbitrary chart files; include more than just templates and schemas.
            for item in sorted(chart.rglob("*")):
                if item.is_file():
                    digest.update(item.relative_to(chart).as_posix().encode() + b"\0")
                    digest.update(hashlib.sha256(item.read_bytes()).digest())
            key = digest.hexdigest()
            directory = getattr(args, "cache_dir", None) or Path(".cache/hypothesis-helm/charts")
            path = directory.expanduser().resolve() / f"{key}.json"
            baseline = read_outcomes(path)
            fresh = path.is_file() and 0 <= time.time() - path.stat().st_mtime < RETENTION_SECONDS
            changed = chart_changed(original, changes)
            reusable = not changed and fresh and baseline.get(key) == "passed"
            reason = (
                "unchanged chart with a matching completed success"
                if reusable
                else "chart changed or Git comparison unavailable"
                if changed
                else "no matching completed success within 21 days"
            )
            return cls(path, key, baseline, reusable, reason)
        except (OSError, ValueError) as exc:
            return cls(reason=f"cache verification unavailable: {exc}")

    def publish(self, result: dict[str, object]) -> None:
        """
        Publish success only for completed work; preserve concurrent failures.

        Args:
            result (dict[str, object]): Current chart execution outcome.

        Returns:
            None: Atomic cache publication is best-effort and cannot hide test failures.
        """
        if self.path is None:
            return
        traversal = result.get("traversal", {})
        complete = not isinstance(traversal, dict) or (
            traversal.get("incomplete_paths", 0) == 0
            and traversal.get("remaining_paths", 0) == 0
            and traversal.get("completed_paths", 0) == traversal.get("selected_paths", 0)
        )
        outcome = "passed" if result.get("status") == "passed" and complete else "failed"
        try:
            merge_outcomes(self.path, self.baseline, {self.key: outcome})
        except OSError as exc:
            LOGGER.warning("Could not save chart cache: %s", exc)

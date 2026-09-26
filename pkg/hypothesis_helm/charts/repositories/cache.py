"""
Reuse completed repository chart tests only after Git and content verification.
"""

import argparse
import hashlib
import json
import logging
import shutil
import tempfile
import time
from pathlib import Path

from attrs import define, field

from hypothesis_helm.charts.repositories.changes import chart_changed
from hypothesis_helm.environment import env
from hypothesis_helm.execution.planning.partition import digest as evidence_digest
from hypothesis_helm.execution.state.cache import fingerprint, merge_outcomes, read_outcomes
from hypothesis_helm.schemas.contracts import mapping

__all__ = ("ChartCache", "RETENTION_SECONDS")


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
        cached_result (dict[str, object]): Verified partition evidence restored with a cached success.
    """

    path: Path | None = None
    key: str = ""
    baseline: dict[str, str] = field(factory=dict)
    reusable: bool = False
    reason: str = "cache disabled"
    cached_result: dict[str, object] = field(factory=dict)

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
        if getattr(args, "rerun", "auto") == "all":
            return cls(reason="--rerun all requires fresh execution")
        if getattr(args, "export_suppressions", False) or any(
            getattr(args, name, None) is not None for name in ("export_minimal_values", "export_topological_graph")
        ):
            return cls(reason="requested exports require execution")
        # External schema trees and validators have independent lifetimes and caches.
        if env.get("HYPOTHESIS_HELM_CONFORMITY"):
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
            "run_id",
            "execution",
            "invocation",
        }
        settings = json.dumps({key: value for key, value in vars(args).items() if key not in ignored}, sort_keys=True, default=str)
        try:
            digest = hashlib.sha256(fingerprint(chart, args.seed, settings, "repository").encode())
            binary = shutil.which(args.helm)
            if binary is None:
                return cls(reason="Helm binary unavailable for cache verification")
            # A renderer upgrade invalidates results even when chart files and CLI settings are unchanged.
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
            cached_result: dict[str, object] = {}
            if reusable and getattr(args, "shard", None) is not None:
                # A chart-level pass is insufficient: restore the exact owned work and its completion evidence.
                try:
                    saved = mapping(json.loads(path.with_suffix(".evidence.json").read_text()))
                    cached_result = mapping(saved["result"])
                    reusable = saved.get("checksum") == evidence_digest(cached_result) and bool(
                        mapping(cached_result.get("work_partition", {})).get("complete")
                    )
                except (OSError, ValueError, KeyError):
                    reusable = False
                if not reusable:
                    cached_result = {}
                    reason = "cached success lacks verified shard completion evidence"
            return cls(path, key, baseline, reusable, reason, cached_result)
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
        # A timeout without a finding is incomplete coverage, not a reusable successful scan.
        tested = int(str(result.get("attempts") or 0)) > 0
        if "work_partition" in result:
            complete = complete and bool(mapping(result["work_partition"]).get("complete"))
        outcome = "passed" if result.get("status") == "passed" and complete and tested else "failed"
        try:
            if outcome == "passed" and "work_partition" in result:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                # Publish evidence first, then the outcome under the existing merge lock. Concurrent failures still win.
                with tempfile.NamedTemporaryFile(mode="w", dir=self.path.parent, delete=False) as stream:
                    staged = Path(stream.name)
                    json.dump({"checksum": evidence_digest(result), "result": result}, stream)
                try:
                    staged.replace(self.path.with_suffix(".evidence.json"))
                finally:
                    staged.unlink(missing_ok=True)
            merge_outcomes(self.path, self.baseline, {self.key: outcome})
        except OSError as exc:
            LOGGER.warning("Could not save chart cache: %s", exc)

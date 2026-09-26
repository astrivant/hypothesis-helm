"""Publish portable recursive-shard evidence independently of disposable chart copies."""

import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from hypothesis_helm.execution.planning.partition import digest
from hypothesis_helm.schemas.contracts import mapping, sequence

__all__ = ("chart_digest", "publish_shard")


def chart_digest(chart: Path) -> str:
    """
    Hash chart content, including dependencies and files read through Helm's Files object.

    Args:
        chart (Path): Original or dependency-prepared chart tree.

    Returns:
        str: Identity independent of checkout directory and file timestamps.
    """
    result = hashlib.sha256()
    for path in sorted(chart.rglob("*")):
        relative = path.relative_to(chart)
        if path.is_file() and not {".git", ".cache", "__pycache__"}.intersection(relative.parts):
            result.update(relative.as_posix().encode() + b"\0")
            result.update(hashlib.sha256(path.read_bytes()).digest())
    return result.hexdigest()


def publish_shard(report: dict[str, object], args: argparse.Namespace, output: Path, status: int) -> None:
    """
    Save a self-contained scan result at the shared CI artifact convention.

    Args:
        report (dict[str, object]): Completed or interrupted repository scan evidence.
        args (argparse.Namespace): Effective command options and resolved shard coordinates.
        output (Path): This shard's private artifact directory.
        status (int): Process exit status retained by the aggregation job.

    Returns:
        None: JSON and JUnit files are available even for empty or incomplete partitions.
    """
    settings = {
        key: value
        for key, value in vars(args).items()
        if key
        not in {
            "chart",
            "directory",
            "artifact_dir",
            "report",
            "cache_dir",
            "shard",
            "run_id",
            "scan_deadline",
            "execution",
            "invocation",
            "jobs",
            "log_file",
            "log_color",
            "progress",
            "verbose",
            "debug",
            "helm",
            "config",
            "base_ref",
        }
    }
    # Match settings, not machine-local executable paths. Chart bytes are verified per chart.
    report.update(
        report_kind="repository-shard-v1",
        run_id=getattr(args, "run_id", None),
        shard={"index": args.shard.index, "total": args.shard.total},
        settings_digest=digest(json.loads(json.dumps(settings, default=str))),
        exit_code=status,
    )
    suite = ET.Element("testsuite", name="recursive charts")
    for raw in sequence(report["charts"]):
        chart = mapping(raw)
        case = ET.SubElement(suite, "testcase", name=str(chart["chart"]), time=str(chart.get("testing_seconds", 0)))
        outcome = chart["status"]
        if outcome in {"empty-shard", "skipped-library", "cached-pass"}:
            ET.SubElement(case, "skipped", message=str(outcome))
        elif outcome not in {"passed", "ignored", "findings"}:
            ET.SubElement(case, "failure" if outcome in {"failed", "baseline-failed"} else "error", message=str(outcome))
    payload = ET.tostring(suite, encoding="unicode")
    report.update(junit_xml=payload, junit_sha256=hashlib.sha256(payload.encode()).hexdigest())
    (output / "junit.xml").write_text(payload + "\n")
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    (output / "scan.json").write_text(json.dumps(report, indent=2) + "\n")

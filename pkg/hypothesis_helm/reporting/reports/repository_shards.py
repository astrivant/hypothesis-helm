"""Verify and combine partitions of the same recursively discovered charts."""

import fcntl
import hashlib
import json
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

from hypothesis_helm.execution.planning.partition import digest
from hypothesis_helm.integrations.sharding import Shard
from hypothesis_helm.reporting.evidence.errors import chart_errors, deduplicate_errors
from hypothesis_helm.reporting.evidence.provenance import finish_epoch, trace_run
from hypothesis_helm.reporting.reports.repository import write_reports
from hypothesis_helm.schemas.contracts import mapping, sequence

__all__ = ("aggregate_repository",)


def _validate_work(records: list[dict[str, object]]) -> None:
    """
    Verify common inventories, exclusive ownership and honest completion claims.

    Args:
        records (list[dict[str, object]]): The same chart's results in shard order.

    Returns:
        None: Invalid evidence raises before any final artifact is published.
    """
    inventories: set[str] = set()
    visited: set[str] = set()
    for index, record in enumerate(records, 1):
        raw = record.get("work_partition")
        if raw is None:
            if record["status"] in {"passed", "cached-pass", "empty-shard"}:
                raise ValueError("Successful chart shard lacks its work partition")
            continue  # Failed preparation has no plan; its failure must survive aggregation.
        work = mapping(raw)
        coordinates = Shard(index, len(records))
        if (work.get("index"), work.get("total")) != (index, len(records)):
            raise ValueError("Chart partition coordinates disagree with its enclosing report")
        units = mapping(work["units"])
        initial = [str(unit) for unit in sequence(work["initial"])]
        if len(initial) != len(set(initial)) or not set(initial) <= units.keys():
            raise ValueError("Invalid initial work inventory")
        identity = digest([units, initial])
        if work.get("inventory_digest") != identity:
            raise ValueError("Chart work inventory checksum mismatch")
        inventories.add(identity)
        selected = [unit for unit in initial if coordinates.includes(str(units[unit]))]
        if work.get("selected") != selected:
            raise ValueError("Shard selection does not match deterministic ownership")
        observed = [str(unit) for unit in sequence(work["visited"])]
        completed = [str(unit) for unit in sequence(work["completed"])]
        if (
            len(observed) != len(set(observed))
            or len(completed) != len(set(completed))
            or not set(completed) <= set(observed)
            or not set(observed) <= units.keys()
            or any(not coordinates.includes(str(units[unit])) for unit in observed)
            or visited.intersection(observed)
        ):
            raise ValueError("Overlapping, duplicate or incorrectly assigned chart work")
        visited.update(observed)
        complete = set(selected) <= set(completed) and set(observed) == set(completed)
        if work.get("complete") != complete:
            raise ValueError("Chart partition completion claim disagrees with execution evidence")
        if record["status"] in {"passed", "cached-pass", "empty-shard", "findings", "ignored"} and not complete:
            raise ValueError("Successful chart shard has unfinished work")
        if record["status"] == "empty-shard" and (selected or observed or record.get("attempts")):
            raise ValueError("Nonempty work was reported as an empty shard")
    if len(inventories) > 1:
        raise ValueError("Shards planned different work for the same chart")


def _combine_chart(records: list[dict[str, object]]) -> dict[str, object]:
    """
    Combine one chart's evidence without confusing idle shards with omitted tests.

    Args:
        records (list[dict[str, object]]): Verified chart partitions.

    Returns:
        dict[str, object]: One chart section with merged path findings and counters.
    """
    statuses = {str(item["status"]) for item in records} - {"empty-shard"}
    priority = ("interrupted", "error", "failed", "baseline-failed", "scan-timeout", "time-limit", "generation-error", "unavailable")
    status = next((state for state in priority if state in statuses), None)
    if status is None:
        status = (
            "findings"
            if "findings" in statuses
            else "passed"
            if statuses and statuses <= {"passed", "cached-pass", "ignored"}
            else next(iter(statuses))
            if len(statuses) == 1
            else "incomplete"
        )
    first = next((record for record in records if record["status"] != "empty-shard"), records[0])
    chart = {
        key: value for key, value in first.items() if key not in {"work_partition", "cache", "error", "error_diagnostics", "traversal"}
    }
    chart.update(
        status=status,
        result="PASS"
        if status == "passed"
        else "FINDINGS"
        if status == "findings"
        else "FAIL"
        if status in {"failed", "baseline-failed"}
        else "N/A",
        attempts=sum(int(str(record.get("attempts", 0))) for record in records),
        testing_seconds=max(float(str(record.get("testing_seconds", 0))) for record in records),
        elapsed_seconds=max(float(str(record.get("elapsed_seconds", 0))) for record in records),
        coverage_complete=False,
        proof_of_totality=False,
        phases=[phase for record in records for phase in sequence(record.get("phases", []))],
        findings=[finding for record in records for finding in sequence(record.get("findings", []))],
        shard_results=records,
    )
    traversals = [mapping(record["traversal"]) for record in records if "traversal" in record]
    if traversals:
        chart["traversal"] = {
            "discovered_paths": max(int(str(item["discovered_paths"])) for item in traversals),
            **{
                key: sum(int(str(item[key])) for item in traversals)
                for key in (
                    "selected_paths",
                    "visited_paths",
                    "completed_paths",
                    "incomplete_paths",
                    "remaining_paths",
                )
            },
        }
    # Diagnostics also cover failures before path planning, such as missing dependencies or invalid defaults.
    errors = [error for record in records for error in chart_errors(record)]
    chart["error_diagnostics"] = list({digest(error): error for error in errors}.values())
    messages = list(dict.fromkeys(str(record["error"]) for record in records if record.get("error")))
    if messages:
        chart["error"] = "\n\n".join(messages)
    return chart


def aggregate_repository(reports: list[dict[str, object]], total: int, run_id: str, output: Path) -> int:
    """
    Publish one report after validating every chart partition from every CI shard.

    Args:
        reports (list[dict[str, object]]): Self-contained reports sorted by shard index.
        total (int): Expected shard count including empty assignments.
        run_id (str): Explicit shared execution identifier.
        output (Path): New immutable report bundle directory.

    Returns:
        int: Combined exit status; incomplete execution remains incomplete.
    """
    signatures: set[str] = set()
    inventories: set[str] = set()
    charts_by_shard: list[list[dict[str, object]]] = []
    merged = ET.Element("testsuites")
    for index, report in enumerate(reports, 1):
        if report.get("report_kind") != "repository-shard-v1" or report.get("run_id") != run_id:
            raise ValueError("Cannot mix report formats or run identifiers")
        if mapping(report.get("shard")) != {"index": index, "total": total}:
            raise ValueError("Missing, duplicate or mismatched repository shard coordinates")
        if not report.get("discovery_complete"):
            raise ValueError("Cannot verify a repository shard with incomplete chart discovery")
        if not isinstance(report.get("settings_digest"), str):
            raise ValueError("Repository shard lacks its settings identity")
        signatures.add(str(report["settings_digest"]))
        charts = [mapping(chart) for chart in sequence(report["charts"])]
        names = [str(chart["chart"]) for chart in charts]
        if not names or len(names) != len(set(names)):
            raise ValueError("Empty or duplicate repository chart inventory")
        inventories.add(digest(names))
        charts_by_shard.append(charts)
        payload = str(report.get("junit_xml", ""))
        if hashlib.sha256(payload.encode()).hexdigest() != report.get("junit_sha256"):
            raise ValueError("Repository shard JUnit checksum mismatch")
        merged.append(ET.fromstring(payload))
    if len(signatures) != 1 or len(inventories) != 1:
        raise ValueError("Repository shards used different settings or chart inventories")
    combined: list[dict[str, object]] = []
    for group in zip(*charts_by_shard, strict=True):
        records = list(group)
        for key in ("chart_fingerprint", "prepared_fingerprint"):
            identities = {str(record[key]) for record in records if key in record}
            if len(identities) > 1:
                raise ValueError(f"Shards tested different chart content: {records[0]['chart']}")
        _validate_work(records)
        combined.append(_combine_chart(records))
    codes = [int(str(report["exit_code"])) for report in reports]
    status = 130 if 130 in codes else 2 if any(code not in {0, 1} for code in codes) else 1 if 1 in codes else 0
    if status == 0 and any(chart["status"] not in {"passed", "findings", "ignored"} for chart in combined):
        raise ValueError("Successful repository shards do not establish successful chart execution")
    identity = digest(reports)
    first = reports[0]
    result: dict[str, object] = {
        "title": "Helm sharded repository results",
        "directory": first["directory"],
        "run_id": run_id,
        "source": first.get("source", {}),
        "execution": first.get("execution", {}),
        "input_digest": identity,
        "started_epoch": min(float(str(report["started_epoch"])) for report in reports),
        "settings": {**mapping(first["settings"]), "shards": total},
        "charts": combined,
        "charts_discovered": len(combined),
        "discovery_complete": True,
        "unstarted_charts": sum(chart["status"] == "pending" for chart in combined),
        "scan_status": "completed" if status in {0, 1} else "incomplete",
        "counts": dict(Counter(str(chart["status"]) for chart in combined)),
        "exit_code": status,
        "attempts": sum(int(str(chart["attempts"])) for chart in combined),
        "ignored_rules": first.get("ignored_rules", []),
        "finding_policy": first.get("finding_policy", {}),
        "shards": reports,
        "summary": [
            f"All {total} shards visit the same {len(combined)} charts; each owns distinct path properties or finite regions.",
            "Baselines are local setup and may repeat. Render hashes are process-local, not a global uniqueness count.",
        ],
    }
    finished = max(finish_epoch(report) for report in reports)
    result["elapsed_seconds"] = finished - float(str(result["started_epoch"]))
    deduplicate_errors(result)
    trace_run(result, finished_epoch=finished)
    output.parent.mkdir(parents=True, exist_ok=True)
    with (output.parent / f".{output.name}.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if output.exists():
            saved = mapping(json.loads((output / "report.json").read_text()))
            if saved.get("input_digest") != identity or saved.get("run_id") != run_id:
                raise ValueError("Final report already exists for different inputs; choose a new output directory")
            for name, checksum in mapping(saved["artifact_checksums"]).items():
                if hashlib.sha256((output / name).read_bytes()).hexdigest() != checksum:
                    raise ValueError(f"Existing final report artifact checksum mismatch: {name}")
            return status
        with TemporaryDirectory(prefix=f".{output.name}-", dir=output.parent) as temporary:
            staged = Path(temporary) / "report"
            staged.mkdir()
            ET.ElementTree(merged).write(staged / "junit.xml", encoding="utf-8", xml_declaration=True)
            write_reports(result, staged / "report")
            result["artifact_checksums"] = {
                path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in staged.iterdir() if path.is_file()
            }
            (staged / "report.json").write_text(json.dumps(result, indent=2) + "\n")
            staged.rename(output)
    print(f"Final report: {output / 'report.pdf'}")
    return status

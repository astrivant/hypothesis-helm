"""
Publish one immutable report bundle after all independently executed shards finish.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory

from hypothesis_helm.integrations.sharding import Shard
from hypothesis_helm.reporting.repository import write_reports
from hypothesis_helm.schemas.contracts import mapping, sequence


def read_reports(inputs: list[Path]) -> list[dict[str, object]]:
    """
    Decode piped JSON objects, NDJSON, arrays, or downloaded report files.

    Args:
        inputs (list[Path]): Report files or artifact roots; empty reads stdin.

    Returns:
        list[dict[str, object]]: Self-contained shard records, with no remote filesystem reads.
    """
    sources = [child for source in inputs for child in (sorted(source.glob("shards/*/report.json")) if source.is_dir() else [source])]
    contents = [source.read_text() for source in sources] if inputs else [sys.stdin.read()]
    result: list[dict[str, object]] = []
    decoder = json.JSONDecoder()
    for content in contents:
        remaining = content.lstrip()
        while remaining:
            decoded, end = decoder.raw_decode(remaining)
            records = decoded if isinstance(decoded, list) else [decoded]
            result.extend(mapping(record) for record in records)
            remaining = remaining[end:].lstrip()
    return result


def aggregate(inputs: list[Path], total: int, run_id: str, output: Path | None = None) -> int:
    """
    Validate all shard evidence and atomically publish JSON, JUnit, Markdown, and PDF together.

    Args:
        inputs (list[Path]): JSON report files or artifact directories; empty reads standard input.
        total (int): Required shard count, including empty partitions.
        run_id (str): Identifier explicitly supplied to every shard in this run.
        output (Path | None): New immutable output directory; directory inputs default to final/.

    Returns:
        int: Combined execution status; incompatible or missing inputs raise before publication.
    """
    if total < 1 or not run_id.strip():
        raise ValueError("shards must be positive and run-id must be nonempty")
    directory = inputs[0].resolve() if len(inputs) == 1 and inputs[0].is_dir() else None
    output = (output or (directory / "final" if directory else Path("reports/aggregate"))).resolve()
    if directory is not None and (output == directory or output.is_relative_to(directory / "shards")):
        raise ValueError("final reports must be separate from shard artifacts")
    reports = read_reports(inputs)
    if len(reports) != total:
        raise ValueError(f"Expected {total} shard reports, received {len(reports)}")
    reports.sort(key=lambda record: int(str(mapping(record.get("shard"))["index"])))
    output.parent.mkdir(parents=True, exist_ok=True)
    with ExitStack() as scope:
        publication = scope.enter_context((output.parent / f".{output.name}.lock").open("a"))
        fcntl.flock(publication, fcntl.LOCK_EX)
        records: list[dict[str, object]] = []
        signatures: set[str] = set()
        inventories: set[str] = set()
        selected: set[str] = set()
        matched: set[int] = set()
        merged = ET.Element("testsuites")
        input_hash = hashlib.sha256()
        counts = dict.fromkeys(("tests", "failures", "errors", "skipped"), 0)
        reused = 0
        failures: list[str] = []
        for index, record in enumerate(reports, 1):
            raw = json.dumps(record, sort_keys=True).encode()
            payload = record.get("junit_xml")
            if not isinstance(payload, str):
                raise ValueError(f"Shard {index}/{total} lacks its embedded JUnit report")
            junit = payload.encode("utf-8")
            try:
                xml = ET.fromstring(junit)
            except ET.ParseError as exc:
                raise ValueError(f"Shard {index}/{total} has invalid JUnit XML") from exc
            if record.get("run_id") != run_id:
                raise ValueError(f"Shard {index}/{total} belongs to a different or missing run-id")
            assignment = mapping(record.get("shard"))
            if (assignment.get("index"), assignment.get("total")) != (index, total):
                raise ValueError(f"Invalid or duplicate shard coordinates: expected {index}/{total}")
            signature = record.get("suite_fingerprint")
            inventory = assignment.get("matched_digest")
            if not isinstance(signature, str) or not isinstance(inventory, str):
                raise ValueError(f"Shard {index}/{total} lacks suite or collection identity")
            signatures.add(signature)
            inventories.add(inventory)
            matched.add(int(str(assignment["matched"])))
            nodes = [str(node) for node in sequence(assignment["tests"])]
            if len(nodes) != len(set(nodes)) or len(nodes) != assignment["selected"]:
                raise ValueError(f"Invalid selection count for shard {index}/{total}")
            if selected.intersection(nodes) or any(not Shard(index, total).includes(node) for node in nodes):
                raise ValueError("Shard selections overlap or contain incorrectly assigned properties")
            selected.update(nodes)
            if record.get("collect_only"):
                raise ValueError("Collection-only results cannot form a final test report")
            if hashlib.sha256(junit).hexdigest() != record.get("junit_sha256"):
                raise ValueError(f"Shard {index}/{total} JUnit checksum mismatch")
            cached = [str(node) for node in sequence(record.get("reused_properties", []))]
            if len(cached) != len(set(cached)) or not set(cached) <= set(nodes):
                raise ValueError(f"Invalid reused property inventory for shard {index}/{total}")
            reused += len(cached)
            cases = list(xml.iter("testcase"))
            if record.get("exit_code") == 0 and len(cases) + len(cached) != len(nodes):
                raise ValueError(f"Shard {index}/{total} claims success without covering its selection")
            counts["tests"] += len(cases)
            for case in cases:
                for tag, key in (
                    ("failure", "failures"),
                    ("error", "errors"),
                    ("skipped", "skipped"),
                ):
                    entries = case.findall(tag)
                    counts[key] += bool(entries)
                    if tag != "skipped":
                        failures.extend(
                            f"{case.get('classname', '')}.{case.get('name', '')}: {entry.text or entry.get('message', '')}"
                            for entry in entries
                        )
            merged.extend([xml] if xml.tag == "testsuite" else list(xml))
            records.append(record)
            input_hash.update(raw)
            input_hash.update(junit)
        if len(signatures) != 1 or len(inventories) != 1 or matched != {len(selected)}:
            raise ValueError("Shards do not cover the same suite and complete property selection")
        actual_inventory = hashlib.sha256(json.dumps(sorted(selected)).encode()).hexdigest()
        if inventories != {actual_inventory}:
            raise ValueError("Combined property selection does not match the collection checksum")
        identity = input_hash.hexdigest()
        if output.exists():
            existing = mapping(json.loads((output / "report.json").read_text()))
            if existing.get("run_id") != run_id or existing.get("input_digest") != identity:
                raise ValueError("Final report already exists for different inputs; choose a new output directory")
            for name, checksum in mapping(existing["artifact_checksums"]).items():
                if hashlib.sha256((output / name).read_bytes()).hexdigest() != checksum:
                    raise ValueError(f"Existing final report artifact checksum mismatch: {name}")
            return int(str(existing["exit_code"]))
        codes = [int(str(record["exit_code"])) for record in records]
        status = (
            130
            if 130 in codes
            else 2
            if any(code not in (0, 1) for code in codes)
            else 1
            if 1 in codes or counts["failures"] or counts["errors"]
            else 0
        )
        outcome = "passed" if status == 0 else "failed" if status == 1 else "incomplete"
        summary = [
            f"Run: {run_id}. All {total} shards reported; {len(selected)} selected properties.",
            f"Executed: {counts['tests']}; reused cached successes: {reused}; "
            f"failures: {counts['failures']}; errors: {counts['errors']}; "
            f"skipped: {counts['skipped']}.",
            "Render hashes are process-local; their counts cannot establish global output uniqueness.",
        ]
        record = {
            "chart": Path(str(records[0]["suite"])).name,
            "status": outcome,
            "result": "PASS" if status == 0 else "FAIL" if status == 1 else "N/A",
            "coverage": f"{len(selected)} selected properties across {total} shards",
            "artifacts": str(directory / "shards") if directory is not None else "none",
            "phases": [{"phase": f"shard {index}/{total}", "status": item["status"]} for index, item in enumerate(records, 1)],
        }
        if failures:
            record["error"] = "\n\n".join(failures)
        report: dict[str, object] = {
            "title": "Helm sharded test results",
            "directory": str(directory) if directory is not None else "piped shard reports",
            "run_id": run_id,
            "input_digest": identity,
            "started_epoch": min(float(str(item["started_epoch"])) for item in records),
            "elapsed_seconds": max(float(str(item["started_epoch"])) + float(str(item["elapsed_seconds"])) for item in records)
            - min(float(str(item["started_epoch"])) for item in records),
            "scan_status": "completed" if status in (0, 1) else "incomplete",
            "discovery_complete": True,
            "unstarted_charts": 0,
            "charts_discovered": 1,
            "counts": {outcome: 1},
            "charts": [record],
            "settings": {"shards": total, "jobs_per_shard": [item["jobs"] for item in records]},
            "summary": summary,
            "shards": records,
            "exit_code": status,
            "properties": {**counts, "selected": len(selected), "reused": reused},
            "render_hashes": {"scope": "process-local", "global_unique_bundles": None},
        }
        with TemporaryDirectory(prefix=f".{output.name}-", dir=output.parent) as temporary:
            staged = Path(temporary) / "report"
            staged.mkdir()
            ET.ElementTree(merged).write(staged / "junit.xml", encoding="utf-8", xml_declaration=True)
            write_reports(report, staged / "report")
            report["artifact_checksums"] = {
                name: hashlib.sha256((staged / name).read_bytes()).hexdigest() for name in ("junit.xml", "report.md", "report.pdf")
            }
            (staged / "report.json").write_text(json.dumps(report, indent=2) + "\n")
            staged.rename(output)
        print(f"Final report: {output / 'report.pdf'}")
        return status

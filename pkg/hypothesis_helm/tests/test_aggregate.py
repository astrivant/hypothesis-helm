"""
Verify aggregation of self-contained reports transported from independent CI runners.
"""

import hashlib
import io
import json
from pathlib import Path

import pytest

from hypothesis_helm.cli import main
from hypothesis_helm.integrations.sharding import Shard


def records() -> list[dict[str, object]]:
    """
    Construct complete, disjoint reports whose original filesystem paths do not exist.

    Returns:
        list[dict[str, object]]: Two verified shard records covering six properties.
    """
    nodes = [f"test_chart_values.py::test_example[{index}]" for index in range(6)]
    digest = hashlib.sha256(json.dumps(sorted(nodes)).encode()).hexdigest()
    result = []
    for index in (1, 2):
        selected = [node for node in nodes if Shard(index, 2).includes(node)]
        junit = "<testsuites><testsuite>" + "".join(f'<testcase name="{node}"/>' for node in selected) + "</testsuite></testsuites>"
        result.append(
            {
                "run_id": "pipeline-42-attempt-1",
                "suite_fingerprint": "same-content",
                "suite": "/nonexistent/other-runner/generated",
                "status": "passed",
                "exit_code": 0,
                "jobs": 2,
                "started_epoch": 1000,
                "elapsed_seconds": 2,
                "junit": "/nonexistent/other-runner/junit.xml",
                "junit_xml": junit,
                "junit_sha256": hashlib.sha256(junit.encode()).hexdigest(),
                "shard": {
                    "index": index,
                    "total": 2,
                    "matched": len(nodes),
                    "matched_digest": digest,
                    "selected": len(selected),
                    "tests": selected,
                },
            }
        )
    return result


@pytest.mark.parametrize("encoding", ["array", "concatenated", "ndjson"])
def test_piped_reports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, encoding: str) -> None:
    """
    Merge all supported pipe encodings without reading original JUnit or source files.

    Args:
        tmp_path (Path): Final report destination.
        monkeypatch (pytest.MonkeyPatch): Replace standard input.
        encoding (str): Transport representation.

    Returns:
        None: All four artifacts appear together with correct executed and selected counts.
    """
    reports = records()
    payload = (
        json.dumps(reports)
        if encoding == "array"
        else "\n".join(json.dumps(record, indent=2 if encoding == "concatenated" else None) for record in reports)
    )
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    output = tmp_path / "final"
    assert (
        main(
            [
                "aggregate",
                "--shards",
                "2",
                "--run-id",
                "pipeline-42-attempt-1",
                "--output-dir",
                str(output),
            ]
        )
        == 0
    )
    assert {path.name for path in output.iterdir()} == {
        "report.json",
        "report.md",
        "report.pdf",
        "junit.xml",
    }
    report = json.loads((output / "report.json").read_text())
    assert report["properties"]["selected"] == report["properties"]["tests"] == 6


@pytest.mark.parametrize("damage", ["missing", "duplicate", "run-id", "suite", "checksum", "inventory", "traversal", "ignored-rules"])
def test_incompatible_reports_never_publish(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, damage: str) -> None:
    """
    Reject missing or mixed pipeline artifacts before publishing any final report.

    Args:
        tmp_path (Path): Final report destination.
        monkeypatch (pytest.MonkeyPatch): Replace standard input.
        damage (str): Evidence to invalidate.

    Returns:
        None: Aggregation fails explicitly and leaves no final bundle.
    """
    reports = records()
    if damage == "missing":
        reports.pop()
    elif damage == "duplicate":
        reports[1] = reports[0]
    elif damage == "run-id":
        reports[1]["run_id"] = "another-attempt"
    elif damage == "suite":
        reports[1]["suite_fingerprint"] = "another-source"
    elif damage == "checksum":
        reports[1]["junit_xml"] = "<testsuites/>"
    elif damage == "ignored-rules":
        reports[1]["ignored_rules"] = ["HH1008"]
    elif damage == "traversal":
        reports[1]["traversal_strategy"] = "random"
    else:
        for record in reports:
            assignment = record["shard"]
            assert isinstance(assignment, dict)
            assignment["matched_digest"] = "same-but-wrong-in-both-shards"
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(reports)))
    output = tmp_path / "final"
    assert (
        main(
            [
                "aggregate",
                "--shards",
                "2",
                "--run-id",
                "pipeline-42-attempt-1",
                "--output-dir",
                str(output),
            ]
        )
        == 2
    )
    assert not output.exists()

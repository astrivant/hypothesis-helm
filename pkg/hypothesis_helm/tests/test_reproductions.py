"""
Verify chart-grouped diagnostics retain exact triggering paths and joint values.
"""

import copy
import re
from pathlib import Path

import pytest

from hypothesis_helm.reporting.errors import deduplicate_errors
from hypothesis_helm.reporting.links import Publication, linked_prose, publish_links
from hypothesis_helm.reporting.repository import artifact_link, write_reports
from hypothesis_helm.reporting.reproductions import changed_values, failing_input, input_summary
from hypothesis_helm.schemas.contracts import mapping, sequence


def test_exact_input_paths_and_empty_values() -> None:
    """
    Preserve literal keys, indexed lists, false, zero, empty strings, containers, and null.

    Returns:
        None: Flattened paths retain distinct keys and every supplied leaf value.
    """
    source: dict[str, object] = {"values": {"a.b": False, "a": {"b": 0}, "*": "", "list": [None, {}, []]}}
    assert failing_input(source)["paths"] == {
        '$["a.b"]': False,
        "$.a.b": 0,
        '$["*"]': "",
        "$.list[0]": None,
        "$.list[1]": {},
        "$.list[2]": [],
    }
    selected = failing_input({**source, "paths": [["a", "b"], ["list", 0], ["missing"]]})
    assert selected["paths"] == failing_input(source)["paths"]
    assert list(mapping(selected["paths"]))[:2] == ["$.a.b", "$.list[0]"]
    assert selected["absent_paths"] == ["$.missing"]
    assert failing_input({}) == {"recorded": False}
    assert failing_input({"values": {}})["paths"] == {"$": {}}


def test_reports_group_errors_and_inputs_by_chart(tmp_path: Path) -> None:
    """
    Keep diagnostics shared in JSON while showing chart-specific joint inputs inline.

    Args:
        tmp_path (Path): Markdown and PDF report destination.

    Returns:
        None: Each chart section includes its diagnostic and the values used together.
    """
    error = "incompatible ingress and service\nUse --debug flag to render out invalid YAML"
    phases = [
        {
            "phase": "permutations",
            "status": "failed",
            "error": error,
            "values": {"ingress": {"enabled": True}, "service": {"type": "ExternalName", "externalName": ""}},
        },
        {
            "phase": "$.service.port",
            "path": ["service", "port"],
            "status": "failed",
            "error": error,
            "values": {"service": {"port": 0}, "dependentSibling": "required context"},
            "artifacts": "second/paths/port",
        },
    ]
    report: dict[str, object] = {
        "directory": "/charts",
        "started_epoch": 1,
        "elapsed_seconds": 1,
        "charts_discovered": 2,
        "counts": {"failed": 2},
        "settings": {},
        "charts": [
            {"chart": "first", "status": "failed", "phases": [phases[0]], "artifacts": "first"},
            {"chart": "second", "status": "failed", "phases": [phases[1]], "artifacts": "second"},
        ],
    }
    original = copy.deepcopy(phases)
    markdown, pdf = write_reports(report, tmp_path / "report")
    first, second = markdown.read_text().split("### first\n", 1)[1].split("### second\n", 1)
    assert "incompatible ingress and service" in first and "incompatible ingress and service" in second
    assert "$.ingress.enabled = true" in first
    assert '$.service.type = "ExternalName"' in first
    assert '$.service.externalName = ""' in first
    assert "$.service.port = 0" in second
    assert "second/paths/port" in second
    assert "required context" not in second
    assert "Selected fields (full context in artifacts)" in second
    assert "--debug" not in markdown.read_text()
    assert "used together" in first
    assert report["error_summary"] == {"unique_errors": 1, "occurrences": 2, "duplicates": 1}
    assert phases == original
    assert pdf.read_bytes().startswith(b"%PDF")
    snapshot = copy.deepcopy(report)
    deduplicate_errors(report)
    assert report == snapshot


def test_expansion_keeps_each_failing_permutation(tmp_path: Path) -> None:
    """
    Retain expansion failures without duplicating the primary counterexample.

    Args:
        tmp_path (Path): Joint-input report destination.

    Returns:
        None: Every failing configuration appears under its chart and shared diagnostic.
    """
    failures = [{"error": "bad pair", "values": {"enabled": True, "port": value}} for value in (0, 1)]
    report: dict[str, object] = {
        "directory": "/charts",
        "started_epoch": 1,
        "elapsed_seconds": 1,
        "charts_discovered": 1,
        "counts": {"failed": 1},
        "settings": {},
        "charts": [{"chart": "demo", "status": "failed", **failures[0], "failure_expansion": {"failures": failures}}],
    }
    markdown, _ = write_reports(report, tmp_path / "report")
    groups = sequence(report["error_groups"])
    assert len(groups) == 1
    occurrences = [mapping(item) for item in sequence(mapping(groups[0])["occurrences"])]
    assert len(occurrences) == 2
    assert [mapping(mapping(item["input"])["paths"])["$.port"] for item in occurrences] == [0, 1]
    text = markdown.read_text()
    assert text.count("bad pair") == 1
    assert "$.port = 0" in text and "$.port = 1" in text


def test_changed_overrides_and_bounded_previews(tmp_path: Path) -> None:
    """
    Keep changed siblings visible and bound large inputs without dropping stored cases.

    Args:
        tmp_path (Path): Compact report destination.

    Returns:
        None: Defaults disappear from summaries, while full inputs and cases remain available.
    """
    defaults = {"service": {"port": 80, "peers": ["a", "b"]}, "enabled": True, "untouched": "default"}
    values = {"service": {"port": 0, "peers": ["a"]}, "enabled": False, "untouched": "default", "new": None}
    changes = changed_values(values, defaults)
    assert changes == {"$.service.port": 0, "$.service.peers": ["a"], "$.enabled": False, "$.new": None}
    assert changed_values({}, defaults) == {}
    assert changed_values({"service": {}}, defaults) == {}
    assert changed_values({"x": None}, {"x": None}) == {"$.x": None}
    assert changed_values({"x": False}, {"x": 0}) == {"$.x": False}
    assert changed_values({"x": 1.0}, {"x": 1}) == {"$.x": 1.0}
    evidence = failing_input({"values": values, "path": ["service", "port"], "input_changes": changes})
    summary = "\n".join(input_summary(evidence))
    assert "$.enabled = false" in summary and "untouched" not in summary
    large = {f"field{i}": "x" * 10000 for i in range(1000)}
    failures = [{"values": large, "error": "bad input", "phase": str(index), "status": "failed"} for index in range(100)]
    report: dict[str, object] = {
        "directory": "/charts",
        "started_epoch": 1,
        "elapsed_seconds": 1,
        "charts_discovered": 1,
        "counts": {"failed": 1},
        "settings": {},
        "charts": [{"chart": "demo", "status": "failed", "phases": failures, "artifacts": "full-evidence"}],
    }
    markdown, pdf = write_reports(report, tmp_path / "brief")
    text = markdown.read_text()
    assert len(text) < 5000
    assert "98 additional occurrences" in text
    assert "994 more paths" in text
    assert "value shortened" in text
    assert "full-evidence" in text
    assert b"/Subtype /Link" in pdf.read_bytes()
    assert mapping(report["error_summary"])["occurrences"] == 100
    assert mapping(sequence(report["charts"])[0])["phases"] == failures
    assert artifact_link("Input", tmp_path / "saved inputs", tmp_path / "report.md") == "[Input](<saved%20inputs>)"
    assert artifact_link("Input", "retained-run/inputs", tmp_path / "report.md") == "[Input](<retained-run/inputs>)"


def test_public_pdf_links(tmp_path: Path) -> None:
    """
    Render public links for files, folders, and multiple inline labels on main.

    Args:
        tmp_path (Path): Publication checkout containing retained inputs and reports.

    Returns:
        None: PDF annotations and Markdown targets agree and contain no local paths.
    """
    artifacts = tmp_path / "docs" / "saved inputs"
    artifacts.mkdir(parents=True)
    (artifacts / "values.json").write_text("{}")
    report: dict[str, object] = {
        "directory": "charts",
        "started_epoch": 1,
        "elapsed_seconds": 1,
        "charts_discovered": 1,
        "counts": {"failed": 1},
        "settings": {},
        "summary": ["[Input & values](<saved%20inputs/values.json>) and [All inputs](<saved%20inputs>)"],
        "charts": [{"chart": "demo", "status": "failed", "error": "failure", "artifacts": str(artifacts)}],
    }
    publication = Publication(tmp_path, "https://github.com/example/charts", "main")
    markdown, pdf = write_reports(report, tmp_path / "docs" / "report", publication=publication)
    uris = re.findall(rb"/URI\s*\(([^)]+)\)", pdf.read_bytes())
    assert len(uris) == 4
    assert all(uri.startswith(b"https://github.com/example/charts/") for uri in uris)
    assert b"https://github.com/example/charts/blob/main/docs/saved%20inputs/values.json" in uris
    assert b"https://github.com/example/charts/tree/main/docs/saved%20inputs" in uris
    assert all(uri.decode() in markdown.read_text() for uri in uris)
    assert str(tmp_path) not in markdown.read_text()
    with pytest.raises(ValueError):
        publication.url("../../outside", markdown)
    with pytest.raises(ValueError):
        publication.url("file:///private/input.json", markdown)
    literal = '`$.input = "[literal](../../outside)"`'
    assert publish_links(literal, markdown, publication) == literal
    assert "<link " not in linked_prose(literal)

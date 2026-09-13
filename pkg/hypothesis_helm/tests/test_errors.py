"""
Shared dependency diagnostics preserve source identity and affected chart contexts.
"""

import copy
import json
import tarfile
from pathlib import Path
from textwrap import dedent

import pytest
from ruamel.yaml.error import YAMLError

from hypothesis_helm.cli import main
from hypothesis_helm.reporting.errors import chart_errors, deduplicate_errors, template_source
from hypothesis_helm.reporting.repository import write_reports


def dependency(root: Path, *, version: str = "1.0.0", content: str = "shared template") -> Path:
    """
    Build a parent with one aliased, unpacked library dependency.

    Args:
        root (Path): Parent chart directory.
        version (str): Library version.
        content (str): Template bytes used to distinguish modified dependency copies.

    Returns:
        Path: Dependency directory with valid metadata and defaults.
    """
    root.mkdir(parents=True)
    (root / "Chart.yaml").write_text(
        dedent(f"""
        apiVersion: v2
        name: {root.name}
        version: 1.0.0
        dependencies:
          - name: shared
            alias: alias
            version: {version}
        """)
    )
    (root / "values.yaml").write_text("{}\n")
    child = root / "charts/alias"
    (child / "templates").mkdir(parents=True)
    (child / "Chart.yaml").write_text(
        dedent(f"""
        apiVersion: v2
        name: shared
        type: library
        version: {version}
        """)
    )
    (child / "values.yaml").write_text("{}\n")
    (child / "templates/_validate.tpl").write_text(content)
    return child


def diagnostic(parent: str, message: str = "port must exceed 100") -> str:
    """
    Construct distinct parent stacks ending at the same dependency failure.

    Args:
        parent (str): Parent chart name.
        message (str): Terminal error message, retained exactly in the signature.

    Returns:
        str: Representative Helm nested-template diagnostic.
    """
    return (
        f'Error: template: {parent}/templates/service.yaml:8:2: executing "{parent}" '
        f'at <include "shared.validate" .>: error calling include: '
        f"template: {parent}/charts/alias/templates/_validate.tpl:3:5: "
        f'executing "shared.validate" at <fail>: error calling fail: {message}'
    )


@pytest.mark.parametrize("packaged", [False, True])
def test_shared_error_groups(tmp_path: Path, packaged: bool) -> None:
    """
    Group dependency failures across parents, phases, and a standalone recursive chart.

    Args:
        tmp_path (Path): Chart and report directory.
        packaged (bool): Resolve the second parent's dependency from an aliased archive.

    Returns:
        None: One displayed error retains all affected charts and phase artifacts.
    """
    first = tmp_path / "first"
    second = tmp_path / "second"
    child = dependency(first)
    other = dependency(second)
    if packaged:
        archive = second / "charts/shared-1.0.0.tgz"
        with tarfile.open(archive, "w:gz") as bundle:
            bundle.add(other, arcname="shared")
        # Move the directory outside charts to force archive-based resolution.
        other.rename(tmp_path / "unpacked")
    records = []
    for root in (first, second):
        error = diagnostic(root.name)
        phases = [{"phase": name, "status": "failed", "error": error} for name in ("known-inputs", "robustness")]
        record: dict[str, object] = {
            "chart": root.name,
            "status": "failed",
            "attempts": 4,
            "artifacts": str(root),
            "phases": phases,
            "error": "\n\n".join(f"{phase['phase']}: {phase['error']}" for phase in phases),
        }
        record["error_diagnostics"] = chart_errors(record, root)
        records.append(record)
    standalone: dict[str, object] = {
        "chart": "first/charts/alias",
        "status": "failed",
        "error": diagnostic("first").split("error calling include: ")[1].replace("first/charts/alias/", "shared/"),
    }
    standalone["error_diagnostics"] = chart_errors(standalone, child)
    records.append(standalone)
    original = copy.deepcopy(records)
    report: dict[str, object] = {
        "directory": str(tmp_path),
        "started_epoch": 1,
        "elapsed_seconds": 2,
        "charts_discovered": 3,
        "counts": {"failed": 3},
        "settings": {},
        "charts": records,
    }
    deduplicate_errors(report)
    assert report["error_summary"] == {"unique_errors": 1, "occurrences": 5, "duplicates": 4}
    md, pdf = write_reports(report, tmp_path / "summary")
    assert md.read_text().count("port must exceed 100") == 1
    assert pdf.read_bytes().startswith(b"%PDF-")
    groups = report["error_groups"]
    assert isinstance(groups, list)
    assert groups[0]["source"]["name"] == "shared"
    assert groups[0]["affected_charts"] == ["first", "first/charts/alias", "second"]
    for record, before in zip(records, original, strict=True):
        assert record["error_refs"] == ["E001"]
        assert {key: value for key, value in record.items() if key != "error_refs"} == before
    snapshot = copy.deepcopy(report)
    deduplicate_errors(report)
    assert report == snapshot


@pytest.mark.parametrize("difference", ["version", "template", "message", "unresolved"])
def test_distinct_dependency_errors(tmp_path: Path, difference: str) -> None:
    """
    Keep failures separate when source identity or the terminal diagnostic differs.

    Args:
        tmp_path (Path): Chart directory.
        difference (str): Source or diagnostic distinction that must survive grouping.

    Returns:
        None: Conservative signatures do not conflate different dependency evidence.
    """
    records = []
    for name in ("first", "second"):
        root = tmp_path / name
        dependency(
            root,
            version="2.0.0" if name == "second" and difference == "version" else "1.0.0",
            content="modified" if name == "second" and difference == "template" else "shared",
        )
        error = diagnostic(
            name,
            "port must exceed 200" if difference == "message" and name == "second" else "port must exceed 100",
        )
        record: dict[str, object] = {"chart": name, "status": "failed", "error": error}
        record["error_diagnostics"] = chart_errors(record, None if difference == "unresolved" else root)
        records.append(record)
    report: dict[str, object] = {"charts": records}
    deduplicate_errors(report)
    assert report["error_summary"] == {"unique_errors": 2, "occurrences": 2, "duplicates": 0}


def test_scan_dependency_deduplication(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """
    Deduplicate before temporary copies disappear and keep scanning every parent.

    Args:
        tmp_path (Path): Repository with repeated dependencies.
        monkeypatch (pytest.MonkeyPatch): Substitute the chart execution boundary.
        capsys (pytest.CaptureFixture[str]): Capture aggregate JSON.

    Returns:
        None: JSON and human reports share one group without skipping affected charts.
    """
    for name in ("first", "second"):
        dependency(tmp_path / name)
    calls = []

    def exercise(path: Path, args: object, artifacts: Path) -> dict[str, object]:
        """
        Return a dependency failure from a chart's isolated copy.

        Args:
            path (Path): Isolated chart directory.
            args (object): Scan settings.
            artifacts (Path): Diagnostic destination.

        Returns:
            dict[str, object]: Failed parent result.
        """
        name = "first" if "name: first" in (path / "Chart.yaml").read_text() else "second"
        calls.append(name)
        return {"status": "failed", "error": diagnostic(name), "attempts": 2}

    monkeypatch.setattr("hypothesis_helm.charts.scan.exercise_chart", exercise)
    assert (
        main(
            [
                "scan",
                str(tmp_path),
                "--helm",
                "/usr/bin/true",
                "--no-build-dependencies",
                "--artifact-dir",
                str(tmp_path / "artifacts"),
                "--report",
                str(tmp_path / "summary"),
            ]
        )
        == 1
    )
    report = json.loads(capsys.readouterr().out)
    assert calls == ["first", "second"]
    assert report["counts"] == {"failed": 2, "skipped-library": 2}
    assert report["error_summary"] == {"unique_errors": 1, "occurrences": 2, "duplicates": 1}
    assert (tmp_path / "summary.md").read_text().count("port must exceed 100") == 1
    saved = next((tmp_path / "artifacts").glob("*/scan.json"))
    assert json.loads(saved.read_text()) == report


def test_repeated_dependency_build_errors() -> None:
    """
    Group identical preparation errors without counting unstarted charts as failures.

    Returns:
        None: Exact diagnostic groups retain each affected dependency-build context.
    """
    records: list[dict[str, object]] = [
        {
            "chart": name,
            "status": "dependency-build-failed",
            "error": "Error: could not download shared: repository unavailable",
        }
        for name in ("first", "second")
    ]
    records.append({"chart": "later", "status": "pending", "error": "Not started: --fail"})
    report: dict[str, object] = {"charts": records}
    deduplicate_errors(report)
    assert report["error_summary"] == {"unique_errors": 1, "occurrences": 2, "duplicates": 1}
    assert records[-1]["status"] == "pending"
    assert records[-1]["error_refs"] == []


def test_report_explains_tooling_failure_and_shows_input(tmp_path: Path) -> None:
    """
    Explain a retained parser failure alongside the exact input that reproduced it.

    Args:
        tmp_path (Path): Human report destination.

    Returns:
        None: Reports are actionable without rewriting recorded diagnostics or statuses.
    """
    error = "invalid rendered manifest: Object of type TaggedScalar is not JSON serializable"
    phase = {
        "phase": "known-inputs",
        "status": "failed",
        "error": error,
        "values": {"extraEnvVarsCM": "="},
    }
    report: dict[str, object] = {
        "directory": "/charts",
        "started_epoch": 1,
        "elapsed_seconds": 1,
        "charts_discovered": 1,
        "counts": {"failed": 1},
        "settings": {},
        "charts": [
            {
                "chart": "apache",
                "status": "failed",
                "phases": [phase],
                "error": f"known-inputs: {error}",
            }
        ],
    }
    md, _ = write_reports(report, tmp_path / "summary")
    text = md.read_text()
    assert "TaggedScalar" not in text
    assert "test tool could not convert a YAML-tagged value" in text
    assert "Reproducing values (known-inputs)" in text
    assert '"extraEnvVarsCM": "="' in text
    assert phase["error"] == error
    assert phase["status"] == "failed"


def test_unreadable_source_is_conservative(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Preserve original errors when source metadata cannot be inspected.

    Args:
        tmp_path (Path): Built chart directory.
        monkeypatch (pytest.MonkeyPatch): Simulate a malformed metadata document.

    Returns:
        None: Failed provenance lookup does not replace a chart diagnostic.
    """
    dependency(tmp_path / "first")

    def invalid(text: str) -> object:
        """
        Reject malformed YAML metadata.

        Args:
            text (str): Metadata document.

        Returns:
            object: Never returned because parsing fails.
        """
        raise YAMLError("invalid metadata")

    monkeypatch.setattr("hypothesis_helm.reporting.errors.yamlio.load", invalid)
    assert template_source(tmp_path / "first", "first/charts/alias/templates/_validate.tpl") is None
    assert template_source(tmp_path / "first", "first/../templates/secret") is None

"""
Verify evidence-based classification, catalog generation and actionable reports.
"""

import json
import shutil
from pathlib import Path
from textwrap import dedent

import pytest
from hypothesis import strategies as st

from hypothesis_helm.charts.model import Chart
from hypothesis_helm.charts.rendering import render
from hypothesis_helm.charts.runner import check_chart
from hypothesis_helm.cli import main
from hypothesis_helm.findings.catalog import CATALOG
from hypothesis_helm.findings.generator import FindingGenerator
from hypothesis_helm.reporting.errors import chart_errors
from hypothesis_helm.reporting.repository import write_reports
from hypothesis_helm.rules import ENVIRONMENT, RenderFailure

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def chart(tmp_path: Path) -> Chart:
    """
    Create a chart whose template can be changed independently of its values.

    Args:
        tmp_path (Path): Isolated chart directory.

    Returns:
        Chart: Helm-loadable chart with intentionally permissive inputs.
    """
    if shutil.which("helm") is None:
        pytest.skip("Helm is required")
    (tmp_path / "templates").mkdir()
    (tmp_path / "Chart.yaml").write_text(
        dedent("""
        apiVersion: v2
        name: findings
        version: 1.0.0
    """)
    )
    (tmp_path / "values.yaml").write_text("enabled: true\n")
    return Chart(tmp_path, {"type": "object"}, {"enabled": True})


@pytest.mark.parametrize(
    ("template", "code"),
    [
        ("{{ .Values.service.port }}", "HH3001"),
        ("{{ .Values.enabled | upper }}", "HH3002"),
        ('{{ include "missing.helper" . }}', "HH3003"),
        ('{{ fail "nil pointer evaluating interface {}.port" }}', "HH1001"),
        ('{{ required "wrong type for value; expected string; got bool" .Values.absent }}', "HH1001"),
        ("apiVersion: [", "HH1003"),
    ],
)
def test_real_helm_diagnostics(chart: Chart, template: str, code: str) -> None:
    """
    Detect actual Helm conditions while keeping explicit rejection messages unclassified.

    Args:
        chart (Chart): Native Helm fixture.
        template (str): Template exhibiting a known condition.
        code (str): Expected observation, independent of the Python exception type.

    Returns:
        None: Real diagnostics select precise rules and retain their original evidence.
    """
    (chart.path / "templates" / "example.yaml").write_text(template)
    with pytest.raises(RenderFailure) as error:
        render(chart, chart.defaults, stream=False)
    failure = error.value
    assert failure.code == code
    assert failure.finding.rule == CATALOG[code]
    assert failure.finding.evidence in str(failure)


def test_specific_ignore_does_not_ignore_other_template_findings(chart: Chart, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Apply ignore policy to a detected chart condition rather than its exception class.

    Args:
        chart (Chart): Real chart with an incompatible template operand.
        monkeypatch (pytest.MonkeyPatch): Set inherited policy between runs.

    Returns:
        None: Only the matching finding is ignored, and ignored outputs never count as validated.
    """
    (chart.path / "templates" / "example.yaml").write_text("{{ .Values.enabled | upper }}")
    monkeypatch.setenv(ENVIRONMENT, '["HH1001", "HH3001"]')
    result = check_chart(chart, max_examples=1, input_strategy=st.just({"enabled": True}), time_limit=10)
    assert result["status"] == "failed"
    assert result["code"] == "HH3002"
    monkeypatch.setenv(ENVIRONMENT, '["HH3002"]')
    result = check_chart(chart, max_examples=1, input_strategy=st.just({"enabled": True}), time_limit=10)
    assert result["status"] == "ignored"
    assert result["coverage_complete"] is False
    ignored = result["ignored_failures"]
    assert isinstance(ignored, dict)
    assert set(ignored) == {"HH3002"}
    assert ignored["HH3002"] > 0


def test_catalog_generation(capsys: pytest.CaptureFixture[str]) -> None:
    """
    Keep public catalogs and the inert configuration derived from the finding library.

    Args:
        capsys (pytest.CaptureFixture[str]): Capture catalog JSON from the public CLI.

    Returns:
        None: Every finding includes detection evidence, an example and repair guidance.
    """
    assert main(["rules", "--format", "json"]) == 0
    records = json.loads(capsys.readouterr().out)
    assert {record["code"] for record in records} == set(CATALOG)
    assert all(record[key] for record in records for key in ("detection", "example", "remediation", "category", "kind"))
    assert (ROOT / ".hypothesis-helm.yaml").read_text() == FindingGenerator.render("config")
    for code in ("HH1001", "HH1002", "HH1011", "HH1012", "HH2005"):
        assert FindingGenerator.create(code, "observed evidence").record()["kind"] == "diagnostic"
    with pytest.raises(KeyError):
        FindingGenerator.create("HH9999", "unknown")


def test_report_classification_preserves_evidence_and_inputs(tmp_path: Path) -> None:
    """
    Show a concise chart finding alongside the reproducible input and diagnostic.

    Args:
        tmp_path (Path): Report destination.

    Returns:
        None: Markdown and PDF generation preserve the condition's meaning and its reproducer.
    """
    failure = FindingGenerator.create("HH3002", "expected string; got bool")
    record: dict[str, object] = {
        "chart": "example",
        "status": "failed",
        "code": failure.rule.code,
        "error": failure.evidence,
        "values": {"enabled": True},
    }
    assert chart_errors(record)[0]["finding"] == failure.record()
    report: dict[str, object] = {
        "directory": "/charts",
        "started_epoch": 1,
        "elapsed_seconds": 1,
        "charts_discovered": 1,
        "counts": {"failed": 1},
        "settings": {},
        "charts": [record],
    }
    md, pdf = write_reports(report, tmp_path / "summary")
    text = md.read_text()
    assert "Incompatible value type in template" in text
    assert "template / violation" in text
    assert "expected string; got bool" in text
    assert "$.enabled = true" in text
    assert pdf.is_file()

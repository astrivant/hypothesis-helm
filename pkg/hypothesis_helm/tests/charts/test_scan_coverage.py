"""
Keep chart testing active when finite interaction planning cannot describe its inputs.
"""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from hypothesis_helm.charts.repositories.repository import RepositorySource
from hypothesis_helm.charts.testing.coverage import require_attempts
from hypothesis_helm.cli import main
from hypothesis_helm.tests.fixtures.cli import result_text


@pytest.mark.parametrize("remote", [False, True])
@pytest.mark.parametrize("domain", ["open", "unbounded", "inferred", "finite"])
def test_requested_permutations_still_execute_charts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], remote: bool, domain: str
) -> None:
    """
    Resolve explicit interaction requests per chart without dropping non-finite input domains.

    Args:
        tmp_path (Path): Source chart and execution artifacts.
        monkeypatch (pytest.MonkeyPatch): Replace fetching and execution while keeping CLI planning real.
        capsys (pytest.CaptureFixture[str]): Structured results and the fallback warning.
        remote (bool): Exercise remote scan or local recursive test.
        domain (str): Open objects, unbounded scalars, inferred values, or finite factors.

    Returns:
        None: Testing retains budgets and workers, and reports the actual coverage mode without editing the schema.
    """
    root = tmp_path / "chart"
    root.mkdir()
    (root / "Chart.yaml").write_text("apiVersion: v2\nname: example\nversion: 1.0.0\n")
    (root / "values.yaml").write_text('enabled: false\nlabel: "ready"\n')
    schema = {
        "type": "object",
        "additionalProperties": domain == "open",
        "properties": {
            "enabled": {"type": "boolean"},
            "label": {"type": "string", **({} if domain == "unbounded" else {"enum": ["ready"]})},
        },
    }
    original = json.dumps(schema)
    if domain != "inferred":
        (root / "values.schema.json").write_text(original)
    paths = Mock(return_value={"status": "passed", "attempts": 3, "coverage_complete": False})
    finite = Mock(return_value={"status": "passed", "attempts": 3})
    monkeypatch.setattr("hypothesis_helm.charts.repositories.scan.check_paths", paths)
    monkeypatch.setattr("hypothesis_helm.charts.repositories.scan.check_chart", finite)
    monkeypatch.setattr("hypothesis_helm.charts.repositories.scan.audit_findings", lambda chart: {"findings": [], "unresolved": []})
    if remote:
        source = RepositorySource("https://github.com/example/charts.git", root, "charts", True)
        monkeypatch.setattr("hypothesis_helm.charts.repositories.scan.prepare_helm_source", lambda *args, **kwargs: None)
        monkeypatch.setattr("hypothesis_helm.charts.repositories.scan.RepositorySource.prepare", lambda *args: source)
    monkeypatch.chdir(tmp_path)
    assert (
        main(
            [
                "scan" if remote else "test",
                source.location if remote else str(root),
                "--helm",
                "/usr/bin/true",
                "--no-build-dependencies",
                "--no-cache",
                "--log-file",
                "/dev/stderr",
                "--permutations",
                "10",
                "--traversal-strategy",
                "sensitivity-first",
                "--filter",
                "--jobs",
                "8",
                "--chart-timeout",
                "10m",
                "--max-examples",
                "10",
                "--seed",
                "17",
                "--artifact-dir",
                str(tmp_path / "results"),
            ]
        )
        == 0
    )
    output = capsys.readouterr()
    report = json.loads(result_text(output.out))
    chart = report["charts"][0]
    assert chart["attempts"] == report["attempts"] == 3
    assert chart["status"] == "passed"
    if domain == "finite":
        paths.assert_not_called()
        assert finite.call_args.kwargs["permutations"] == 10
        assert "coverage_fallback" not in chart
    else:
        finite.assert_not_called()
        options = paths.call_args.kwargs
        assert {key: options[key] for key in ("jobs", "budget", "max_examples", "seed", "filtering", "traversal_strategy")} == {
            "jobs": 8,
            "budget": 600,
            "max_examples": 10,
            "seed": 17,
            "filtering": True,
            "traversal_strategy": "random",
        }
        assert chart["coverage_fallback"]["requested_permutations"] == 10
        assert chart["coverage_fallback"]["effective"] == "path-properties"
        assert chart["traversal_fallback"]["effective"] == "random"
        assert chart["coverage_complete"] is False
        assert "Requested interaction coverage is not guaranteed" in output.err
    if domain != "inferred":
        assert (root / "values.schema.json").read_text() == original


@pytest.mark.parametrize("finite_options", [False, True])
def test_single_chart_explicit_permutations_fall_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], finite_options: bool
) -> None:
    """
    Use path workers for a lone non-finite chart even without recursive-report options.

    Args:
        tmp_path (Path): Standalone chart.
        monkeypatch (pytest.MonkeyPatch): Capture path execution and bypass upstream tools.
        capsys (pytest.CaptureFixture[str]): Scan result with effective coverage.
        finite_options (bool): Request controls that have no equivalent in path-based execution.

    Returns:
        None: The command executes instead of rejecting finite planning or parallel settings.
    """
    (tmp_path / "Chart.yaml").write_text("apiVersion: v2\nname: example\nversion: 1.0.0\n")
    (tmp_path / "values.yaml").write_text("enabled: false\n")
    (tmp_path / "values.schema.json").write_text('{"type":"object","properties":{"enabled":{"type":"boolean"}}}')
    paths = Mock(return_value={"status": "passed", "attempts": 2})
    monkeypatch.setattr("hypothesis_helm.charts.repositories.scan.check_paths", paths)
    monkeypatch.setattr("hypothesis_helm.charts.repositories.scan.audit_findings", lambda chart: {"findings": [], "unresolved": []})
    monkeypatch.chdir(tmp_path)
    options = ["--filter-topology", "2", "--expand-failures"] if finite_options else []
    assert (
        main(
            ["test", str(tmp_path), "--helm", "/usr/bin/true", "--permutations", "10", "--jobs", "8", "--log-file", "/dev/stderr", *options]
        )
        == 0
    )
    report = json.loads(result_text(capsys.readouterr().out))
    assert paths.call_args.kwargs["jobs"] == 8
    assert report["attempts"] == 2
    assert report["charts"][0]["coverage_fallback"]["unavailable_options"] == (
        ["--filter-topology", "--expand-failures"] if finite_options else []
    )


@pytest.mark.parametrize("status", ["passed", "findings", "ignored"])
def test_scan_rejects_success_without_test_attempts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], status: str
) -> None:
    """
    Refuse successful scan exits and cache publication when fresh execution does no testing.

    Args:
        tmp_path (Path): Scan source and artifacts.
        monkeypatch (pytest.MonkeyPatch): Return a faulty zero-attempt worker result.
        capsys (pytest.CaptureFixture[str]): Final status and the visible no-tests diagnostic.
        status (str): Otherwise successful result status.

    Returns:
        None: The scan exits nonzero and identifies the execution problem.
    """
    (tmp_path / "Chart.yaml").write_text("apiVersion: v2\nname: example\nversion: 1.0.0\n")
    (tmp_path / "values.yaml").write_text("{}\n")
    monkeypatch.setattr("hypothesis_helm.charts.repositories.scan.exercise_chart", lambda *args: {"status": status, "attempts": 0})
    monkeypatch.chdir(tmp_path)
    assert main(["test", str(tmp_path), "--helm", "/usr/bin/true", "--log-file", "/dev/stderr"]) == 1
    output = capsys.readouterr()
    report = json.loads(result_text(output.out))
    assert report["attempts"] == 0
    assert report["scan_status"] == "not-tested"
    assert report["charts"][0]["status"] == "error"
    assert "No manifest tests were attempted" in report["charts"][0]["error"]
    assert "No manifest test attempts were executed" in output.err


@pytest.mark.parametrize("status", ["cached-pass", "empty-shard", "dry-run", "interrupted", "time-limit", "failed"])
def test_no_work_and_stopped_results_remain_explicit(status: str) -> None:
    """
    Preserve deliberate no-work outcomes and the original reason testing stopped.

    Args:
        status (str): Cache, shard, planning, cancellation, deadline, or failure status.

    Returns:
        None: A zero-attempt guard never masks these outcomes with a different failure.
    """
    result: dict[str, object] = {"status": status, "attempts": 0}
    require_attempts(result)
    assert result == {"status": status, "attempts": 0}

"""
Repository discovery, execution boundaries, and portable reports.
"""

import json
from pathlib import Path
from textwrap import dedent

import pytest

from hypothesis_helm.charts.scan import discover_charts
from hypothesis_helm.cli import argument_parser, main
from hypothesis_helm.reporting.repository import wrap_markdown, write_reports


@pytest.mark.parametrize("existing", [False, True])
def test_scan_rejects_local_directories(tmp_path: Path, existing: bool, capsys: pytest.CaptureFixture[str]) -> None:
    """
    Keep remote scanning separate from local directory testing.

    Args:
        tmp_path (Path): Local source directory.
        existing (bool): Whether the requested local path exists.
        capsys (pytest.CaptureFixture[str]): Capture the CLI diagnostic.

    Returns:
        None: Both local spellings fail with guidance to use test.
    """
    source = tmp_path if existing else tmp_path / "missing"
    assert main(["scan", str(source), "--helm", "/usr/bin/true"]) == 2
    error = json.loads(capsys.readouterr().out)["error"]
    assert "use test" in error


def test_local_testing_never_fetches_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Prevent local discovery from interpreting a directory as a remote repository alias.

    Args:
        tmp_path (Path): Empty local directory.
        monkeypatch (pytest.MonkeyPatch): Guard remote source preparation.

    Returns:
        None: Local discovery reports no charts without a source-fetch request.
    """

    def remote(*args: object, **kwargs: object) -> None:
        """
        Reject an unexpected remote source operation.

        Args:
            *args (object): Source arguments.
            **kwargs (object): Source options.

        Returns:
            None: This boundary must never be reached.
        """
        pytest.fail("Local testing attempted remote source preparation")

    monkeypatch.setattr("hypothesis_helm.charts.scan.prepare_helm_source", remote)
    monkeypatch.setattr("hypothesis_helm.charts.scan.RepositorySource.prepare", remote)
    assert main(["test", str(tmp_path), "--helm", "/usr/bin/true", "--artifact-dir", str(tmp_path / "results")]) == 2


def test_discovery(tmp_path: Path) -> None:
    """
    Find nested charts, preserve invalid metadata, and avoid symlink cycles.

    Args:
        tmp_path (Path): Isolated directory tree.

    Returns:
        None: Assertions verify discovery results.
    """
    (tmp_path / "Chart.yaml").write_text(
        dedent("""
        apiVersion: v2
        name: root
        version: "1.2.3"
    """)
    )
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "Chart.yaml").write_text("name: incomplete\n")
    (nested / "loop").symlink_to(tmp_path, target_is_directory=True)
    found = discover_charts(tmp_path)
    assert [(chart["chart"], chart["status"]) for chart in found] == [
        (".", "pending"),
        ("nested", "invalid-metadata"),
    ]
    assert "apiVersion" in str(found[1]["error"])


@pytest.mark.parametrize(
    "metadata",
    [
        "[]",
        "null",
        "apiVersion: v9",
        "apiVersion: v2\nname: ../escape\nversion: '1.2.3'",
        "apiVersion: v2\nname: okay\nversion: banana",
    ],
)
def test_invalid_metadata(tmp_path: Path, metadata: str) -> None:
    """
    Reject unusable metadata before invoking Helm.

    Args:
        tmp_path (Path): Isolated chart directory.
        metadata (str): Invalid Chart.yaml content.

    Returns:
        None: Invalid records remain visible in the result.
    """
    (tmp_path / "Chart.yaml").write_text(metadata)
    assert discover_charts(tmp_path)[0]["status"] == "invalid-metadata"


def test_report_paths_and_pagination(tmp_path: Path) -> None:
    """
    Produce readable paired files for either explicit extension.

    Args:
        tmp_path (Path): Report destination.

    Returns:
        None: Long diagnostics are summarized; many distinct charts still paginate.
    """
    report: dict[str, object] = {
        "directory": "/charts",
        "started_epoch": 123,
        "elapsed_seconds": 1,
        "charts_discovered": 2,
        "counts": {"failed": 2},
        "settings": {},
        "summary": ["Scan findings need triage before being called chart defects. " * 8],
        "charts": [{"chart": "demo", "status": "failed", "error": "failure\n" * 2000}],
    }
    md, pdf = write_reports(report, tmp_path / "custom.pdf")
    assert md.name == "custom.md"
    assert pdf.name == "custom.pdf"
    assert "failure" in md.read_text()
    assert "<img " not in md.read_text()
    assert not (tmp_path / "hypothesis-helm-logo.png").exists()
    assert b"/Subtype /Image" in pdf.read_bytes()
    assert all(len(line) <= 140 for line in md.read_text().splitlines())
    assert pdf.read_bytes().startswith(b"%PDF-")
    assert pdf.read_bytes().count(b"/Type /Page\n") == 1
    assert "Diagnostic shortened" in md.read_text()
    report["charts"] = [{"chart": f"demo-{index}", "status": "failed", "error": "failure"} for index in range(40)]
    report["charts_discovered"] = 40
    report["counts"] = {"failed": 40}
    _, pdf = write_reports(report, tmp_path / "many")
    assert pdf.read_bytes().count(b"/Type /Page\n") >= 2


def test_report_wrapping_preserves_markdown() -> None:
    """
    Preserve reproductions, fenced diagnostics, links, and list continuation.

    Returns:
        None: Prose wraps without altering diagnostic or Markdown structure.
    """
    prose = "Observed failures require triage. " * 10
    link = "[chart artifacts](<runs/" + "long-chart-name-" * 12 + " with spaces/values.json>)"
    code = json.dumps({"value": "a " * 150})
    fenced = f"````text\n{code}\n```\n{prose}\n````\n"
    assert wrap_markdown(fenced) == fenced
    assert wrap_markdown(f"~~~json\n{code}\n~~~\n") == f"~~~json\n{code}\n~~~\n"
    wrapped = wrap_markdown(prose)
    assert all(len(line) <= 140 for line in wrapped.splitlines())
    assert wrapped.split() == prose.split()
    listed = wrap_markdown("- " + prose).splitlines()
    assert listed[0].startswith("- ")
    assert all(line.startswith("  ") and len(line) <= 140 for line in listed[1:])
    linked = wrap_markdown(prose + link + "\n")
    assert link in linked.splitlines()
    assert wrap_markdown(linked) == linked
    assert link + "." in wrap_markdown(prose + link + ".").splitlines()
    inline = "`" + "a b " * 40 + "`"
    assert inline in wrap_markdown(prose + inline)
    assert wrap_markdown(prose.rstrip() + "  ").endswith("  \n")


def test_scan_execution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """
    Preserve property results and classify missing schemas without false passes.

    Args:
        tmp_path (Path): Isolated chart repository.
        monkeypatch (pytest.MonkeyPatch): Replace only the external execution boundary.
        capsys (pytest.CaptureFixture[str]): Capture machine-readable summary.

    Returns:
        None: Status, artifacts, and paired reports agree.
    """
    import hypothesis_helm.charts.scan as module

    for name in ("a", "b"):
        chart = tmp_path / name
        chart.mkdir()
        (chart / "values.yaml").write_text("{}\n")
        (chart / "Chart.yaml").write_text(f"apiVersion: v2\nname: {name}\nversion: '1.0.0'\n")
    monkeypatch.setattr("hypothesis_helm.charts.scan.shutil.which", lambda name: "/bin/true")
    monkeypatch.setattr(
        module,
        "exercise_chart",
        lambda path, args, artifacts: {
            "status": "passed" if "name: a" in (path / "Chart.yaml").read_text() else "baseline-only",
            "attempts": 5,
        },
    )
    assert (
        main(
            [
                "test",
                str(tmp_path),
                "--no-build-dependencies",
                "--report",
                str(tmp_path / "result"),
                "--artifact-dir",
                str(tmp_path / "artifacts"),
            ]
        )
        == 2
    )
    report = json.loads(capsys.readouterr().out)
    assert report["counts"] == {"passed": 1, "baseline-only": 1}
    assert (tmp_path / "result.md").exists()
    assert (tmp_path / "result.pdf").exists()
    assert argument_parser().parse_args(["test", str(tmp_path), "--report"]).report == ""


@pytest.mark.parametrize("fail_fast", [False, True])
@pytest.mark.parametrize("outcome", ["failed", "baseline-failed", "error", "time-limit"])
def test_scan_fail_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    fail_fast: bool,
    outcome: str,
) -> None:
    """
    Stop failed scans without losing findings or treating unstarted charts as passes.

    Args:
        tmp_path (Path): Isolated repository and report destination.
        monkeypatch (pytest.MonkeyPatch): Replace chart execution with recorded outcomes.
        capsys (pytest.CaptureFixture[str]): Capture the aggregate JSON report.
        fail_fast (bool): Enable early termination.
        outcome (str): First tested chart outcome, including incomplete coverage.

    Returns:
        None: Execution order, exit code, and retained reports agree.
    """
    for name in ("a", "b", "c"):
        chart = tmp_path / name
        chart.mkdir()
        (chart / "Chart.yaml").write_text(
            dedent(f"""
            apiVersion: v2
            name: {name}
            version: '1.0.0'
            """)
        )
        if name != "a":
            (chart / "values.yaml").write_text("{}\n")
    calls: list[str] = []

    def exercise(path: Path, args: object, artifacts: Path) -> dict[str, object]:
        """
        Record tested charts and retain a representative failure artifact.

        Args:
            path (Path): Isolated chart copy.
            args (object): Scan options.
            artifacts (Path): Reproducer destination.

        Returns:
            dict[str, object]: Controlled chart outcome.
        """
        calls.append((path / "Chart.yaml").read_text())
        artifacts.mkdir(parents=True)
        (artifacts / "values.json").write_text('{"flag": true}\n')
        return {"status": outcome if len(calls) == 1 else "passed", "attempts": 3}

    monkeypatch.setattr("hypothesis_helm.charts.scan.exercise_chart", exercise)
    options = [
        "test",
        str(tmp_path),
        "--helm",
        "/usr/bin/true",
        "--filter",
        "--no-build-dependencies",
        "--artifact-dir",
        str(tmp_path / "artifacts"),
        "--report",
        str(tmp_path / "result"),
    ]
    if fail_fast:
        options.append("--fail")
    code = main(options)
    report = json.loads(capsys.readouterr().out)
    stopped = fail_fast and outcome != "time-limit"
    assert code == (2 if outcome == "time-limit" else 1)
    assert len(calls) == (1 if stopped else 2)
    assert report["scan_status"] == ("failed-early" if stopped else "completed")
    assert report["settings"]["fail"] is fail_fast
    assert report["unstarted_charts"] == int(stopped)
    assert report["charts"][0]["status"] == "missing-values"
    assert report["charts"][1]["status"] == outcome
    assert report["charts"][2]["status"] == ("pending" if stopped else "passed")
    if stopped:
        assert report["charts"][2]["result"] == "N/A"
        assert "--fail" in report["charts"][2]["error"]
    assert (Path(report["charts"][1]["artifacts"]) / "values.json").exists()
    assert json.loads(next((tmp_path / "artifacts").glob("*/scan.json")).read_text()) == report
    assert outcome in (tmp_path / "result.md").read_text()
    assert (tmp_path / "result.pdf").read_bytes().startswith(b"%PDF-")


def test_missing_values_single_and_recursive(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """
    Fail the sole missing baseline and keep scanning a mixed repository.

    Args:
        tmp_path (Path): Isolated repository.
        capsys (pytest.CaptureFixture[str]): JSON output capture.

    Returns:
        None: Single and recursive exit statuses follow the documented contract.
    """
    first = tmp_path / "first"
    first.mkdir()
    (first / "Chart.yaml").write_text("apiVersion: v2\nname: first\nversion: '1.0.0'\n")
    assert main(["test", str(first), "--helm", "/usr/bin/true", "--artifact-dir", str(tmp_path / "out")]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["counts"] == {"missing-values": 1}
    assert report["charts"][0]["result"] == "N/A"
    second = tmp_path / "second"
    second.mkdir()
    (second / "Chart.yaml").write_text("apiVersion: v2\nname: second\nversion: '1.0.0'\n")
    (second / "values.yaml").write_text("{}\n")
    assert (
        main(
            [
                "test",
                str(tmp_path),
                "--helm",
                "/usr/bin/true",
                "--artifact-dir",
                str(tmp_path / "out"),
            ]
        )
        == 1
    )
    report = json.loads(capsys.readouterr().out)
    assert report["counts"] == {"missing-values": 1, "failed": 1}
    assert report["charts"][1]["error"] == "[HH1009] chart rendered no resources"
    assert report["charts"][1]["baseline"]["code"] == "HH1009"


def test_values_override_and_dependency_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """
    Build before testing and apply the chosen baseline only in the isolated copy.

    Args:
        tmp_path (Path): Chart and artifact destination.
        monkeypatch (pytest.MonkeyPatch): Replace external Helm execution.
        capsys (pytest.CaptureFixture[str]): Capture final summary.

    Returns:
        None: Ordering and source preservation assertions pass.
    """
    import subprocess

    (tmp_path / "Chart.yaml").write_text("apiVersion: v2\nname: demo\nversion: '1.0.0'\n")
    (tmp_path / "values.yaml").write_text("enabled: false\n")
    (tmp_path / "custom.yaml").write_text("enabled: true\n")
    calls: list[list[str]] = []

    def command(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        """
        Record literal commands without invoking a network-enabled Helm process.

        Args:
            argv (list[str]): Helm command.
            **kwargs (object): Subprocess settings.

        Returns:
            subprocess.CompletedProcess[str]: Successful dependency build.
        """
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, "dependencies built", "")

    def exercise(path: Path, args: object, artifacts: Path) -> dict[str, object]:
        """
        Check the selected baseline after dependency resolution.

        Args:
            path (Path): Isolated working chart.
            args (object): Execution options.
            artifacts (Path): Output destination.

        Returns:
            dict[str, object]: Successful test result.
        """
        assert calls[0][1:3] == ["dependency", "build"]
        assert (path / "values.yaml").read_text() == "enabled: true\n"
        return {"status": "passed", "attempts": 1}

    monkeypatch.setattr("hypothesis_helm.charts.scan.Processes.run", lambda self, *args, **kwargs: command(*args, **kwargs))
    monkeypatch.setattr("hypothesis_helm.charts.scan.comparison", lambda *args: {"status": "unavailable"})
    monkeypatch.setattr("hypothesis_helm.charts.scan.exercise_chart", exercise)
    assert (
        main(
            [
                "test",
                str(tmp_path),
                "--helm",
                "/usr/bin/true",
                "--values",
                "custom.yaml",
                "--artifact-dir",
                str(tmp_path / "out"),
            ]
        )
        == 0
    )
    assert (tmp_path / "values.yaml").read_text() == "enabled: false\n"
    assert json.loads(capsys.readouterr().out)["counts"] == {"passed": 1}


def test_interrupt_preserves_remaining_charts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """
    Save reports on interruption without claiming unattempted charts passed.

    Args:
        tmp_path (Path): Two-chart repository.
        monkeypatch (pytest.MonkeyPatch): Interrupt the chart execution boundary.
        capsys (pytest.CaptureFixture[str]): Capture partial summary.

    Returns:
        None: The interrupted and pending charts remain in both reports.
    """
    for name in ("a", "b"):
        path = tmp_path / name
        path.mkdir()
        (path / "Chart.yaml").write_text(f"apiVersion: v2\nname: {name}\nversion: '1.0.0'\n")
        (path / "values.yaml").write_text("{}\n")

    def interrupt(path: Path, args: object, artifacts: Path) -> dict[str, object]:
        """
        Simulate an interrupt while the first chart is running.

        Args:
            path (Path): Chart under test.
            args (object): Execution options.
            artifacts (Path): Output destination.

        Returns:
            dict[str, object]: Never returned because the operation is interrupted.
        """
        raise KeyboardInterrupt()

    monkeypatch.setattr("hypothesis_helm.charts.scan.exercise_chart", interrupt)
    assert (
        main(
            [
                "test",
                str(tmp_path),
                "--helm",
                "/usr/bin/true",
                "--no-build-dependencies",
                "--report",
                str(tmp_path / "partial"),
                "--artifact-dir",
                str(tmp_path / "out"),
            ]
        )
        == 130
    )
    report = json.loads(capsys.readouterr().out)
    assert report["counts"] == {"interrupted": 1, "pending": 1}
    assert "pending" in (tmp_path / "partial.md").read_text()
    assert (tmp_path / "partial.pdf").exists()


def test_scan_timeout_pauses_for_dependencies(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """
    Allow dependency preparation past the scan budget, then interrupt active testing.

    Args:
        tmp_path (Path): Fake Helm executable and two charts.
        capsys (pytest.CaptureFixture[str]): Capture the partial JSON report.

    Returns:
        None: Dependency time is separate and the restored scan alarm stops testing.
    """
    import os
    import shlex
    import time

    pid = tmp_path / "helm.pid"
    helm = tmp_path / "helm"
    helm.write_text(
        dedent(
            f"""
            #!/bin/sh
            if [ "$1" = dependency ]; then
                sleep 0.4
                exit 0
            fi
            printf '%s' "$$" > {shlex.quote(str(pid))}
            exec sleep 10
            """
        ).lstrip()
    )
    helm.chmod(0o755)
    for name in ("a", "b"):
        path = tmp_path / name
        path.mkdir()
        (path / "Chart.yaml").write_text(f"apiVersion: v2\nname: {name}\nversion: '1.0.0'\n")
        (path / "values.yaml").write_text("{}\n")
    started = time.monotonic()
    assert (
        main(
            [
                "test",
                str(tmp_path),
                "--helm",
                str(helm),
                "--scan-timeout",
                "0.3s",
                "--chart-timeout",
                "2s",
                "--report",
                str(tmp_path / "partial"),
                "--artifact-dir",
                str(tmp_path / "out"),
            ]
        )
        == 124
    )
    assert time.monotonic() - started < 3
    report = json.loads(capsys.readouterr().out)
    assert report["counts"] == {"scan-timeout": 1, "pending": 1}
    assert report["unstarted_charts"] == 1
    assert report["discovery_complete"] is True
    assert report["settings"]["chart_timeout_seconds"] == 2
    assert report["dependency_preparation_seconds"] >= 0.4
    assert report["dependency_preparation_seconds"] == report["charts"][0]["dependency_preparation_seconds"]
    assert report["testing_seconds"] > 0
    assert report["elapsed_seconds"] >= report["dependency_preparation_seconds"] + report["testing_seconds"]
    text = (tmp_path / "partial.md").read_text()
    assert "scan-timeout" in text
    assert "Dependency preparation:" in text
    assert "Chart testing:" in text
    assert "Elapsed (wall clock):" in text
    assert (tmp_path / "partial.pdf").exists()
    with pytest.raises(ProcessLookupError):
        os.kill(int(pid.read_text()), 0)


def test_timeout_during_discovery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """
    Make incomplete discovery explicit instead of claiming an empty successful scan.

    Args:
        tmp_path (Path): Directory under discovery.
        monkeypatch (pytest.MonkeyPatch): Simulate slow metadata parsing.
        capsys (pytest.CaptureFixture[str]): Capture the partial summary.

    Returns:
        None: Unknown remaining inventory is reported as incomplete discovery.
    """
    import time

    (tmp_path / "Chart.yaml").write_text("apiVersion: v2\nname: a\nversion: '1.0.0'\n")
    monkeypatch.chdir(tmp_path)  # Keep the slow chart parser separate from caller policy loading.
    monkeypatch.setattr("hypothesis_helm.charts.scan.yamlio.load", lambda text: time.sleep(2))
    assert (
        main(
            [
                "test",
                str(tmp_path),
                "--helm",
                "/usr/bin/true",
                "--scan-timeout",
                "0.1s",
                "--artifact-dir",
                str(tmp_path / "out"),
            ]
        )
        == 124
    )
    report = json.loads(capsys.readouterr().out)
    assert report["discovery_complete"] is False
    assert report["scan_status"] == "scan-timeout"


@pytest.mark.parametrize("outcome", ["passed", "failed", "timeout", "interrupted"])
def test_dependency_timing_accounting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], outcome: str
) -> None:
    """
    Pause cumulative scan accounting for every dependency result without resetting test budgets.

    Args:
        tmp_path (Path): Two-chart repository.
        monkeypatch (pytest.MonkeyPatch): Replace Helm and the scanner's local clock.
        capsys (pytest.CaptureFixture[str]): Capture the final report.
        outcome (str): Dependency completion, failure, timeout, or interruption.

    Returns:
        None: Preparation and testing totals remain disjoint, including partial scans.
    """
    import argparse
    import subprocess
    import time
    from types import SimpleNamespace

    import hypothesis_helm.charts.scan as module

    for name in ("a", "b"):
        chart = tmp_path / name
        chart.mkdir()
        (chart / "Chart.yaml").write_text(f"apiVersion: v2\nname: {name}\nversion: '1.0.0'\n")
        (chart / "values.yaml").write_text("{}\n")
    clock = [time.monotonic()]
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=lambda: clock[0], time=time.time))
    remaining = []

    def prepare(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        """
        Spend more preparation time than the entire scan budget.

        Args:
            argv (list[str]): Dependency command.
            **kwargs (object): Independent command timeout and capture settings.

        Returns:
            subprocess.CompletedProcess[str]: Simulated successful or failed preparation.

        Raises:
            subprocess.TimeoutExpired: The dependency command timed out.
            KeyboardInterrupt: The user interrupted preparation.
        """
        assert argv[1:3] == ["dependency", "build"]
        assert kwargs["timeout"] == 30
        clock[0] += 4
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(argv, 30)
        if outcome == "interrupted":
            raise KeyboardInterrupt
        return subprocess.CompletedProcess(argv, int(outcome == "failed"), "prepared", "")

    def exercise(path: Path, args: argparse.Namespace, artifacts: Path) -> dict[str, object]:
        """
        Consume a quarter second of the remaining scan budget.

        Args:
            path (Path): Prepared chart.
            args (argparse.Namespace): Cumulative scan and chart budgets.
            artifacts (Path): Result destination.

        Returns:
            dict[str, object]: Successful property-test result.
        """
        assert args.chart_timeout == 1
        remaining.append(args.scan_deadline - clock[0])
        clock[0] += 0.25
        return {"status": "passed", "attempts": 1, "execution_seconds": 0.2}

    monkeypatch.setattr("hypothesis_helm.charts.scan.Processes.run", lambda self, *args, **kwargs: prepare(*args, **kwargs))
    monkeypatch.setattr(module, "comparison", lambda *args: {"status": "unavailable"})
    monkeypatch.setattr(module, "exercise_chart", exercise)
    code = main(
        [
            "test",
            str(tmp_path),
            "--helm",
            "/usr/bin/true",
            "--chart-timeout",
            "1s",
            "--scan-timeout",
            "2s",
            "--artifact-dir",
            str(tmp_path / "out"),
        ]
    )
    report = json.loads(capsys.readouterr().out)
    assert code == {"passed": 0, "failed": 2, "timeout": 2, "interrupted": 130}[outcome]
    assert report["dependency_preparation_seconds"] == (4 if outcome == "interrupted" else 8)
    assert report["testing_seconds"] == (0.5 if outcome == "passed" else 0)
    assert report["elapsed_seconds"] == report["dependency_preparation_seconds"] + report["testing_seconds"]
    assert remaining == ([2, 1.75] if outcome == "passed" else [])
    assert report["scan_status"] == ("interrupted" if outcome == "interrupted" else "completed")


def test_scan_timeout_arguments() -> None:
    """
    Keep per-chart compatibility while validating both duration arguments.

    Returns:
        None: Defaults and duration parsing remain explicit.
    """
    parser = argument_parser()
    args = parser.parse_args(["scan", "https://example.com/charts.git"])
    assert args.chart_timeout == 180
    assert args.scan_timeout is None
    assert parser.parse_args(["scan", "https://example.com/charts.git", "--time-limit", "2m"]).chart_timeout == 120
    for flag in ("--chart-timeout", "--scan-timeout"):
        with pytest.raises(SystemExit):
            parser.parse_args(["scan", "https://example.com/charts.git", flag, "0"])


def test_scan_deadline_preserves_runner_statistics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    Retain partial runner counters when it handles the scan alarm internally.

    Args:
        tmp_path (Path): Chart and output directories.
        monkeypatch (pytest.MonkeyPatch): Simulate a runner returning partial statistics.
        capsys (pytest.CaptureFixture[str]): Capture scan statistics.

    Returns:
        None: Total expiration preserves the available iteration accounting.
    """
    import time

    from hypothesis_helm.reporting.budget import TimeLimitReached

    (tmp_path / "Chart.yaml").write_text("apiVersion: v2\nname: a\nversion: '1.0.0'\n")
    (tmp_path / "values.yaml").write_text("{}\n")

    def exercise(path: Path, args: object, artifacts: Path) -> dict[str, object]:
        """
        Return the same partial-counter contract as the property runner.

        Args:
            path (Path): Chart under test.
            args (object): Execution configuration.
            artifacts (Path): Statistics destination.

        Returns:
            dict[str, object]: Counters preserved after an execution alarm.
        """
        try:
            time.sleep(2)
        except TimeLimitReached:
            return {
                "status": "time-limit",
                "attempts": 3,
                "completed_iterations": 2,
                "remaining_iterations": 7,
            }
        raise AssertionError("scan deadline did not interrupt the runner")

    monkeypatch.setattr("hypothesis_helm.charts.scan.exercise_chart", exercise)
    assert (
        main(
            [
                "test",
                str(tmp_path),
                "--helm",
                "/usr/bin/true",
                "--no-build-dependencies",
                "--scan-timeout",
                "0.1s",
                "--artifact-dir",
                str(tmp_path / "out"),
            ]
        )
        == 124
    )
    report = json.loads(capsys.readouterr().out)
    assert report["charts"][0]["status"] == "scan-timeout"
    assert report["charts"][0]["attempts"] == 3
    assert report["charts"][0]["completed_iterations"] == 2
    assert report["charts"][0]["remaining_iterations"] == 7


@pytest.mark.parametrize("finite", [True, False])
def test_scan_filter_support(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    finite: bool,
) -> None:
    """
    Apply finite filtering or known-input-first sampling according to the chart domain.

    Args:
        tmp_path (Path): Isolated chart.
        monkeypatch (pytest.MonkeyPatch): Capture property runner settings.
        capsys (pytest.CaptureFixture[str]): Capture the final filtering report.
        finite (bool): Whether the chart input has a finite domain.

    Returns:
        None: Filtering uses the appropriate strategy without changing the chart contract.
    """
    (tmp_path / "Chart.yaml").write_text("apiVersion: v2\nname: sample\nversion: '1.0.0'\n")
    (tmp_path / "values.yaml").write_text("{}\n")
    (tmp_path / "values.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {"input": {"type": "boolean" if finite else "string"}},
            }
        )
    )
    called: dict[str, object] = {}

    def check(chart: object, **kwargs: object) -> dict[str, object]:
        """
        Record settings instead of running the property suite.

        Args:
            chart (object): Loaded input model.
            **kwargs (object): Property runner settings.

        Returns:
            dict[str, object]: Successful synthetic runner result.
        """
        called.update(kwargs)
        return {"status": "passed", "attempts": 1}

    monkeypatch.setattr("hypothesis_helm.charts.scan.check_chart", check)
    monkeypatch.setattr("hypothesis_helm.charts.paths.check_chart", check)
    monkeypatch.setattr("hypothesis_helm.charts.paths.render", lambda *args, **kwargs: [{"kind": "ConfigMap"}])
    assert (
        main(
            [
                "test",
                str(tmp_path),
                "--helm",
                "/usr/bin/true",
                "--no-build-dependencies",
                "--filter",
                "--jobs",
                "1",
                "--artifact-dir",
                str(tmp_path / "out"),
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert called.get("trim_topology", 0) == (2 if finite else 0)
    assert called.get("expand_failures", False) is finite
    assert report["charts"][0]["filtering"]["applied"] is True
    if not finite:
        assert report["charts"][0]["filtering"]["method"] == "known-path-generation"
        assert "input_strategy" in called

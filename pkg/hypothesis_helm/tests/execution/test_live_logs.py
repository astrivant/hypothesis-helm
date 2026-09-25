"""
Keep live finding diagnostics visible while preserving manifest streams and worker ownership.
"""

import json
import logging
import os
import subprocess
import sys
import time
from argparse import Namespace
from pathlib import Path
from textwrap import dedent
from typing import TextIO

import pytest

from hypothesis_helm.charts.model import Chart
from hypothesis_helm.charts.repositories.scan import exercise_chart
from hypothesis_helm.charts.testing.paths import check_paths
from hypothesis_helm.charts.testing.prioritized import check_prioritized
from hypothesis_helm.charts.testing.runner import check_chart
from hypothesis_helm.charts.values import yamlio
from hypothesis_helm.cli import main
from hypothesis_helm.environment import refresh_env
from hypothesis_helm.exceptions.rendering import RenderFailure
from hypothesis_helm.execution.runtime.processes import Processes
from hypothesis_helm.execution.workers.path_queue import execute
from hypothesis_helm.findings.severity import ACTIVE_POLICY
from hypothesis_helm.reporting.console.logs import WORKER_PREFIX, FindingLog, LogFormatter, WorkerLogFormatter, WorkerLogs
from hypothesis_helm.rules import ENVIRONMENT
from hypothesis_helm.schemas.contracts import mapping, sequence
from hypothesis_helm.tests import PROJECT_ROOT
from hypothesis_helm.tests.execution.test_path_workers import fixture_chart


@pytest.mark.parametrize("fail", [False, True])
@pytest.mark.parametrize("severity, priority", [(None, logging.WARNING), ("error", logging.ERROR), ("info", logging.INFO)])
def test_audit_logs_source_locations_without_duplicates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, fail: bool, severity: str | None, priority: int
) -> None:
    """
    Show actionable template locations and retain fail-fast behavior for unresolved analysis.

    Args:
        tmp_path (Path): Isolated chart fixture.
        monkeypatch (pytest.MonkeyPatch): Deterministic audit and execution results.
        caplog (pytest.LogCaptureFixture): Finding log capture.
        fail (bool): Whether the caller requests immediate failure.
        severity (str | None): Recorded override, or the catalog default when absent.
        priority (int): Expected logging level.

    Returns:
        None: Repeated diagnostics log once; source locations appear in both logs and fail-fast errors.
    """
    chart = fixture_chart(tmp_path)
    finding: dict[str, object] = {"code": "HH2005", "file": "templates/worker.yaml", "line": 188, "message": "helper context is unresolved"}
    if severity is not None:
        finding["severity"] = severity
    monkeypatch.setattr(
        "hypothesis_helm.charts.repositories.scan.audit_findings", lambda chart: {"findings": [], "unresolved": [finding, finding]}
    )
    monkeypatch.setattr("hypothesis_helm.charts.repositories.scan._exercise_chart", lambda *args: {"status": "passed"})
    with caplog.at_level(priority):
        result = exercise_chart(chart.path, Namespace(fail=fail), tmp_path / "results")
    assert caplog.text.count("Audit finding:") == 1
    assert caplog.records[0].levelno == priority
    assert "templates/worker.yaml:188" in caplog.text and "path=[]" not in caplog.text
    assert result["status"] == ("failed" if fail else "passed")
    if fail:
        assert "templates/worker.yaml:188" in str(result["error"])


@pytest.mark.parametrize(
    "warning",
    [
        'level=INFO msg="warning: cannot overwrite table with non table for airflow.redis.sentinel.annotations (map[])"',
        "warning: merge failed",
    ],
)
def test_preview_prefers_native_error_over_merge_warning(caplog: pytest.LogCaptureFixture, warning: str) -> None:
    """
    Display the actual Helm failure when stderr starts with an unrelated coalescing warning.

    Args:
        caplog (pytest.LogCaptureFixture): Captured finding preview.
        warning (str): Helm log or plain warning preceding the fatal diagnostic.

    Returns:
        None: Console output names the error while preserving bounded, single-line previews.
    """
    message = dedent(f"""
        [HH1001] {warning}
        Error: execution error at (airflow/charts/redis/templates/NOTES.txt:202:4): invalid settings
        private details
        """).strip()
    findings = FindingLog("airflow", {})
    with caplog.at_level(logging.WARNING):
        findings.observed("HH1001", message, {})
    assert "Error: execution error at" in caplog.text
    assert "invalid settings" in caplog.text
    assert warning not in caplog.text
    assert "private details" not in caplog.text
    assert message.startswith(f"[HH1001] {warning}")


def test_observed_and_final_findings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    """
    Announce a bug before shrinking, retain its final input and respect ignored checks.

    Args:
        tmp_path (Path): Reproducer destination.
        monkeypatch (pytest.MonkeyPatch): Deterministic failing renderer and policy.
        caplog (pytest.LogCaptureFixture): Live diagnostics.

    Returns:
        None: Shrinking does not flood the log or announce suppressed failures as bugs.
    """
    chart = Chart(
        tmp_path,
        {"type": "object", "properties": {"value": {"enum": [1, 2]}}, "required": ["value"], "additionalProperties": False},
        {"value": 0},
    )

    def fail(*args: object, **kwargs: object) -> list[dict[str, object]]:
        """
        Reject generated values as malformed YAML.

        Args:
            *args (object): Candidate chart and values.
            **kwargs (object): Render context.

        Returns:
            list[dict[str, object]]: No resource is returned from this intentional failure.

        Raises:
            RenderFailure: An invalid YAML finding.
        """
        raise RenderFailure("YAML parse error\nprivate raw manifest follows", code="HH1101")

    monkeypatch.setattr("hypothesis_helm.charts.testing.runner.render", fail)
    with caplog.at_level(logging.ERROR):
        result = check_chart(
            chart,
            input_strategy=chart.strategy(),
            check_defaults=False,
            max_examples=4,
            artifact_dir=tmp_path / "results",
            protected_paths=(("value",),),
        )
    assert result["status"] == "failed"
    assert caplog.text.count("Finding observed:") == 1
    assert caplog.text.count("Counterexample recorded:") == 1
    assert all(record.levelno == logging.ERROR for record in caplog.records)
    assert "[HH1101]" in caplog.text and "$.value = 1" in caplog.text
    assert "private raw manifest" not in caplog.text
    monkeypatch.setenv(ENVIRONMENT, '["HH1101"]')
    refresh_env()
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        check_chart(chart, input_strategy=chart.strategy(), check_defaults=False, max_examples=4)
    assert "Finding observed:" not in caplog.text and "Counterexample recorded:" not in caplog.text


@pytest.mark.parametrize("severity, priority", [("info", logging.INFO), ("warning", logging.WARNING), ("error", logging.ERROR)])
@pytest.mark.parametrize("recorded", [False, True])
def test_finding_logs_use_effective_severity(caplog: pytest.LogCaptureFixture, severity: str, priority: int, recorded: bool) -> None:
    """
    Honor both active scoped overrides and severity recorded before a scope exited.

    Args:
        caplog (pytest.LogCaptureFixture): Console log records at the selected threshold.
        severity (str): Effective finding severity.
        priority (int): Expected Python logging level.
        recorded (bool): Whether the caller supplies the earlier severity decision.

    Returns:
        None: Findings survive the matching log threshold and use the matching color label.
    """
    # A recorded decision must win even when the current scope would classify the code differently.
    token = ACTIVE_POLICY.set({"severity": {"HH1101": "warning" if recorded else severity}})
    try:
        with caplog.at_level(priority):
            FindingLog("example", {}).emit("Counterexample recorded", "HH1101", "invalid YAML", severity=severity if recorded else None)
    finally:
        ACTIVE_POLICY.reset(token)
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.levelno == priority
    assert record.__dict__["finding_severity"] == severity
    color = {"info": "36", "warning": "33", "error": "31"}[severity]
    assert LogFormatter(color=True).format(record).startswith(f"\033[{color}m[{severity.upper()}]\033[0m")


@pytest.mark.parametrize("level", [logging.INFO, logging.WARNING, logging.ERROR])
def test_incremental_worker_logs(tmp_path: Path, caplog: pytest.LogCaptureFixture, level: int) -> None:
    """
    Forward complete structured events once, excluding partial and raw diagnostic output.

    Args:
        tmp_path (Path): Worker log directory.
        caplog (pytest.LogCaptureFixture): Parent logger observations.
        level (int): Worker severity that must survive forwarding unchanged.

    Returns:
        None: Interleaved polls preserve complete messages and their finding context.
    """
    event = logging.LogRecord("hypothesis_helm.worker", level, "worker.py", 1, "found\na failure", (), None)
    event.finding_code = "HH1101"
    event.finding_severity = logging.getLevelName(level).lower()
    encoded = WorkerLogFormatter().format(event) + "\n"
    first = tmp_path / "worker-0.log"
    first.write_text("raw traceback\n" + encoded[:20])
    second = tmp_path / "worker-1.log"
    second.write_text(WORKER_PREFIX + "broken json\n")
    relay = WorkerLogs(tmp_path, 2)
    with caplog.at_level(level):
        relay.drain()
        assert caplog.records == []
        with first.open("a") as stream:
            stream.write(encoded[20:])
        relay.drain()
        relay.drain()
    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == level
    assert caplog.records[0].getMessage() == "found\na failure"
    assert caplog.records[0].__dict__["finding_code"] == "HH1101"
    assert caplog.records[0].__dict__["finding_severity"] == logging.getLevelName(level).lower()


def test_worker_logs_arrive_before_exit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Require the parent to receive a log before allowing its subprocess to finish.

    Args:
        tmp_path (Path): Queue and acknowledgement location.
        monkeypatch (pytest.MonkeyPatch): Substitute a small cooperating worker.

    Returns:
        None: A real subprocess cannot exit successfully if logs are deferred until completion.
    """
    acknowledgement = tmp_path / "acknowledged"
    script = dedent("""
        import json
        import sys
        import time
        from pathlib import Path
        print('HYPOTHESIS_HELM_LOG ' + json.dumps({'message': 'handshake', 'level': 30}), flush=True)
        deadline = time.monotonic() + 10
        while not Path(sys.argv[1]).exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert Path(sys.argv[1]).exists(), 'log was not relayed while worker was running'
    """)
    original = Processes.run

    def worker(
        owner: Processes, args: list[str], *, stdout: TextIO, stderr: TextIO, env: dict[str, str], pass_fds: tuple[int, ...], check: bool
    ) -> subprocess.CompletedProcess[str]:
        """
        Start the handshake worker using the coordinator's real subprocess owner.

        Args:
            owner (Processes): Owner responsible for joining the subprocess.
            args (list[str]): Replaced internal worker command.
            stdout (TextIO): Parent-owned worker log.
            stderr (TextIO): Parent-owned diagnostic stream.
            env (dict[str, str]): Worker environment.
            pass_fds (tuple[int, ...]): Shared manifest descriptors.
            check (bool): Whether to raise on a failed child.

        Returns:
            subprocess.CompletedProcess[str]: Real child exit status.
        """
        return original(
            owner,
            [sys.executable, "-c", script, str(acknowledgement)],
            stdout=stdout,
            stderr=stderr,
            env=env,
            pass_fds=pass_fds,
            check=check,
        )

    class Acknowledge(logging.Handler):
        """
        Unblock a worker only after the parent logging system receives its message.
        """

        def emit(self, record: logging.LogRecord) -> None:
            """
            Acknowledge the expected live record.

            Args:
                record (logging.LogRecord): Forwarded event.

            Returns:
                None: The marker allows the worker to exit.
            """
            if record.getMessage() == "handshake":
                acknowledgement.touch()

    monkeypatch.setattr(Processes, "run", worker)
    logger = logging.getLogger("hypothesis_helm")
    handler = Acknowledge()
    level = logger.level
    logger.setLevel(logging.WARNING)
    logger.addHandler(handler)
    try:
        assert execute({"paths": [{}], "deadline": time.monotonic() + 20}, tmp_path / "queue", 1) == []
        assert acknowledgement.exists()
    finally:
        logger.removeHandler(handler)
        logger.setLevel(level)


@pytest.mark.parametrize("mode", ["standalone", "paths", "prioritized"])
def test_input_baseline_once_per_chart_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, mode: str
) -> None:
    """
    Announce shared inventories once without suppressing a later run of the same chart.

    Args:
        tmp_path (Path): Chart and per-run artifacts.
        monkeypatch (pytest.MonkeyPatch): Replace external renders with a valid resource.
        caplog (pytest.LogCaptureFixture): Coordinator and property log records.
        mode (str): Standalone, path-based, or two-phase execution boundary.

    Returns:
        None: Each complete chart run emits one baseline despite multiple paths or phases.
    """
    chart = fixture_chart(tmp_path)
    # Permit deferred arbitrary-key cases so both prioritized phases execute.
    chart.schema.pop("additionalProperties")
    resource = {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "workers"}}
    monkeypatch.setattr("hypothesis_helm.charts.testing.runner.render", lambda *args, **kwargs: [resource])
    monkeypatch.setattr("hypothesis_helm.charts.testing.paths.render", lambda *args, **kwargs: [resource])
    with caplog.at_level(logging.INFO):
        for repeat in range(2):
            if mode == "standalone":
                result = check_chart(chart, max_examples=2)
            elif mode == "paths":
                result = check_paths(
                    chart, budget=30, max_examples=2, seed=0, helm="helm", timeout=5, artifacts=tmp_path / f"results-{repeat}"
                )
            else:
                result = check_prioritized(
                    chart, budget=30, max_examples=2, seed=0, helm="helm", timeout=5, artifacts=tmp_path / f"results-{repeat}"
                )
                assert [mapping(phase)["phase"] for phase in sequence(result["phases"])] == ["known-inputs", "robustness"]
            assert result["status"] == "passed"
            announcements = [record for record in caplog.records if record.getMessage().startswith("Compiler input baseline:")]
            assert len(announcements) == repeat + 1
            assert announcements[-1].__dict__["chart"] == "workers"


@pytest.mark.parametrize("color", ["never", "auto", "always"])
def test_cli_log_destinations(tmp_path: Path, capsys: pytest.CaptureFixture[str], color: str) -> None:
    """
    Show logs by default and append to explicitly selected files without leaking handlers.

    Args:
        tmp_path (Path): Tiny chart and log directory.
        capsys (pytest.CaptureFixture[str]): Standard output and error capture.
        color (str): Plain, terminal-sensitive or explicitly colored log formatting.

    Returns:
        None: File logging leaves report JSON clean and subsequent invocations return to stdout.
    """
    fixture_chart(tmp_path)
    logger = logging.getLogger("hypothesis_helm")
    handlers = list(logger.handlers)
    assert main(["audit", str(tmp_path)]) == 0
    assert "[INFO] Auditing path" in capsys.readouterr().out
    logfile = tmp_path / "logs" / "audit.log"
    for repeat in range(2):
        assert main(["audit", str(tmp_path), "--log-file", str(logfile), "--log-color", color]) == 0
        output = capsys.readouterr()
        assert json.loads(output.out)["chart"] == str(tmp_path)
        assert "[INFO]" not in output.out + output.err
        assert logfile.read_text().count("Auditing path $.field0") == repeat + 1
        assert ("\033[" in logfile.read_text()) is (color == "always")
    assert logger.handlers == handlers
    assert main(["audit", str(tmp_path), "--log-file", str(tmp_path)]) == 2
    assert json.loads(capsys.readouterr().out)["type"] == "IsADirectoryError"
    assert logger.handlers == handlers
    assert main(["audit", str(tmp_path)]) == 0
    assert "[INFO] Auditing path" in capsys.readouterr().out


@pytest.mark.parametrize("output_format", ["json", "yaml"])
def test_parallel_path_manifest_stream(tmp_path: Path, capfd: pytest.CaptureFixture[str], output_format: str) -> None:
    """
    Forward path workers' manifests without mixing live logs or partial documents into stdout.

    Args:
        tmp_path (Path): Real chart and scan output directory.
        capfd (pytest.CaptureFixture[str]): Descriptor-level stream capture.
        output_format (str): Requested manifest encoding.

    Returns:
        None: More than the baseline reaches stdout; all records are valid complete resources.
    """
    chart = fixture_chart(tmp_path)
    for field in mapping(chart.schema["properties"]).values():
        mapping(field).pop("maximum")
    (tmp_path / "values.schema.json").write_text(json.dumps(chart.schema))
    assert (
        main(
            [
                "test",
                str(tmp_path),
                "--chart-timeout",
                "30s",
                "--no-build-dependencies",
                "--no-cache",
                "--filter",
                "--jobs",
                "2",
                "--max-examples",
                "2",
                "--artifact-dir",
                str(tmp_path / "results"),
                "--output-format",
                output_format,
                "--log-color",
            ]
        )
        == 0
    )
    output = capfd.readouterr()
    resources = [json.loads(line) for line in output.out.splitlines()] if output_format == "json" else yamlio.load_all(output.out)
    assert len(resources) > 1
    assert all(isinstance(resource, dict) and resource["kind"] == "ConfigMap" for resource in resources)
    assert "Testing path" in output.err and "Scan completed" in output.err
    assert '"status": "passed"' not in output.err
    assert output.err.count("Compiler input baseline:") == 1
    assert "[INFO]" not in output.out
    assert "\033[" not in output.out and "\033[" in output.err
    assert "HYPOTHESIS_HELM_MANIFEST_FD" not in os.environ


def test_refresh_tees_logs_and_preserves_report(tmp_path: Path) -> None:
    """
    Keep refresh logs visible, report JSON clean and failing chart exit codes intact.

    Args:
        tmp_path (Path): Stub CLI and per-chart output directory.

    Returns:
        None: One invocation writes the same diagnostic to the console and retained log.
    """
    binary = tmp_path / "hypothesis-helm"
    binary.write_text(
        dedent(f"""
            #!{sys.executable}
            import sys
            from pathlib import Path
            from hypothesis_helm.reporting.console.summary import print_summary
            assert sys.argv[sys.argv.index('--log-file') + 1] == '/dev/stderr'
            assert sys.argv[sys.argv.index('--disable-codes') + 1] == 'HH2006'
            assert sys.argv[sys.argv.index('--shard') + 1] == 'none'
            report = Path('run/saved results/scan.json')
            report.parent.mkdir(parents=True)
            report.write_text('{{"status":"failed"}}')
            print_summary({{'status': 'failed'}}, report)
            print('[WARNING] Finding observed: [HH1101] invalid YAML', file=sys.stderr, flush=True)
            raise SystemExit(1)
        """).lstrip()
    )
    binary.chmod(0o755)
    (tmp_path / "run/jobs").mkdir(parents=True)
    recipe = PROJECT_ROOT / "pkg/hypothesis_helm_benchmarking/refresh/recipes/repository-chart.sh"
    process = subprocess.run(
        ["bash", str(recipe), "chart", "1", "1", "run"],
        cwd=tmp_path,
        env={**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}"},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert process.returncode == 1
    assert "[HH1101]" in process.stdout
    log = (tmp_path / "run/jobs/1.err").read_text()
    summary = (tmp_path / "run/jobs/1.out").read_text()
    assert log == "[WARNING] Finding observed: [HH1101] invalid YAML\n"
    assert summary == "Test failed.\nResults saved: run/saved results/scan.json\n"
    assert process.stdout == log + summary
    assert json.loads((tmp_path / "run/jobs/1.json").read_text()) == {"status": "failed"}
    assert not (tmp_path / "run/jobs/1.json.pending").exists()

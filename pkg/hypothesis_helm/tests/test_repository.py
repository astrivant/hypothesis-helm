"""
Remote repository discovery, provenance, cleanup, and checkout failure reporting.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

from hypothesis_helm.charts.repository import remote_name, run_git
from hypothesis_helm.cli import main


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/example/charts.git",
        "https://github.com/example/charts/",
        "git@github.com:example/charts.git",
        "ssh://git@github.com/example/charts.git",
    ],
)
def test_remote_scan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], url: str) -> None:
    """
    Clone with real Git through a local URL rewrite and scan the resulting chart.

    Args:
        tmp_path (Path): Local Git origin and retained artifacts.
        monkeypatch (pytest.MonkeyPatch): Configure Git transport and fake only chart tests.
        capsys (pytest.CaptureFixture[str]): Capture the aggregate JSON report.
        url (str): Public clone URL spelling preserved through the CLI.

    Returns:
        None: Reports identify the original URL and commit after checkout cleanup.
    """
    import hypothesis_helm.charts.scan as scanner

    if shutil.which("git") is None:
        pytest.skip("Git required")
    origin = tmp_path / "origin"
    origin.mkdir()
    subprocess.run(["git", "init", str(origin)], check=True, capture_output=True)
    chart = origin / "nested" / "demo"
    chart.mkdir(parents=True)
    (chart / "Chart.yaml").write_text(
        dedent("""
        apiVersion: v2
        name: demo
        version: 1.0.0
    """)
    )
    (chart / "values.yaml").write_text("{}\n")
    subprocess.run(["git", "-C", str(origin), "add", "."], check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(origin),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-m",
            "fixture",
        ],
        check=True,
        capture_output=True,
    )
    revision = subprocess.check_output(["git", "-C", str(origin), "rev-parse", "HEAD"], text=True).strip()
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", f"url.{origin.as_uri()}.insteadOf")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", url)
    monkeypatch.setenv("GIT_ALLOW_PROTOCOL", "file")
    roots: list[Path] = []
    discover = scanner.discover_charts

    def inspect(root: Path, *, deadline: float | None = None) -> list[dict[str, object]]:
        """
        Record the checkout while exercising actual recursive discovery.

        Args:
            root (Path): Temporary Git working tree.
            deadline (float | None): Total scan deadline.

        Returns:
            list[dict[str, object]]: Discovered chart metadata.
        """
        roots.append(root)
        return discover(root, deadline=deadline)

    monkeypatch.setattr(scanner, "discover_charts", inspect)
    monkeypatch.setattr(scanner, "exercise_chart", lambda *args: {"status": "passed", "attempts": 3})
    monkeypatch.chdir(tmp_path)
    assert (
        main(
            [
                "scan",
                url,
                "--helm",
                "/usr/bin/true",
                "--no-build-dependencies",
                "--report",
                "--artifact-dir",
                str(tmp_path / "artifacts"),
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["directory"] == url
    assert report["source"] == {"url": url, "revision": revision, "checkout_status": "ready"}
    assert report["charts"][0]["chart"] == "nested/demo"
    assert report["charts"][0]["values_file"] == "nested/demo/values.yaml"
    assert report["counts"] == {"passed": 1}
    assert roots and not roots[0].exists()
    markdown = next(tmp_path.glob("charts_*_report.md"))
    assert url in markdown.read_text() and revision in markdown.read_text()
    assert markdown.with_suffix(".pdf").exists()
    assert list((tmp_path / "artifacts").glob("charts_*/checkout.txt"))


@pytest.mark.parametrize("failure", ["authentication", "clone-timeout", "scan-timeout", "interrupted"])
def test_checkout_failure_reports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure: str,
) -> None:
    """
    Preserve failed checkout reports without claiming an empty successful discovery.

    Args:
        tmp_path (Path): Report destination.
        monkeypatch (pytest.MonkeyPatch): Simulate Git failures at the transport boundary.
        capsys (pytest.CaptureFixture[str]): Capture JSON status.
        failure (str): Checkout failure or deadline to simulate.

    Returns:
        None: Exit codes, diagnostics, and cleanup match the failure mode.
    """
    import time

    roots: list[Path] = []

    def fail(command: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
        """
        Fail clone before chart discovery.

        Args:
            command (list[str]): Git clone command.
            timeout (float): Remaining budget.

        Returns:
            subprocess.CompletedProcess[str]: Failed authentication, or an exception.
        """
        roots.append(Path(command[-1]))
        if failure == "interrupted":
            raise KeyboardInterrupt()
        if failure.endswith("timeout"):
            if failure == "scan-timeout":
                time.sleep(timeout + 0.01)
            raise subprocess.TimeoutExpired(command, timeout)
        return subprocess.CompletedProcess(command, 128, "", "Permission denied (publickey)")

    monkeypatch.setattr("hypothesis_helm.charts.repository.run_git", fail)
    arguments = [
        "scan",
        "git@github.com:example/charts.git",
        "--helm",
        "/usr/bin/true",
        "--report",
        str(tmp_path / "result"),
        "--artifact-dir",
        str(tmp_path / "out"),
    ]
    if failure == "scan-timeout":
        arguments.extend(["--scan-timeout", "0.05s"])
    code = main(arguments)
    assert code == {"authentication": 1, "clone-timeout": 124, "scan-timeout": 124, "interrupted": 130}[failure]
    report = json.loads(capsys.readouterr().out)
    assert report["scan_status"] == ("clone-failed" if failure == "authentication" else failure)
    assert report["discovery_complete"] is False
    assert report["charts_discovered"] == 0
    assert report["source"]["revision"] is None
    assert report["error"]
    assert not roots[0].parent.exists()
    assert "checkout did not complete" in (tmp_path / "result.md").read_text()


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/a",
        "file:///tmp/repo",
        "ext::command",
        "https://token@example.com/repo",
        "https://example.com/",
    ],
)
def test_invalid_remote_source(url: str) -> None:
    """
    Reject unsupported transports and embedded credentials before invoking Git.

    Args:
        url (str): Unsupported or malformed repository location.

    Returns:
        None: Invalid URLs cannot reach the clone command.
    """
    with pytest.raises(ValueError):
        remote_name(url)
    assert remote_name("./charts") is None


def test_git_timeout_reaps_process(tmp_path: Path) -> None:
    """
    Stop a blocked Git transport without leaving the child running.

    Args:
        tmp_path (Path): PID recording location.

    Returns:
        None: The checkout subprocess has exited before timeout propagates.
    """
    pid = tmp_path / "pid"
    command = [
        sys.executable,
        "-c",
        "import os,sys,time; open(sys.argv[1], 'w').write(str(os.getpid())); time.sleep(10)",
        str(pid),
    ]
    with pytest.raises(subprocess.TimeoutExpired):
        run_git(command, 0.3)
    with pytest.raises(ProcessLookupError):
        os.kill(int(pid.read_text()), 0)

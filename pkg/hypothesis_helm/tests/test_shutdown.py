"""
Verify graceful interruption, descendant cleanup, and partial reports.
"""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import cast
from unittest.mock import Mock

import pytest

from hypothesis_helm.execution.processes import Processes, _signal_group


@pytest.mark.parametrize("sig", [0, signal.SIGINT, signal.SIGTERM, signal.SIGKILL])
@pytest.mark.parametrize("disappears", [False, True])
def test_group_permission_race_is_rechecked(monkeypatch: pytest.MonkeyPatch, sig: int, disappears: bool) -> None:
    """
    Recheck transient permission failures for both shutdown signals and existence probes.

    Args:
        monkeypatch (pytest.MonkeyPatch): Substitute deterministic operating-system outcomes.
        sig (int): Probe or shutdown signal encountering the race.
        disappears (bool): Whether retry confirms disappearance or a still-signalable group.

    Returns:
        None: An exited leader never causes live descendants to be skipped.
    """
    child = Mock(spec=subprocess.Popen, pid=12345)
    child.poll.return_value = 0
    send = Mock(side_effect=[PermissionError(1, "Operation not permitted"), ProcessLookupError() if disappears else None])
    monkeypatch.setattr(os, "killpg", send)
    assert _signal_group(child, sig) is not disappears
    assert send.call_count == 2
    send.assert_called_with(child.pid, sig)
    child.poll.assert_called_once()


def test_group_permission_denial_is_not_hidden(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Keep a persistent permission denial visible instead of claiming descendants exited.

    Args:
        monkeypatch (pytest.MonkeyPatch): Substitute a persistent operating-system denial.

    Returns:
        None: Cleanup fails explicitly when group disappearance cannot be confirmed.
    """
    child = Mock(spec=subprocess.Popen, pid=12345)
    child.poll.return_value = 0
    monkeypatch.setattr(os, "killpg", Mock(side_effect=PermissionError(1, "Operation not permitted")))
    with pytest.raises(PermissionError):
        _signal_group(child, signal.SIGTERM, permission_grace=0)


@pytest.mark.parametrize(("jobs", "stubborn"), [("1", False), ("auto", False), ("2", True)])
def test_interrupt_stops_process_groups(tmp_path: Path, jobs: str, stubborn: bool) -> None:
    """
    Interrupt only the CLI and verify that workers and descendants are stopped.

    Args:
        tmp_path (Path): Directory containing the interruptible saved suite.
        jobs (str): Serial, adaptive, or fixed parallel execution.
        stubborn (bool): Whether the active worker ignores cooperative shutdown signals.

    Returns:
        None: Exit 130 preserves partial results and leaves no live child processes.
    """
    (tmp_path / "test_chart_values.py").write_text(
        """
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
import pytest
from hypothesis_helm.reporting.output import emit_manifest

@pytest.mark.parametrize("index", range(8))
def test_shutdown(index):
    if index == 0:
        emit_manifest({"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "done"}})
        return
    if index != 1:
        time.sleep(60)
        return
    stubborn = os.environ["STUBBORN"] == "1"
    if stubborn:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    child = subprocess.Popen([sys.executable, "-c",
        "import signal,time; signal.signal(signal.SIGINT, signal.SIG_IGN); "
        + ("signal.signal(signal.SIGTERM, signal.SIG_IGN); " if stubborn else "")
        + "time.sleep(60)"])
    Path("ready.json").write_text(json.dumps([os.getpid(), child.pid]))
    time.sleep(60)
"""
    )
    environment = dict(os.environ, STUBBORN=str(int(stubborn)), PYTHON_CPU_COUNT="2")
    output_file = tmp_path / "stdout.log"
    diagnostics_file = tmp_path / "stderr.log"
    # Workers can fill an unread pipe before writing the readiness/JUnit files.
    with output_file.open("w") as output_stream, diagnostics_file.open("w") as diagnostics_stream:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "hypothesis_helm.cli",
                "run",
                str(tmp_path),
                "--jobs",
                jobs,
                "--traversal-strategy",
                "linear",
                "-o",
                "json",
            ],
            cwd=tmp_path,
            env=environment,
            stdout=output_stream,
            stderr=diagnostics_stream,
            text=True,
            start_new_session=True,
        )
    owned: list[int] = []
    try:
        deadline = time.monotonic() + 20
        ready = tmp_path / "ready.json"
        while not ready.exists() and time.monotonic() < deadline and process.poll() is None:
            time.sleep(0.05)
        assert ready.exists(), diagnostics_file.read_text()
        owned = json.loads(ready.read_text())
        if jobs != "1":
            while not list(tmp_path.glob("workers-*/junit-0.xml")) and time.monotonic() < deadline:
                time.sleep(0.05)
            assert list(tmp_path.glob("workers-*/junit-0.xml")), diagnostics_file.read_text()
        process.send_signal(signal.SIGINT)
        process.wait(timeout=15)
        output, diagnostics = output_file.read_text(), diagnostics_file.read_text()
        assert process.returncode == 130, diagnostics
        assert json.loads((tmp_path / "report.json").read_text())["status"] == "interrupted"
        assert "test_shutdown[0]" in (tmp_path / "junit.xml").read_text()
        cached = json.loads(next((tmp_path / "cache").rglob("*.json")).read_text())
        assert cached["test_chart_values.py::test_shutdown[0]"] == "passed"
        assert cached.get("test_chart_values.py::test_shutdown[1]") != "passed"
        assert json.loads(output.splitlines()[0])["metadata"]["name"] == "done"
        assert "Interrupted" in diagnostics or "interrupted" in diagnostics
        for pid in owned:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.05)
            else:
                pytest.fail(f"child {pid} survived shutdown")
        if jobs != "1":
            feedback = json.loads((tmp_path / "concurrency.json").read_text())
            assert feedback["interrupted"]
            assert feedback["not_started"]
    finally:
        if owned:
            try:
                os.killpg(owned[0], signal.SIGKILL)
            except ProcessLookupError:
                pass
        if process.poll() is None:
            process.kill()
        process.wait()


def test_shutdown_prevents_new_children(tmp_path: Path) -> None:
    """
    Ensure queued work cannot spawn a child after the shutdown barrier is set.

    Args:
        tmp_path (Path): Directory where an incorrectly launched process would write a file.

    Returns:
        None: The launch returns interrupted without executing any child code.
    """
    processes = Processes()
    processes.stop()
    result = processes.run(
        [sys.executable, "-c", "from pathlib import Path; Path('unexpected').touch()"],
        cwd=tmp_path,
        env=dict(os.environ),
    )
    assert result.returncode == 130
    assert not (tmp_path / "unexpected").exists()


def test_communication_failure_reaps_owned_worker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Retain ownership when communicate fails before the subprocess has exited.

    Args:
        tmp_path (Path): Isolated worker directory.
        monkeypatch (pytest.MonkeyPatch): Inject a pipe-read failure after a real spawn.

    Returns:
        None: The original error propagates after the worker is joined and pipes are closed.
    """
    children: list[subprocess.Popen[str]] = []
    create = subprocess.Popen

    def spawn(*args: object, **kwargs: object) -> subprocess.Popen[str]:
        """
        Record a real process before simulating a communication failure.

        Args:
            *args (object): Arguments passed through to Popen.
            **kwargs (object): Keyword arguments passed through to Popen.

        Returns:
            subprocess.Popen[str]: Real worker with an injected read error.
        """
        child = cast("subprocess.Popen[str]", create(*args, **kwargs))  # type: ignore[call-overload]
        children.append(child)
        monkeypatch.setattr(child, "communicate", Mock(side_effect=OSError("pipe read failed")))
        return child

    monkeypatch.setattr(subprocess, "Popen", spawn)
    processes = Processes(interrupt_grace=0.1)
    with pytest.raises(OSError, match="pipe read failed"):
        processes.run([sys.executable, "-c", "import time; time.sleep(30)"], cwd=tmp_path, env=dict(os.environ), capture_output=True)
    assert len(children) == 1
    child = children[0]
    assert child.returncode is not None
    assert child.stdout is not None and child.stdout.closed
    assert child.stderr is not None and child.stderr.closed
    assert not processes._children
    assert not _signal_group(child, 0)


def test_one_cleanup_failure_does_not_skip_other_children(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Join other workers even when one process group cannot be released.

    Args:
        monkeypatch (pytest.MonkeyPatch): Supply deterministic process-group responses.

    Returns:
        None: Failed ownership remains visible; successfully joined workers are released.
    """
    blocked = Mock(spec=subprocess.Popen, pid=10001, stdin=None, stdout=None, stderr=None)
    finished = Mock(spec=subprocess.Popen, pid=10002, stdin=None, stdout=None, stderr=None)

    def signal_group(child: subprocess.Popen[str], sig: int) -> bool:
        """
        Refuse access to one group and report the other already gone.

        Args:
            child (subprocess.Popen[str]): Mock child whose group is being inspected.
            sig (int): Signal or probe number.

        Returns:
            bool: False for the released group.
        """
        if child is blocked:
            raise PermissionError("cannot signal owned group")
        return False

    monkeypatch.setattr("hypothesis_helm.execution.processes._signal_group", signal_group)
    processes = Processes(interrupt_grace=0)
    processes._children.update((blocked, finished))
    with pytest.raises(ExceptionGroup, match="Failed to release"):
        processes.stop()
    blocked.wait.assert_called_once()
    finished.wait.assert_called_once()
    assert processes._children == {blocked}

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

import pytest

from hypothesis_helm.execution.processes import Processes


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
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    owned: list[int] = []
    try:
        deadline = time.monotonic() + 20
        ready = tmp_path / "ready.json"
        while not ready.exists() and time.monotonic() < deadline and process.poll() is None:
            time.sleep(0.05)
        assert ready.exists(), "worker never started"
        owned = json.loads(ready.read_text())
        if jobs != "1":
            while not list(tmp_path.glob("workers-*/junit-0.xml")) and time.monotonic() < deadline:
                time.sleep(0.05)
            assert list(tmp_path.glob("workers-*/junit-0.xml"))
        process.send_signal(signal.SIGINT)
        output, diagnostics = process.communicate(timeout=15)
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

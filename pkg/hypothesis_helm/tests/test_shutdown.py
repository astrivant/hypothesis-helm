"""
Verify graceful interruption, descendant cleanup, and partial reports.
"""

import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from textwrap import dedent
from typing import cast
from unittest.mock import Mock

import pytest

from hypothesis_helm.benchmarking.execution.runner import Job, measure
from hypothesis_helm.charts.registry import HelmTransport
from hypothesis_helm.charts.repository import run_git
from hypothesis_helm.execution.parallel import run_parallel
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


@pytest.mark.parametrize(
    ("jobs", "stubborn", "nested"), [("1", False, False), ("auto", False, False), ("2", True, False), ("1", True, True), ("2", True, True)]
)
@pytest.mark.parametrize("interrupt_signal", [signal.SIGINT, signal.SIGTERM])
def test_interrupt_stops_process_groups(tmp_path: Path, jobs: str, stubborn: bool, nested: bool, interrupt_signal: int) -> None:
    """
    Interrupt only the CLI and verify that workers and descendants are stopped.

    Args:
        tmp_path (Path): Directory containing the interruptible saved suite.
        jobs (str): Serial, adaptive, or fixed parallel execution.
        stubborn (bool): Whether the active worker ignores cooperative shutdown signals.
        nested (bool): Whether an inner command owner must finish before pytest is stopped.
        interrupt_signal (int): Terminal interruption or CI termination delivered to the parent.

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
from hypothesis_helm.execution.processes import Processes

@pytest.mark.parametrize("index", range(8))
def test_shutdown(index):
    if index == 0:
        emit_manifest({"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "done"}})
        return
    if index != 1:
        time.sleep(60)
        return
    stubborn = os.environ["STUBBORN"] == "1"
    if os.environ["NESTED"] == "1":
        Processes().run([sys.executable, "-c",
            "import json,os,signal,time; from pathlib import Path; "
            "signal.signal(signal.SIGINT, signal.SIG_IGN); signal.signal(signal.SIGTERM, signal.SIG_IGN); "
            "Path('ready.json').write_text(json.dumps([os.getppid(),os.getpid()])); time.sleep(60)"])
        return
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
    environment = dict(os.environ, STUBBORN=str(int(stubborn)), NESTED=str(int(nested)), PYTHON_CPU_COUNT="2")
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
        process.send_signal(interrupt_signal)
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


def test_repeated_cancellation_during_join_preserves_siblings(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Deliver repeated termination while joining the first of two owned children.

    Args:
        monkeypatch (pytest.MonkeyPatch): Mark process groups gone without sending real signals.

    Returns:
        None: Both children are joined before pending termination reaches the caller.
    """
    children = [Mock(spec=subprocess.Popen, pid=pid, stdin=None, stdout=None, stderr=None) for pid in (10001, 10002)]

    def interrupted_join(*, timeout: float) -> None:
        """
        Inject repeated cancellation at the join boundary.

        Args:
            timeout (float): Bound applied by the process owner.

        Returns:
            None: The protected join completes despite both signals.
        """
        signal.raise_signal(signal.SIGTERM)
        signal.raise_signal(signal.SIGTERM)

    children[0].wait.side_effect = interrupted_join
    monkeypatch.setattr("hypothesis_helm.execution.processes._signal_group", lambda child, sig: False)
    owner = Processes()
    owner._children.update(children)
    with pytest.raises(KeyboardInterrupt):
        owner.stop()
    for child in children:
        child.wait.assert_called_once()
    assert not owner._children


@pytest.mark.parametrize("transport", ["command", "git", "helm"])
@pytest.mark.parametrize("failure", ["read", "timeout", "success"])
def test_transports_reap_descendants(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, transport: str, failure: str) -> None:
    """
    Exercise shared ownership through real transports, including an already exited leader.

    Args:
        tmp_path (Path): Readiness and child identity files.
        monkeypatch (pytest.MonkeyPatch): Inject a read failure after descendants exist.
        transport (str): External-command, Git or Helm transport boundary.
        failure (str): Communication error, deadline or successful leader completion.

    Returns:
        None: Both leader and descendant are gone before the transport returns or raises.
    """
    ready = tmp_path / "ready.json"
    script = tmp_path / "transport.py"
    script.write_text(
        dedent("""
        import json
        import os
        import subprocess
        import sys
        import time
        from pathlib import Path

        child = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        Path(sys.argv[1]).write_text(json.dumps([os.getpid(), child.pid]))
        if sys.argv[2] != "success":
            time.sleep(30)
    """)
    )
    original = subprocess.Popen.communicate

    def communicate(child: subprocess.Popen[str], *args: object, **kwargs: object) -> tuple[str, str]:
        """
        Fail a live pipe only after the process has created its descendant.

        Args:
            child (subprocess.Popen[str]): Owned transport leader.
            *args (object): Communication input arguments.
            **kwargs (object): Communication deadline arguments.

        Returns:
            tuple[str, str]: Captured streams when no read failure is injected.
        """
        if failure == "read":
            deadline = time.monotonic() + 5
            while not ready.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            raise OSError("injected transport read failure")
        return original(child, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(subprocess.Popen, "communicate", communicate)
    command = [sys.executable, str(script), str(ready), failure]
    try:
        if transport == "git":
            result = run_git(command, 1)
        elif transport == "helm":
            result = HelmTransport(dict(os.environ), time.monotonic() + 1).run(command)
        else:
            result = Processes().run(command, capture_output=True, timeout=1)
    except (OSError, subprocess.TimeoutExpired) as exc:
        assert isinstance(exc, subprocess.TimeoutExpired if failure == "timeout" else OSError)
        assert failure != "success"
    else:
        assert failure == "success"
        assert result.returncode == 0
    assert ready.exists()
    for pid in json.loads(ready.read_text()):
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)


def test_execution_and_cleanup_errors_are_preserved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Preserve both failures while retaining an unjoined worker for a later cleanup attempt.

    Args:
        tmp_path (Path): Unused working directory for the mocked worker.
        monkeypatch (pytest.MonkeyPatch): Inject failures before successful cleanup is retried.

    Returns:
        None: Both causes are reported and unresolved ownership remains registered.
    """
    child = Mock(spec=subprocess.Popen, pid=12345)
    child.communicate.side_effect = OSError("read failed")
    monkeypatch.setattr(subprocess, "Popen", Mock(return_value=child))
    monkeypatch.setattr(Processes, "stop", Mock(side_effect=PermissionError("cleanup failed")))
    owner = Processes()
    with pytest.raises(ExceptionGroup) as errors:
        owner.run(["worker"], cwd=tmp_path)
    assert [str(error) for error in errors.value.exceptions] == ["read failed", "cleanup failed"]
    assert owner._children == {child}


@pytest.mark.skipif(not hasattr(signal, "SIGALRM"), reason="POSIX alarm required")
@pytest.mark.parametrize("before_handler", [False, True])
def test_timeout_alarm_waits_for_real_child_cleanup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, before_handler: bool) -> None:
    """
    Deliver the overall deadline during timeout cleanup without losing the real child.

    Args:
        tmp_path (Path): Isolated subprocess working directory.
        monkeypatch (pytest.MonkeyPatch): Force the two deadlines to overlap deterministically.
        before_handler (bool): Deliver the deadline just before cleanup installs its handler.

    Returns:
        None: The deadline propagates only after the child is joined and handlers are restored.
    """
    from hypothesis_helm.reporting.budget import TimeLimitReached, execution_timer

    children: list[subprocess.Popen[str]] = []
    create = subprocess.Popen
    signal_group = _signal_group
    alarm_delivered = False

    def spawn(*args: object, **kwargs: object) -> subprocess.Popen[str]:
        """
        Start a real worker and simulate its communication timeout.

        Args:
            *args (object): Native Popen arguments.
            **kwargs (object): Native Popen keyword arguments.

        Returns:
            subprocess.Popen[str]: Registered child whose communicate method times out.
        """
        child = cast("subprocess.Popen[str]", create(*args, **kwargs))  # type: ignore[call-overload]
        children.append(child)
        monkeypatch.setattr(child, "communicate", Mock(side_effect=subprocess.TimeoutExpired("worker", 0.01)))
        return child

    def interrupt_cleanup(child: subprocess.Popen[str], sig: int) -> bool:
        """
        Inject the deadline while the owner is still releasing a process group.

        Args:
            child (subprocess.Popen[str]): Real owned worker.
            sig (int): Cleanup signal or existence probe.

        Returns:
            bool: Whether the original process group still exists.
        """
        nonlocal alarm_delivered
        if not alarm_delivered:
            alarm_delivered = True
            signal.raise_signal(signal.SIGALRM)
        return signal_group(child, sig)

    monkeypatch.setattr(subprocess, "Popen", spawn)
    if before_handler:
        stop = Processes.stop

        def interrupt_before_stop(owner: Processes) -> None:
            """
            Deliver the one-shot deadline before entering the cleanup method.

            Args:
                owner (Processes): Owner retaining its unjoined child.

            Returns:
                None: Retried cleanup uses the original method after alarm delivery.
            """
            nonlocal alarm_delivered
            if not alarm_delivered:
                alarm_delivered = True
                signal.raise_signal(signal.SIGALRM)
            stop(owner)

        monkeypatch.setattr(Processes, "stop", interrupt_before_stop)
    else:
        monkeypatch.setattr("hypothesis_helm.execution.processes._signal_group", interrupt_cleanup)
    previous_alarm, previous_interrupt = signal.getsignal(signal.SIGALRM), signal.getsignal(signal.SIGINT)
    owner = Processes(interrupt_grace=0.1)
    with pytest.raises(TimeLimitReached) as failure, execution_timer(30):
        owner.run([sys.executable, "-c", "import time; time.sleep(30)"], cwd=tmp_path, capture_output=True, timeout=0.01)
    assert isinstance(failure.value.__cause__, subprocess.TimeoutExpired)
    assert len(children) == 1 and children[0].returncode is not None
    assert not owner._children and not signal_group(children[0], 0)
    assert children[0].stdout is not None and children[0].stdout.closed
    assert signal.getsignal(signal.SIGALRM) == previous_alarm
    assert signal.getsignal(signal.SIGINT) == previous_interrupt


@pytest.mark.skipif(not hasattr(signal, "SIGALRM"), reason="POSIX alarm required")
def test_deferred_deadline_preserves_cleanup_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Keep a real cleanup failure visible when the deadline also expires.

    Args:
        monkeypatch (pytest.MonkeyPatch): Supply a child that cannot be joined and an overlapping alarm.

    Returns:
        None: Both causes remain visible and unsuccessful ownership is retained.
    """
    from hypothesis_helm.reporting.budget import TimeLimitReached, execution_timer

    child = Mock(spec=subprocess.Popen, pid=12345, stdin=None, stdout=None, stderr=None)
    child.wait.side_effect = OSError("join failed")
    owner = Processes()
    owner._children.add(child)

    def gone(child: subprocess.Popen[str], sig: int) -> bool:
        """
        Report an exited process group after delivering a cleanup-time alarm.

        Args:
            child (subprocess.Popen[str]): Owned test worker.
            sig (int): Group signal number.

        Returns:
            bool: False to proceed to the failing join.
        """
        signal.raise_signal(signal.SIGALRM)
        return False

    monkeypatch.setattr("hypothesis_helm.execution.processes._signal_group", gone)
    with pytest.raises(BaseExceptionGroup) as failure, execution_timer(30):
        owner.stop()
    assert failure.value.subgroup(OSError) is not None
    assert failure.value.subgroup(TimeLimitReached) is not None
    assert owner._children == {child}
    child.wait.assert_called_once()


@pytest.mark.parametrize("cleanup_fails", [False, True])
def test_scheduler_joins_threads_after_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cleanup_fails: bool) -> None:
    """
    Join a live sibling even when scheduling and process cleanup both fail.

    Args:
        tmp_path (Path): Collection and report directory.
        monkeypatch (pytest.MonkeyPatch): Replace child execution while retaining real worker threads.
        cleanup_fails (bool): Whether cleanup raises after requesting the sibling to stop.

    Returns:
        None: The sibling has finished and every executor thread is joined before error propagation.
    """
    started, stopped, finished = threading.Event(), threading.Event(), threading.Event()

    def execute(owner: Processes, command: list[str], *, env: dict[str, str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        """
        Collect two properties and fail the first only after its sibling is running.

        Args:
            owner (Processes): Shared process owner.
            command (list[str]): Collection or worker invocation.
            env (dict[str, str]): Collection destinations.
            **kwargs (object): Other execution options.

        Returns:
            subprocess.CompletedProcess[str]: Successful collection or stopped sibling.
        """
        if "--collect-only" in command:
            Path(env["HYPOTHESIS_HELM_COLLECT"]).write_text(json.dumps(["test_chart_values.py::first", "test_chart_values.py::second"]))
        elif command[-1].endswith("::first"):
            assert started.wait(5)
            raise OSError("worker failed")
        else:
            started.set()
            try:
                assert stopped.wait(5)
            finally:
                finished.set()
        return subprocess.CompletedProcess(command, 0, "", "")

    def stop(owner: Processes) -> None:
        """
        Unblock the sibling while optionally failing cleanup.

        Args:
            owner (Processes): Shared process owner.

        Returns:
            None: A waiting worker receives the shutdown request.
        """
        stopped.set()
        if cleanup_fails:
            raise PermissionError("cleanup failed")

    monkeypatch.setattr(Processes, "run", execute)
    monkeypatch.setattr(Processes, "stop", stop)
    with pytest.raises(OSError, match="cleanup failed" if cleanup_fails else "worker failed"):
        run_parallel(["pytest", "--junitxml", "junit.xml", "test_chart_values.py"], tmp_path, {}, None, 2)
    assert finished.is_set()
    assert not any(thread.name.startswith("helm-hypothesis") for thread in threading.enumerate())


def _failing_replica(job: Job) -> dict[str, object]:
    """
    Fail one spawned replica while another records its completed work.

    Args:
        job (Job): Disjoint worker assignment with a directory for completion markers.

    Returns:
        dict[str, object]: An unused result from the surviving replica.
    """
    if 0 in job.indices:
        raise OSError("replica failed")
    time.sleep(0.2)
    Path(job.chart, "replica-finished").touch()
    return {}


def test_benchmark_pool_joins_after_replica_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Verify the benchmark pool's existing shutdown barrier with real spawned processes.

    Args:
        tmp_path (Path): Replica completion directory.
        monkeypatch (pytest.MonkeyPatch): Substitute a deterministic failing replica.

    Returns:
        None: A sibling finishes before the failed benchmark returns control.
    """
    monkeypatch.setattr("hypothesis_helm.benchmarking.execution.runner.execute_profiled_worker", _failing_replica)
    with pytest.raises(OSError, match="replica failed"):
        measure(tmp_path, 2, 2, False, seed=0, multiplicity=1, time_limit=5, helm="helm", shard=None)
    assert (tmp_path / "replica-finished").exists()


@pytest.mark.parametrize("interrupt_signal", [signal.SIGINT, signal.SIGTERM, signal.SIGALRM])
def test_registration_finishes_before_cancellation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, interrupt_signal: int) -> None:
    """
    Cancel after OS process creation but before the process owner registers the child.

    Args:
        tmp_path (Path): Child working directory.
        monkeypatch (pytest.MonkeyPatch): Deliver cancellation at the registration boundary.
        interrupt_signal (int): Interrupt, termination or active deadline signal.

    Returns:
        None: The child is registered, stopped and joined before cancellation propagates.
    """
    from hypothesis_helm.reporting.budget import TimeLimitReached, execution_timer

    created: list[subprocess.Popen[str]] = []
    spawn = subprocess.Popen

    def interrupt(*args: object, **kwargs: object) -> subprocess.Popen[str]:
        """
        Deliver the signal after creating a real process and before returning its handle.

        Args:
            *args (object): Native process creation arguments.
            **kwargs (object): Native process creation options.

        Returns:
            subprocess.Popen[str]: A handle whose ownership must survive cancellation.
        """
        child = cast("subprocess.Popen[str]", spawn(*args, **kwargs))  # type: ignore[call-overload]
        created.append(child)
        signal.raise_signal(interrupt_signal)
        return child

    monkeypatch.setattr(subprocess, "Popen", interrupt)
    previous = signal.getsignal(interrupt_signal)
    owner = Processes()
    expected = TimeLimitReached if interrupt_signal == signal.SIGALRM else KeyboardInterrupt
    with pytest.raises(expected), execution_timer(30):
        owner.run([sys.executable, "-c", "import time; time.sleep(30)"], cwd=tmp_path, capture_output=True)
    assert len(created) == 1 and created[0].returncode is not None
    assert not owner._children
    assert not _signal_group(created[0], 0)
    assert signal.getsignal(interrupt_signal) == previous


@pytest.mark.parametrize("stop", ["interrupt", "terminate", "deadline", "parallel-timeout"])
def test_benchmark_cancellation_reaps_nested_replicas(tmp_path: Path, stop: str) -> None:
    """
    Cancel only the coordinator while replicas own renderer processes and descendants.

    Args:
        tmp_path (Path): Fake renderer, chart and retained shutdown evidence.
        stop (str): Parent signal, worker deadline, or GNU Parallel job timeout.

    Returns:
        None: Partial statistics survive and all recorded processes have exited.
    """
    from hypothesis_helm.benchmarking.charts.generator import generate

    if stop == "parallel-timeout" and shutil.which("parallel") is None:
        pytest.skip("GNU Parallel is required for the outer timeout test")
    chart = tmp_path / "chart"
    generate(chart, input_complexity=6)
    renderer = tmp_path / "helm"
    renderer.write_text(
        f"#!{sys.executable}\n"
        + dedent(
            """
            import json, os, signal, subprocess, sys, time
            from pathlib import Path
            child = subprocess.Popen([sys.executable, '-c',
                'import signal,time; signal.signal(signal.SIGINT,signal.SIG_IGN); time.sleep(60)'])
            Path(f'ready-{os.getpid()}.json').write_text(json.dumps([os.getppid(), os.getpid(), child.pid]))
            time.sleep(60)
            """
        ).lstrip()
    )
    renderer.chmod(0o755)
    driver = tmp_path / "driver.py"
    driver.write_text(
        dedent(
            """
            import json
            from pathlib import Path
            from hypothesis_helm.benchmarking.execution.runner import measure
            if __name__ == '__main__':
                result = measure(Path('chart'), 12, 2, False, seed=0, multiplicity=8,
                                 time_limit=5 if Path('deadline').exists() else 30,
                                 helm=str(Path('helm').resolve()), shard=None)
                Path('result.json').write_text(json.dumps(result))
            """
        )
    )
    if stop == "deadline":
        (tmp_path / "deadline").touch()
    command = [sys.executable, str(driver)]
    if stop == "parallel-timeout":
        command = [
            "parallel",
            "--plain",
            "--jobs",
            "1",
            "--timeout",
            "5",
            "--term-seq",
            "TERM,10000,KILL,1000",
            "--quote",
            *command,
            ":::",
            "one",
        ]
    owned: list[int] = []
    with (tmp_path / "log.txt").open("w") as log:
        parent = subprocess.Popen(command, cwd=tmp_path, stdout=log, stderr=log, start_new_session=True)
    try:
        deadline = time.monotonic() + 20
        while len(list(tmp_path.glob("ready-*.json"))) < 2 and time.monotonic() < deadline and parent.poll() is None:
            time.sleep(0.05)
        ready = list(tmp_path.glob("ready-*.json"))
        assert len(ready) == 2, (tmp_path / "log.txt").read_text()
        owned = [pid for path in ready for pid in json.loads(path.read_text())]
        if stop in {"interrupt", "terminate"}:
            parent.send_signal(signal.SIGINT if stop == "interrupt" else signal.SIGTERM)
        parent.wait(timeout=15)
        assert parent.returncode == (1 if stop == "parallel-timeout" else 0), (tmp_path / "log.txt").read_text()
        report = json.loads((tmp_path / "result.json").read_text())
        assert report["status"] == ("time-limit" if stop == "deadline" else "interrupted")
        assert report["assigned"] == report["completed"] + report["remaining"] == 12
        assert report["completed"] == 0 and len(report["workers"]) == 2
        for pid in owned:
            with pytest.raises(ProcessLookupError):
                os.kill(pid, 0)
    finally:
        for pid in owned:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if parent.poll() is None:
            parent.kill()
        parent.wait(timeout=10)

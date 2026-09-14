"""
Own external process groups and stop their descendants on every exit path.
"""

import os
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import TextIO

from attrs import define, field

from hypothesis_helm.execution.signals import DeferredSignals, Termination
from hypothesis_helm.reporting.budget import TimeLimitReached


def _signal_group(child: subprocess.Popen[str], sig: int, *, permission_grace: float = 1.0) -> bool:
    """
    Signal an owned group, allowing a bounded retry while its members finish exiting.

    Darwin can return EPERM for a group containing only exiting or zombie processes.
    Reap the direct child and retry; only ESRCH establishes that the whole group is gone.
    A terminated leader alone does not establish that its descendants have stopped.

    Args:
        child (subprocess.Popen[str]): Owned process whose PID is the group identifier.
        sig (int): Signal to deliver, or zero to probe group existence.
        permission_grace (float): Maximum seconds to retry a transient permission error.

    Returns:
        bool: True if the group accepted the signal, False if it no longer exists.
    """
    deadline = time.monotonic() + permission_grace
    while True:
        try:
            os.killpg(child.pid, sig)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            child.poll()
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.02)


@define
class Processes:
    """
    Track child process groups with a shutdown barrier around process creation.
    """

    _interrupt_grace: float = 0.5
    _lock: threading.Lock = field(factory=threading.Lock)
    _shutdown_lock: threading.Lock = field(factory=threading.Lock)
    _stopping: threading.Event = field(factory=threading.Event)
    _children: set[subprocess.Popen[str]] = field(factory=set)

    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        capture_output: bool = False,
        text: bool = True,
        check: bool = False,
        pass_fds: tuple[int, ...] = (),
        stdout: TextIO | None = None,
        stderr: TextIO | None = None,
        input: str | None = None,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """
        Run a child in a new session and retain ownership until it has exited.

        Args:
            command (list[str]): Child invocation.
            cwd (Path | None): Working directory, or inherit the current directory.
            env (dict[str, str] | None): Child environment, or inherit the current environment.
            capture_output (bool): Whether to collect stdout and stderr.
            text (bool): Whether subprocess pipes use text mode.
            check (bool): Whether nonzero exits raise a subprocess error.
            pass_fds (tuple[int, ...]): Manifest descriptors inherited by the child.
            stdout (TextIO | None): Destination for uncaptured child stdout.
            stderr (TextIO | None): Destination for uncaptured child stderr.
            input (str | None): Text written to the child's standard input.
            timeout (float | None): Communication deadline in seconds, excluding cleanup.

        Returns:
            subprocess.CompletedProcess[str]: Collected process result.
        """
        with Termination():
            try:
                with DeferredSignals():
                    with self._lock:
                        if self._stopping.is_set():
                            return subprocess.CompletedProcess(command, 130, "", "")
                        child = subprocess.Popen(
                            command,
                            cwd=cwd,
                            env=env,
                            text=text,
                            stdin=subprocess.PIPE if input is not None else None,
                            stdout=subprocess.PIPE if capture_output else stdout,
                            stderr=subprocess.PIPE if capture_output else stderr,
                            pass_fds=pass_fds,
                            start_new_session=True,
                        )
                        self._children.add(child)
                output, errors = child.communicate(input=input, timeout=timeout)
                with self._shutdown_lock:
                    # A completed parent can leave descendants in its owned session.
                    # Ownership ends only after the complete group has been stopped.
                    with self._lock:
                        owned = child in self._children
                    if owned:
                        self._reap([child])
            except BaseException as error:
                try:
                    self.stop()
                except BaseException as cleanup_error:
                    if isinstance(cleanup_error, TimeLimitReached) and self._children:
                        # The one-shot alarm can arrive before stop installs its handler.
                        # Retry cleanup after delivery, retaining ownership until it succeeds.
                        try:
                            self.stop()
                        except BaseException as retry_error:
                            raise BaseExceptionGroup("Process execution and cleanup failed", [error, cleanup_error, retry_error]) from None
                    if isinstance(error, subprocess.TimeoutExpired) and isinstance(cleanup_error, TimeLimitReached) and not self._children:
                        raise cleanup_error from error
                    raise BaseExceptionGroup("Process execution and cleanup failed", [error, cleanup_error]) from None
                raise
            result = subprocess.CompletedProcess(command, child.returncode, output, errors)
            if check:
                result.check_returncode()
            return result

    def _reap(self, children: list[subprocess.Popen[str]]) -> None:
        """
        Stop owned descendants and join every parent before releasing its registry entry.

        Args:
            children (list[subprocess.Popen[str]]): Snapshot protected by the shutdown lock.

        Returns:
            None: Every group is gone and every direct child has been joined.
        """
        groups = set(children)
        failures: dict[subprocess.Popen[str], Exception] = {}
        for sig, grace in (
            (signal.SIGINT, self._interrupt_grace),
            (signal.SIGTERM, 1.0),
            (signal.SIGKILL, 1.0),
        ):
            for child in list(groups):
                try:
                    if not _signal_group(child, sig):
                        groups.remove(child)
                except OSError as exc:
                    failures[child] = exc
            deadline = time.monotonic() + grace
            while groups and time.monotonic() < deadline:
                for child in list(groups):
                    try:
                        child.poll()
                        if not _signal_group(child, 0):
                            groups.remove(child)
                    except OSError as exc:
                        failures[child] = exc
                if groups:
                    time.sleep(0.02)
        errors = []
        for child in children:
            try:
                child.wait(timeout=2.0)
                if child in groups:
                    raise failures.get(child, RuntimeError(f"owned process group {child.pid} did not stop"))
                for stream in (child.stdin, child.stdout, child.stderr):
                    if stream is not None:
                        stream.close()
            except Exception as exc:
                errors.append(exc)
            else:
                with self._lock:
                    self._children.discard(child)
        if errors:
            raise ExceptionGroup("Failed to release owned worker process groups", errors)

    def stop(self) -> None:
        """
        Stop scheduling and interrupt, terminate, then kill remaining process groups.

        Returns:
            None: Owned children are reaped after a bounded cooperative shutdown period.
        """
        with DeferredSignals():
            with self._lock:
                self._stopping.set()
            with self._shutdown_lock:
                with self._lock:
                    children = list(self._children)
                self._reap(children)

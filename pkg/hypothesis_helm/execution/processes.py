"""
Own pytest process groups and stop their descendants on interruption.
"""

import os
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import TextIO

from attrs import define, field


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

    _interrupt_grace: float = 2.0
    _lock: threading.Lock = field(factory=threading.Lock)
    _stopping: threading.Event = field(factory=threading.Event)
    _children: set[subprocess.Popen[str]] = field(factory=set)

    def run(
        self,
        command: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        capture_output: bool = False,
        text: bool = True,
        check: bool = False,
        pass_fds: tuple[int, ...] = (),
        stdout: TextIO | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """
        Run a child in a new session and retain ownership until it has exited.

        Args:
            command (list[str]): Child invocation.
            cwd (Path): Working directory for the child.
            env (dict[str, str]): Child environment.
            capture_output (bool): Whether to collect stdout and stderr.
            text (bool): Whether subprocess pipes use text mode.
            check (bool): Whether nonzero exits raise a subprocess error.
            pass_fds (tuple[int, ...]): Manifest descriptors inherited by the child.
            stdout (TextIO | None): Destination for uncaptured child stdout.

        Returns:
            subprocess.CompletedProcess[str]: Collected process result.
        """
        with self._lock:
            if self._stopping.is_set():
                return subprocess.CompletedProcess(command, 130, "", "")
            child = subprocess.Popen(
                command,
                cwd=cwd,
                env=env,
                text=text,
                stdout=subprocess.PIPE if capture_output else stdout,
                stderr=subprocess.PIPE if capture_output else None,
                pass_fds=pass_fds,
                start_new_session=True,
            )
            self._children.add(child)
        try:
            output, errors = child.communicate()
            result = subprocess.CompletedProcess(command, child.returncode, output, errors)
            if check:
                result.check_returncode()
            return result
        except KeyboardInterrupt:
            self.stop()
            raise
        finally:
            with self._lock:
                self._children.discard(child)

    def stop(self) -> None:
        """
        Stop scheduling and interrupt, terminate, then kill remaining process groups.

        Returns:
            None: Owned children are reaped after a bounded cooperative shutdown period.
        """
        main_thread = threading.current_thread() is threading.main_thread()
        previous = signal.signal(signal.SIGINT, signal.SIG_IGN) if main_thread else None
        try:
            with self._lock:
                self._stopping.set()
                children = list(self._children)
            groups = set(children)
            for sig, grace in (
                (signal.SIGINT, self._interrupt_grace),
                (signal.SIGTERM, 1.0),
                (signal.SIGKILL, 0.0),
            ):
                for child in list(groups):
                    if not _signal_group(child, sig):
                        groups.remove(child)
                deadline = time.monotonic() + grace
                while time.monotonic() < deadline:
                    for child in list(groups):
                        child.poll()
                        if not _signal_group(child, 0):
                            groups.remove(child)
                    if not groups:
                        break
                    time.sleep(0.02)
            for child in children:
                child.wait()
        finally:
            if main_thread and previous is not None:
                signal.signal(signal.SIGINT, previous)

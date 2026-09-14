"""
Defer cancellation across ownership changes and translate CI termination into unwinding.
"""

import signal
import threading
from types import FrameType, TracebackType
from typing import Self


class Termination:
    """
    Give default SIGTERM cancellation the same cleanup path as KeyboardInterrupt.
    """

    def __init__(self) -> None:
        """
        Prepare a scope without changing caller-installed signal handlers.
        """
        self.installed = False

    def __enter__(self) -> Self:
        """
        Install an unwinding handler only on the main thread with default SIGTERM.

        Returns:
            Self: Scope that restores the original default on exit.
        """
        if threading.current_thread() is threading.main_thread() and signal.getsignal(signal.SIGTERM) == signal.SIG_DFL:
            signal.signal(signal.SIGTERM, signal.default_int_handler)
            self.installed = True
        return self

    def __exit__(self, kind: type[BaseException] | None, error: BaseException | None, traceback: TracebackType | None) -> None:
        """
        Restore the original termination behavior after owned work has stopped.

        Args:
            kind (type[BaseException] | None): Propagating exception type.
            error (BaseException | None): Original exception.
            traceback (TracebackType | None): Original traceback.

        Returns:
            None: Cancellation remains visible to the caller.
        """
        if self.installed:
            signal.signal(signal.SIGTERM, signal.SIG_DFL)


class DeferredSignals:
    """
    Finish a short ownership or cleanup operation before delivering cancellation.
    """

    def __init__(self) -> None:
        """
        Record callable handlers and pending signals for this scope.
        """
        self.previous: dict[int, signal._HANDLER] = {}
        self.pending: list[int] = []

    def receive(self, signum: int, frame: FrameType | None) -> None:
        """
        Record cancellation once per signal while a critical operation finishes.

        Args:
            signum (int): Pending signal number.
            frame (FrameType | None): Interrupted Python frame.

        Returns:
            None: Repeated signals cannot skip joining another child.
        """
        if signum not in self.pending:
            self.pending.append(signum)

    def __enter__(self) -> Self:
        """
        Defer interrupt, termination and active alarm handlers on the main thread.

        Returns:
            Self: Scope owning temporary handlers.
        """
        if threading.current_thread() is threading.main_thread():
            for signum in (signal.SIGINT, signal.SIGTERM, *([signal.SIGALRM] if hasattr(signal, "SIGALRM") else [])):
                previous = signal.getsignal(signum)
                if callable(previous) or (signum == signal.SIGTERM and previous == signal.SIG_DFL):
                    self.previous[signum] = previous
                    signal.signal(signum, self.receive)
        return self

    def __exit__(self, kind: type[BaseException] | None, error: BaseException | None, traceback: TracebackType | None) -> None:
        """
        Restore handlers and deliver pending signals without hiding cleanup failures.

        Args:
            kind (type[BaseException] | None): Propagating exception type.
            error (BaseException | None): Error raised during the critical operation.
            traceback (TracebackType | None): Original traceback.

        Returns:
            None: Pending cancellation is raised after the operation finishes.
        """
        for signum, previous in self.previous.items():
            signal.signal(signum, previous)
        failures: list[BaseException] = []
        for signum in self.pending:
            handler = self.previous[signum]
            try:
                if callable(handler):
                    handler(signum, None)
                else:
                    raise KeyboardInterrupt()
            except BaseException as pending:
                failures.append(pending)
        if failures:
            if error is not None:
                failures.insert(0, error)
            if len(failures) == 1:
                raise failures[0]
            raise BaseExceptionGroup("Operation and deferred cancellation failed", failures) from None

"""
Forward coordinator cancellation into spawned replicas without abandoning their children.
"""

import os
import signal
import threading
from multiprocessing.synchronize import Event
from types import TracebackType
from typing import Self

from hypothesis_helm.execution.signals import DeferredSignals

CANCEL: Event | None = None


def initialize(cancel: Event) -> None:
    """
    Receive the explicit cancellation event when a replica starts.

    Args:
        cancel (Event): Event owned by this benchmark coordinator.

    Returns:
        None: Each replica observes cancellation from its own pool only.
    """
    global CANCEL
    CANCEL = cancel
    signal.signal(signal.SIGTERM, signal.default_int_handler)


class Cancellation:
    """
    Own a short-lived watcher that interrupts a replica when its coordinator stops.
    """

    def __init__(self) -> None:
        """
        Create a local stop event and an optional cancellation watcher.
        """
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self.watch, name="benchmark-cancellation") if CANCEL is not None else None

    def watch(self) -> None:
        """
        Deliver cancellation to the replica's main thread, where cleanup can unwind.

        Returns:
            None: The watcher exits after cancellation or normal worker completion.
        """
        while not self.stopped.wait(0.05):
            if CANCEL is not None and CANCEL.is_set():
                os.kill(os.getpid(), signal.SIGINT)
                return

    def __enter__(self) -> Self:
        """
        Start the watcher while preserving ownership across thread startup.

        Returns:
            Self: Scope responsible for joining the watcher.
        """
        try:
            with DeferredSignals():
                if self.thread is not None:
                    self.thread.start()
        except BaseException:
            with DeferredSignals():
                self.stopped.set()
                if self.thread is not None and self.thread.ident is not None:
                    self.thread.join()
            raise
        return self

    def __exit__(self, kind: type[BaseException] | None, error: BaseException | None, traceback: TracebackType | None) -> None:
        """
        Stop and join the watcher before leaving the worker or propagating an error.

        Args:
            kind (type[BaseException] | None): Propagating exception type.
            error (BaseException | None): Original worker error.
            traceback (TracebackType | None): Original traceback.

        Returns:
            None: No cancellation thread survives the worker call.
        """
        with DeferredSignals():
            self.stopped.set()
            if self.thread is not None:
                self.thread.join()

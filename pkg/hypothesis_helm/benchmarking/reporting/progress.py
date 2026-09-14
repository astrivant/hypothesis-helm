"""
Show benchmark completion counts locally and plain status messages in CI.
"""

import sys
import time
from collections.abc import Iterable, Iterator, Sized
from contextvars import ContextVar, Token
from multiprocessing import current_process
from types import TracebackType
from typing import Self, TypeVar

from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn, TimeElapsedColumn, TimeRemainingColumn

from hypothesis_helm.execution.environment import in_ci

T = TypeVar("T")
ACTIVE: ContextVar[Progress | None] = ContextVar("benchmark_progress", default=None)


class BenchmarkProgress:
    """
    Own a benchmark display, preserving partial counts when work stops early.
    """

    def __init__(self, description: str) -> None:
        """
        Configure a terminal bar or throttled plain-text status output.

        Args:
            description (str): Study, strategy, or operation being measured.
        """
        self.description = description
        self.parent: Progress | None = None
        self.token: Token[Progress | None] | None = None
        console = Console(stderr=True)
        self.interactive = console.is_terminal and not in_ci(honor_override=False) and current_process().name == "MainProcess"
        self.progress = Progress(
            TextColumn("{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TextColumn("ETA"),
            TimeRemainingColumn(),
            console=console,
            disable=not self.interactive,
            auto_refresh=self.interactive,
            refresh_per_second=4,
            redirect_stdout=False,
            redirect_stderr=False,
        )
        self.task = self.progress.add_task(description, total=None)
        self.completed = 0
        self.total = 0
        self.started = time.monotonic()
        self.updated = self.started

    def __enter__(self) -> Self:
        """
        Start the display before visiting benchmark work.

        Returns:
            Self: Explicit owner responsible for closing the display.
        """
        self.started = self.updated = time.monotonic()
        self.parent = ACTIVE.get()
        if self.parent is not None:
            self.progress = self.parent
            self.task = self.progress.add_task(self.description, total=None)
        else:
            self.progress.start()
        self.token = ACTIVE.set(self.progress)
        return self

    def __exit__(self, kind: type[BaseException] | None, error: BaseException | None, traceback: TracebackType | None) -> None:
        """
        Restore terminal output and retain accurate partial completion counts.

        Args:
            kind (type[BaseException] | None): Exception type, when interrupted.
            error (BaseException | None): Original failure, propagated unchanged.
            traceback (TracebackType | None): Original exception traceback.

        Returns:
            None: No benchmark exception is suppressed.
        """
        status = "stopped" if kind is not None or self.completed < self.total else "complete"
        try:
            self.progress.update(self.task, description=f"{self.description}: {status}", refresh=self.interactive)
        finally:
            if self.token is not None:
                ACTIVE.reset(self.token)
            if self.parent is None:
                self.progress.stop()
            else:
                self.progress.remove_task(self.task)
        if not self.interactive:
            self.log(status)

    def log(self, status: str) -> None:
        """
        Write a plain status line without terminal controls or a bar.

        Args:
            status (str): Current lifecycle state.

        Returns:
            None: CI logs include counts, elapsed time and remaining work.
        """
        elapsed = time.monotonic() - self.started
        remaining = max(0, self.total - self.completed)
        eta = f"{elapsed * remaining / self.completed:.1f}s" if self.completed else "unknown"
        print(
            f"{self.description}: {status}; {self.completed}/{self.total} complete, "
            f"{remaining} remaining; elapsed {elapsed:.1f}s; ETA {eta}",
            file=sys.stderr,
            flush=True,
        )

    def track(self, items: Iterable[T], *, total: int | None = None) -> Iterator[T]:
        """
        Count finished work and include additions to a growing expansion queue.

        Args:
            items (Iterable[T]): Ordered work, possibly extended during execution.
            total (int | None): Required count for iterables without a length.

        Yields:
            T: Next item without changing ordering or random seeds.
        """
        if total is None and not isinstance(items, Sized):
            raise ValueError("progress requires a known total")
        self.total = len(items) if isinstance(items, Sized) else int(total or 0)
        self.progress.update(self.task, total=self.total, refresh=self.interactive)
        if not self.interactive:
            self.log("started")
        for item in items:
            yield item
            self.completed += 1
            if isinstance(items, Sized):
                self.total = len(items)
            now = time.monotonic()
            refresh = now - self.updated >= (0.2 if self.interactive else 10)
            self.progress.update(self.task, completed=self.completed, total=self.total, refresh=refresh and self.interactive)
            if refresh:
                if not self.interactive:
                    self.log("running")
                self.updated = now

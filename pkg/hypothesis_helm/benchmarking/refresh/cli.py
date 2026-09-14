"""
Run every refresh operation from a checkout with bounded workers and explicit ownership.
"""

import argparse
import json
import os
import shutil
import sys
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from types import TracebackType
from typing import Self

from workgraph import OperationQueue

from hypothesis_helm.benchmarking.refresh.plan import Refresh
from hypothesis_helm.execution.processes import Processes
from hypothesis_helm.execution.signals import DeferredSignals, Termination


class RefreshLock:
    """
    Own the checkout lock directory and verify its identity before releasing it.
    """

    def __init__(self, directory: Path) -> None:
        """
        Prepare a unique lock ownership record.

        Args:
            directory (Path): Checkout-wide exclusive refresh lock directory.
        """
        self.directory = directory
        self.identity = {"pid": os.getpid(), "token": uuid.uuid4().hex}

    def __enter__(self) -> Self:
        """
        Acquire the directory atomically and verify the recorded owner.

        Returns:
            Self: Exclusive refresh scope; an existing directory is never taken over.
        """
        acquired = False
        try:
            with DeferredSignals():
                self.directory.mkdir()
                acquired = True
                (self.directory / "owner.json").write_text(json.dumps(self.identity))
                if json.loads((self.directory / "owner.json").read_text()) != self.identity:
                    raise RuntimeError("Refresh lock ownership changed during acquisition")
        except BaseException:
            with DeferredSignals():
                record = self.directory / "owner.json"
                if acquired and record.is_file() and json.loads(record.read_text()) == self.identity:
                    record.unlink()
                    self.directory.rmdir()
            raise
        return self

    def __exit__(self, kind: type[BaseException] | None, error: BaseException | None, traceback: TracebackType | None) -> None:
        """
        Release only the lock still owned by this run, after the queue has joined its children.

        Args:
            kind (type[BaseException] | None): Original exception type.
            error (BaseException | None): Original error.
            traceback (TracebackType | None): Original traceback.

        Returns:
            None: A replaced ownership record is left intact and reported as an error.
        """
        with DeferredSignals():
            if json.loads((self.directory / "owner.json").read_text()) != self.identity:
                raise RuntimeError("Refresh lock ownership changed; lock left intact")
            (self.directory / "owner.json").unlink()
            self.directory.rmdir()


def main(argv: list[str] | None = None) -> int:
    """
    Inspect or execute the full refresh without hiding any operation behind an implicit wait.

    Args:
        argv (list[str] | None): CLI arguments, or the process command line.

    Returns:
        int: Zero for completion, 130 for interruption, or two for an unsuccessful refresh.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", default="auto", help="concurrent independent refresh operations; auto uses available CPUs")
    parser.add_argument("--dry-run", action="store_true", help="print every operation and prerequisite without launching commands")
    args = parser.parse_args(argv)
    try:
        workers = (os.process_cpu_count() or 1) if args.workers == "auto" else int(args.workers)
        if workers < 1:
            raise ValueError("workers must be a positive integer or auto")
        project = Path.cwd()
        if not (project / "benchmarks/refresh/operations.sh").is_file():
            raise ValueError("Run hypothesis-helm-refresh from the project checkout root")
        root = Path(f".cache/refresh/refresh-{int(time.time())}")
        operations = Refresh(root).operations()
        if args.dry_run:
            print(json.dumps({"workers": workers, "operations": [asdict(item) for item in operations]}, indent=2))
            return 0
        for binary in ("python", "helm", "parallel", "git", "hypothesis-helm", "hypothesis-helm-benchmark"):
            if shutil.which(binary) is None:
                raise ValueError(f"Required executable not found: {binary}")
        legacy = Path("benchmarks/runs")
        if (legacy / "full-refresh.lock").exists():
            raise ValueError("An earlier refresh owns benchmarks/runs/full-refresh.lock; let it finish before starting another")
        marker = legacy / "latest-refresh.txt"
        if marker.is_file():
            previous = Path(marker.read_text().strip())
            if previous.is_dir() and not (previous / "publication-finished-epoch.txt").is_file():
                raise ValueError(f"Unfinished earlier refresh at {previous}; inspect it before removing {marker}")
        root.parent.mkdir(parents=True, exist_ok=True)
        with RefreshLock(root.parent / "full-refresh.lock"):
            latest = root.parent / "latest-refresh.txt"
            if latest.is_file():
                previous = Path(latest.read_text().strip())
                if previous.is_dir() and not (previous / "publication-finished-epoch.txt").is_file():
                    raise ValueError(
                        f"Unfinished refresh at {previous}; inspect its operations.json before removing {latest} to start fresh"
                    )
            root.mkdir(exist_ok=False)
            latest.write_text(str(root) + "\n")
            environment = dict(os.environ, MPLBACKEND="Agg")
            environment["PYTHONPATH"] = str(project / "pkg")
            queue = OperationQueue(
                operations,
                workers=workers,
                directory=root,
                cwd=project,
                environment=environment,
                owner_factory=lambda: Processes(interrupt_grace=15.0),
                cancellation_scope=Termination,
                critical_scope=DeferredSignals,
                notify=lambda message: print(message, file=sys.stderr, flush=True),
            )
            print(f"Refresh: {root}; state: {root}/operations.json; logs: {root}/logs/", file=sys.stderr)
            queue.run()
            print(f"Full refresh complete: {root}")
        return 0
    except KeyboardInterrupt:
        print("Refresh interrupted; owned workers joined and incomplete operations recorded.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Refresh failed: {exc}", file=sys.stderr)
        return 2

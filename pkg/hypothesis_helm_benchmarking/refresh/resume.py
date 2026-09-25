"""
Continue an interrupted refresh from its journal while preserving earlier logs and results.
"""

import hashlib
import json
import os
import sys
import time
from pathlib import Path

from hypothesis_helm.environment import env
from hypothesis_helm.execution.runtime.processes import Processes
from hypothesis_helm.execution.runtime.signals import DeferredSignals, Termination
from hypothesis_helm.schemas.contracts import mapping, sequence
from pipeline import Operation, OperationQueue

from hypothesis_helm_benchmarking.refresh.plan import PREPARATION, STUDIES, source_path

__all__ = ("latest_journal", "remaining", "resume")


def latest_journal(parent: Path = Path(".cache/refresh")) -> Path:
    """
    Find the newest continuation of the checkout's last refresh.

    Args:
        parent (Path): Directory containing latest-refresh.txt and refresh workspaces.

    Returns:
        Path: Original or continuation journal with the most recent state.

    Raises:
        ValueError: No previous refresh or resumable journal exists.
    """
    pointer = parent / "latest-refresh.txt"
    if not pointer.is_file():
        raise ValueError("No previous refresh; start hypothesis-helm-refresh without --resume")
    root = Path(pointer.read_text().strip())
    candidates = [root / "operations.json", *root.glob("resumed-*/operations.json"), *root.glob("logs/resumed-*/operations.json")]
    journals = [path for path in candidates if path.is_file()]
    if not journals:
        raise ValueError(f"No refresh journal found under {root}")
    return max(journals, key=lambda path: path.stat().st_mtime_ns)


def _retain_attempts(root: Path, directory: Path, operations: tuple[Operation, ...]) -> None:
    """
    Preserve partial measurements before restarting commands that require fresh output.

    Args:
        root (Path): Original refresh workspace.
        directory (Path): New continuation journal directory.
        operations (tuple[Operation, ...]): Unfinished work only; completed studies remain untouched.

    Returns:
        None: Earlier evidence is moved to prior-attempts beside the continuation journal.
    """
    for operation in operations:
        paths = [root / "outputs" / operation.name] if operation.name in (*STUDIES, "flamegraphs") else []
        if operation.name == "profile":
            paths = [root / "profiles", root / "profile-run"]
        for path in paths:
            if path.exists():
                target = directory / "prior-attempts" / path.relative_to(root)
                target.parent.mkdir(parents=True, exist_ok=True)
                path.rename(target)
                print(f"Retained unfinished {operation.name} output: {target}", file=sys.stderr, flush=True)


def remaining(journal: Path) -> tuple[Operation, ...]:
    """
    Reconstruct unfinished operations and remove only verified completed prerequisites.

    Args:
        journal (Path): Original or continuation operations.json file.

    Returns:
        tuple[Operation, ...]: Remaining queue, including failed operations for retry.
    """
    records = [mapping(item) for item in sequence(mapping(json.loads(journal.read_text()))["operations"])]
    # A journal entry counts as satisfied only after completion, not merely after a process was started.
    completed = {
        str(item["name"])
        for item in records
        if item.get("status") == "completed" and (item.get("exit_code") == 0 or item.get("allow_failure") is True)
    }
    return tuple(
        Operation(
            name=str(item["name"]),
            command=tuple(str(part) for part in sequence(item["command"])),
            requires=tuple(str(name) for name in sequence(item["requires"]) if str(name) not in completed),
            exclusive=bool(item.get("exclusive", False)),
            allow_failure=bool(item.get("allow_failure", False)),
            timeout=float(str(item["timeout"])) if item.get("timeout") is not None else None,
        )
        for item in records
        if str(item["name"]) not in completed
    )


def _workspace(journal: Path) -> tuple[Path, bool]:
    """
    Locate measured sources, or prove that the refresh failed before initialization began.

    Args:
        journal (Path): Original or continuation journal.

    Returns:
        tuple[Path, bool]: Workspace and whether it already contains a measured source snapshot.
    """
    for root in journal.parents:
        if (root / "measured-source-hashes.json").is_file():
            return root, True
    # Preparation uses the checkout so engineers can fix failing checks. Once
    # initialization starts, recovery must keep the original measured sources.
    for root in reversed(journal.parents):
        original = root / "operations.json"
        if not original.is_file():
            continue
        records = [mapping(item) for item in sequence(mapping(json.loads(original.read_text()))["operations"])]
        if not any(item["name"] == "initialize" for item in records):
            continue
        current = [mapping(item) for item in sequence(mapping(json.loads(journal.read_text()))["operations"])]
        for items in (records, current):
            if not any(item["name"] == "initialize" for item in items):
                raise ValueError("Resume requires a measured source snapshot after initialization")
            for item in items:
                if item["name"] == "initialize" or item["name"] not in PREPARATION:
                    if item.get("status") not in {"pending", "blocked"} or item.get("started_epoch") is not None:
                        raise ValueError("Resume requires a measured source snapshot after initialization has started")
        if (root / "frozen-source").exists():
            raise ValueError("Incomplete frozen source snapshot; cannot resume preparation")
        return root, False
    raise ValueError("Resume requires a refresh journal with initialization or a measured source snapshot")


def resume(journal: Path, workers: int, *, dry_run: bool = False) -> None:
    """
    Verify measured sources and resume under the normal refresh ownership contract.

    Args:
        journal (Path): Previous operation journal; no earlier attempt is overwritten.
        workers (int): Maximum concurrent independent operations.
        dry_run (bool): Print the unfinished inventory without creating a new queue.

    Returns:
        None: Completion, or an exception retaining the new journal for another continuation.
    """
    from hypothesis_helm_benchmarking.refresh.cli import RefreshLock

    journal = journal.resolve()
    if journal.is_dir():
        journal /= "operations.json"
    operations = remaining(journal)
    root, prepared = _workspace(journal)
    # Resume the measured implementation; mixing newer code into old measurements would invalidate the comparison.
    sources = mapping(json.loads((root / "measured-source-hashes.json").read_text())) if prepared else {}
    for name, expected in sources.items():
        if hashlib.sha256((root / "frozen-source" / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Frozen measured source changed: {name}")
    if dry_run:
        print("Remaining operations: " + ", ".join(item.name for item in operations))
        return
    if not operations:
        print("This journal has no unfinished operations")
        return
    with RefreshLock(root.parent / "full-refresh.lock"):
        # Before initialization, keep continuation journals in the allowed logs
        # directory so initialization can still reject unexpected artifacts.
        directory = (root if prepared else root / "logs") / f"resumed-{time.time_ns()}"
        environment = dict(env, MPLBACKEND="Agg")
        environment["PYTHONPATH"] = str(root / "frozen-source/pkg") if prepared else source_path(Path.cwd())
        environment["PATH"] = str(Path(sys.executable).parent) + os.pathsep + environment.get("PATH", "")
        queue = OperationQueue(
            operations,
            workers=workers,
            directory=directory,
            cwd=Path.cwd(),
            environment=environment,
            owner_factory=lambda: Processes(interrupt_grace=15.0),
            cancellation_scope=Termination,
            critical_scope=DeferredSignals,
            notify=lambda message: print(message, file=sys.stderr, flush=True),
        )
        # The source snapshot stays immutable. A failed measurement gets an empty
        # destination, while its previous data and every successful study survive.
        _retain_attempts(root, directory, operations)
        print(f"Resume: {directory}; previous journal: {journal}", file=sys.stderr, flush=True)
        queue.run()

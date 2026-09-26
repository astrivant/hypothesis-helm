"""
Run isolated GitHub refresh phases from the same operation inventory used locally.
"""

import json
import shutil
import sys
from dataclasses import replace
from pathlib import Path

from hypothesis_helm.environment import env
from hypothesis_helm.execution.runtime.processes import Processes
from hypothesis_helm.execution.runtime.signals import DeferredSignals, Termination
from pipeline import Operation, OperationQueue

from hypothesis_helm_benchmarking.refresh.plan import STUDIES, Refresh, source_path

__all__ = ("merge_statuses", "phase_operations", "run_phase")


def phase_operations(root: Path, phase: str, study: str | None = None) -> tuple[Operation, ...]:
    """
    Select phase operations while preserving dependencies within each runner.

    Args:
        root (Path): Shared relative workspace restored at the same path on each runner.
        phase (str): Preparation, one study, graph publication, or full verification including repository scans.
        study (str | None): Required study identifier for a matrix job.

    Returns:
        tuple[Operation, ...]: Operations with only external, workflow-enforced prerequisites removed.

    Raises:
        ValueError: The phase or study is unknown.
    """
    operations = Refresh(root).operations()
    if phase == "prepare":
        selected = operations[: next(i for i, item in enumerate(operations) if item.name in STUDIES)]
    elif phase == "study" and study in STUDIES:
        selected = tuple(item for item in operations if item.name == study)
    elif phase in {"graphs", "finish"}:
        selected = operations[next(i for i, item in enumerate(operations) if item.name == "measurements-finished") :]
        if phase == "graphs":
            # PR benchmarks publish studies without also spending hours scanning external repositories.
            selected = selected[: next(i for i, item in enumerate(selected) if item.name == "diagrams-finished") + 1]
            selected += (
                Operation(
                    "verify-benchmark-publication",
                    (sys.executable, str(root / "verify-publication.py"), str(root), "--benchmarks-only"),
                    ("diagrams-finished",),
                ),
            )
    else:
        raise ValueError("Choose prepare, study with a declared --study, graphs, or finish")
    names = {item.name for item in selected}
    return tuple(replace(item, requires=tuple(name for name in item.requires if name in names)) for item in selected)


def merge_statuses(root: Path) -> None:
    """
    Require one successful status from every matrix job before permitting publication.

    Args:
        root (Path): Prepared workspace with downloaded per-study status files.

    Returns:
        None: A complete status ledger replaces the runner-local copy.

    Raises:
        ValueError: Any study status is missing, duplicated, mislabeled or unsuccessful.
    """
    directory = root / "statuses"
    if {path.stem for path in directory.glob("*.tsv")} != set(STUDIES):
        raise ValueError("Refresh matrix is incomplete or contains unexpected study statuses")
    records = []
    for study in STUDIES:
        record = (directory / f"{study}.tsv").read_text()
        if record != f"{study}\t0\n":
            raise ValueError(f"Refresh study did not complete successfully: {study}")
        records.append(record)
    (root / "status.tsv").write_text("".join(records))


def run_phase(root: Path, phase: str, study: str | None, workers: int) -> None:
    """
    Execute one CI phase with owned processes and separate journals for matrix jobs.

    Args:
        root (Path): Relative workspace path shared through workflow artifacts.
        phase (str): Preparation, study, graph publication or full finish.
        study (str | None): Matrix study name.
        workers (int): Concurrent independent operations within this runner.

    Returns:
        None: Outputs remain under the prepared workspace for artifact transport.

    Raises:
        ValueError: The workspace is unsafe, unprepared or contains stale study statuses.
    """
    if root.is_absolute() or ".." in root.parts or root.parent != Path(".cache/refresh"):
        raise ValueError("CI workspace must be .cache/refresh/refresh-<epoch>")
    operations = phase_operations(root, phase, study)
    if phase != "prepare" and not (root / "provenance.json").is_file():
        raise ValueError("Restore the prepared refresh artifact before running this phase")
    if phase == "study" and (root / "status.tsv").exists():
        raise ValueError("A matrix study requires a fresh copy of the prepared workspace")
    if phase in {"graphs", "finish"}:
        merge_statuses(root)
    directory = root if phase == "prepare" else root / "ci-jobs" / (study or phase)
    queue = OperationQueue(
        operations,
        workers=workers,
        directory=directory,
        cwd=Path.cwd(),
        environment=dict(env, MPLBACKEND="Agg", PYTHONPATH=source_path(Path.cwd())),
        owner_factory=lambda: Processes(interrupt_grace=15.0),
        cancellation_scope=Termination,
        critical_scope=DeferredSignals,
        notify=lambda message: print(message, file=sys.stderr, flush=True),
    )
    try:
        queue.run()
    finally:
        if phase == "study":
            status = root / "status.tsv"
            if status.is_file():
                (root / "statuses").mkdir(exist_ok=True)
                shutil.copy2(status, root / "statuses" / f"{study}.tsv")
            log = directory / "logs" / f"{study}.log"
            if log.is_file():
                shutil.copy2(log, root / "logs" / log.name)
    if phase == "prepare":
        provenance_path = root / "provenance.json"
        provenance = json.loads(provenance_path.read_text())
        provenance["execution"] = "Isolated CI study runners and verified diagrams; the full finish phase also runs repository tests"
        provenance["ci_run_id"] = env.get("GITHUB_RUN_ID")
        provenance["ci_run_attempt"] = env.get("GITHUB_RUN_ATTEMPT")
        provenance_path.write_text(json.dumps(provenance, indent=2) + "\n")
        path = env.get("GITHUB_OUTPUT")
        if path:
            matrix = {"study": [name for name in STUDIES if name not in {"error-surface", "stress"}]}
            with Path(path).open("a") as output:
                output.write(f"root={root}\nmatrix={json.dumps(matrix)}\n")

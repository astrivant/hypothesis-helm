"""
Render test progress on stderr without capturing the manifest stream.
"""

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from hypothesis_helm.execution.environment import in_ci


def start_progress(total: int, workers: int, *, force: bool = False) -> tuple[Progress, TaskID]:
    """
    Start progress outside CI, with a final-only summary for redirected output.

    Args:
        total (int): Number of selected properties.
        workers (int): Initial worker target.
        force (bool): Render live updates on redirected stderr outside CI.

    Returns:
        tuple[Progress, TaskID]: Live display and its test task identifier.
    """
    ci = in_ci(honor_override=False)
    progress = Progress(
        TextColumn("{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("workers={task.fields[workers]}"),
        TimeElapsedColumn(),
        TextColumn("ETA"),
        TimeRemainingColumn(),
        console=Console(stderr=True, force_terminal=True if force and not ci else None),
        disable=ci,
        auto_refresh=False,
        redirect_stdout=False,
        redirect_stderr=False,
    )
    task = progress.add_task("Tests", total=total, workers=workers)
    progress.start()
    return progress, task

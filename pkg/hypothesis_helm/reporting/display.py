"""
Render test progress on stderr without capturing the manifest stream.
"""

import os

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


def in_ci() -> bool:
    """
    Detect CI environments even when a runner allocates a terminal.

    Returns:
        bool: Whether a common CI marker has an enabled value.
    """
    return any(
        os.environ.get(name, "").lower() not in {"", "0", "false", "no"}
        for name in ("CI", "GITHUB_ACTIONS", "GITLAB_CI", "CIRCLECI", "TF_BUILD", "JENKINS_URL", "BUILD_BUILDID", "BUILDKITE")
    )


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
    progress = Progress(
        TextColumn("{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("workers={task.fields[workers]}"),
        TimeElapsedColumn(),
        TextColumn("ETA"),
        TimeRemainingColumn(),
        console=Console(stderr=True, force_terminal=True if force and not in_ci() else None),
        disable=in_ci(),
        auto_refresh=False,
        redirect_stdout=False,
        redirect_stderr=False,
    )
    task = progress.add_task("Tests", total=total, workers=workers)
    progress.start()
    return progress, task

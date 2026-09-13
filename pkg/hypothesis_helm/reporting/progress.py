"""
Display readable value paths during generation and pytest execution.
"""

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import cast

import pytest
from rich.progress import Progress, TaskID

from hypothesis_helm.execution.render_hashes import (
    STATISTICS_DIRECTORY,
    reset_process_hashes,
    save_process_statistics,
)
from hypothesis_helm.execution.sampling import ENVIRONMENT as SAMPLING_ENVIRONMENT
from hypothesis_helm.execution.sampling import REPORT as SAMPLING_REPORT
from hypothesis_helm.execution.sampling import Sampling
from hypothesis_helm.execution.traversal import order_paths
from hypothesis_helm.integrations.sharding import parse_shard
from hypothesis_helm.reporting.display import start_progress

LOGGER = logging.getLogger(__name__)
DISPLAY: tuple[Progress, TaskID] | None = None


def format_path(path: tuple[str | int, ...]) -> str:
    """
    Format a value path without losing literal dots, indices, or wildcard segments.

    Args:
        path (tuple[str | int, ...]): Schema path being processed.

    Returns:
        str: Dollar-rooted path with unusual keys escaped in bracket notation.
    """
    result = "$"
    for segment in path:
        if segment == "*":
            result += "[*]"
        elif isinstance(segment, int):
            result += f"[{segment}]"
        elif segment.isidentifier():
            result += f".{segment}"
        else:
            result += f"[{json.dumps(segment, ensure_ascii=True)}]"
    return result


def pytest_configure(config: pytest.Config) -> None:
    """
    Register the generated test marker used to identify each values path.

    Args:
        config (pytest.Config): Configuration for the bundled pytest invocation.

    Returns:
        None: Pytest recognizes generated path metadata without marker warnings.
    """
    reset_process_hashes()
    config.addinivalue_line("markers", "hypothesis_helm_path(path): schema path exercised by a test")


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> None:
    """
    Log the selected path once before its property examples and fixture setup.

    Args:
        item (pytest.Item): Selected property about to execute.

    Returns:
        None: The path is emitted through pytest's live logging output.
    """
    marker = item.get_closest_marker("hypothesis_helm_path")
    if marker is not None:
        path = cast(tuple[str | int, ...], marker.args[0])
        LOGGER.info("Testing path %s", format_path(path))
    else:
        # Older or hand-edited suites may not carry generated path metadata.
        LOGGER.info("Testing %s", item.name)


def pytest_collection_finish(session: pytest.Session) -> None:
    """
    Export selected node IDs for the thread-pool scheduler.

    Args:
        session (pytest.Session): Session after keyword selection and collection.

    Returns:
        None: Selected node IDs are saved when the scheduler requests collection.
    """
    global DISPLAY
    if os.environ.get("HYPOTHESIS_HELM_PROGRESS") == "1" and not session.config.option.collectonly:
        DISPLAY = start_progress(
            len(session.items),
            1,
            force=os.environ.get("HYPOTHESIS_HELM_FORCE_PROGRESS") == "1",
        )
    destination = os.environ.get("HYPOTHESIS_HELM_COLLECT")
    if destination is not None:
        Path(destination).write_text(json.dumps([item.nodeid for item in session.items]))
    depths = os.environ.get("HYPOTHESIS_HELM_COLLECT_DEPTHS")
    if depths is not None:
        Path(depths).write_text(
            json.dumps(
                {
                    item.nodeid: len(marker.args[0]) if (marker := item.get_closest_marker("hypothesis_helm_path")) is not None else 0
                    for item in session.items
                }
            )
        )


def pytest_runtest_logfinish(nodeid: str, location: tuple[str, int | None, str]) -> None:
    """
    Advance serial progress after a selected property's teardown.

    Args:
        nodeid (str): Identifier of the completed test.
        location (tuple[str, int | None, str]): File, line, and test description.

    Returns:
        None: Serial progress advances once per property.
    """
    if DISPLAY is not None:
        progress, task = DISPLAY
        progress.update(task, advance=1, refresh=True)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """
    Close serial progress and preserve its partial count on interruption.

    Args:
        session (pytest.Session): Finishing pytest session.
        exitstatus (int): Pytest session status.

    Returns:
        None: The terminal cursor is restored and the final count remains visible.
    """
    global DISPLAY
    destination = os.environ.get(STATISTICS_DIRECTORY)
    if destination is not None and not session.config.option.collectonly:
        save_process_statistics(Path(destination))
    if DISPLAY is not None:
        progress, task = DISPLAY
        if exitstatus == 2:
            progress.update(task, description="Interrupted", workers=0)
        progress.stop()
        DISPLAY = None


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """
    Order and partition selected properties before execution or inventory export.

    Args:
        config (pytest.Config): Active pytest configuration.
        items (list[pytest.Item]): Collected properties after ordinary keyword filtering.

    Returns:
        None: Each shard retains its assigned properties in the common traversal order.
    """

    def path(item: pytest.Item) -> tuple[str | int, ...]:
        """
        Read generated path metadata, retaining unmarked properties at depth zero.

        Args:
            item (pytest.Item): Collected property, possibly from a hand-edited suite.

        Returns:
            tuple[str | int, ...]: Actual typed value path without splitting dotted keys.
        """
        marker = item.get_closest_marker("hypothesis_helm_path")
        return cast(tuple[str | int, ...], marker.args[0]) if marker is not None else ()

    if SAMPLING_ENVIRONMENT in os.environ:
        policy = Sampling(**json.loads(os.environ[SAMPLING_ENVIRONMENT]))
        retained, evidence = policy.select(items, lambda item: item.nodeid, int(os.environ.get("HYPOTHESIS_HELM_TRAVERSAL_SEED", "0")))
        retained_ids = {item.nodeid for item in retained}
        omitted = [item for item in items if item.nodeid not in retained_ids]
        items[:] = retained
        config.hook.pytest_deselected(items=omitted)
        if destination := os.environ.get(SAMPLING_REPORT):
            Path(destination).write_text(
                json.dumps({**evidence, "unit": "path property", "scope": "global before sharding"}, indent=2) + "\n"
            )
    items[:] = order_paths(
        items,
        path,
        strategy=os.environ.get("HYPOTHESIS_HELM_TRAVERSAL_STRATEGY", "linear"),
        seed=int(os.environ.get("HYPOTHESIS_HELM_TRAVERSAL_SEED", "0")),
        identity=lambda item: item.nodeid,
    )
    selector = os.environ.get("HYPOTHESIS_HELM_SHARD")
    if selector is None:
        return
    shard = parse_shard(selector)
    before = len(items)
    matched_digest = hashlib.sha256(json.dumps(sorted(item.nodeid for item in items)).encode()).hexdigest()
    selected = [item for item in items if shard.includes(item.nodeid)]
    deselected = [item for item in items if not shard.includes(item.nodeid)]
    items[:] = selected
    config.hook.pytest_deselected(items=deselected)
    destination = os.environ.get("HYPOTHESIS_HELM_SHARD_REPORT")
    if destination is not None:
        Path(destination).write_text(
            json.dumps(
                {
                    "index": shard.index,
                    "total": shard.total,
                    "algorithm": "sha256-nodeid-v1",
                    "matched": before,
                    "matched_digest": matched_digest,
                    "selected": len(selected),
                    "tests": [item.nodeid for item in selected],
                },
                indent=2,
            )
            + "\n"
        )

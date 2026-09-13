"""
Persist completed property outcomes and select local retries.
"""

import fcntl
import hashlib
import json
import logging
import os
import sys
from collections.abc import Iterator, Mapping
from importlib.metadata import version
from pathlib import Path
from uuid import uuid4

import pytest

LOGGER = logging.getLogger(__name__)
OUTCOMES: dict[str, str] = {}
CALLED: set[str] = set()


def in_ci(environment: Mapping[str, str]) -> bool:
    """
    Interpret explicit CI booleans before provider-specific indicators.

    Args:
        environment (Mapping[str, str]): Process environment.

    Returns:
        bool: Whether the invocation should use CI defaults.
    """
    if "CI" in environment:
        return environment["CI"].strip().lower() not in {"", "0", "false", "no", "off"}
    return any(
        environment.get(key, "").strip().lower() not in {"", "0", "false", "no", "off"}
        for key in ("GITHUB_ACTIONS", "GITLAB_CI", "CIRCLECI")
    )


def seed_key(seed: int) -> str:
    """
    Hash the canonical decimal seed into a stable cache namespace.

    Args:
        seed (int): Hypothesis seed, including zero or a negative integer.

    Returns:
        str: SHA-256 hex digest of the seed's UTF-8 decimal representation.
    """
    return hashlib.sha256(str(seed).encode("utf-8")).hexdigest()


def fingerprint(
    directory: Path,
    seed: int,
    match: str | None,
    shard: str,
    excluded: tuple[Path, ...] = (),
    *,
    suite_location: Path | None = None,
) -> str:
    """
    Hash suite, chart, implementation, and selection inputs for safe reuse.

    Args:
        directory (Path): Generated suite directory.
        seed (int): Hypothesis seed.
        match (str | None): Keyword selection.
        shard (str): Shard identifier.
        excluded (tuple[Path, ...]): Artifact and cache directories to exclude from the chart.
        suite_location (Path | None): Logical suite location when sources are staged temporarily.

    Returns:
        str: Content-addressed cache key, independent of absolute checkout paths.
    """
    digest = hashlib.sha256(repr((seed, match, shard, sys.version)).encode())
    conformity = os.environ.get("HYPOTHESIS_HELM_CONFORMITY")
    if conformity:
        settings = json.loads(conformity)
        if "cache_root" in settings:
            excluded = (*excluded, Path(settings["cache_root"]))
        digest.update(
            json.dumps(
                {k: v for k, v in settings.items() if k not in {"schemas", "cache_root", "executable"}},
                sort_keys=True,
            ).encode()
        )
    files = sorted(directory.glob("*.py")) + [
        directory / name for name in ("values.coalesced.yaml", "values.inferred.schema.json", "chart-source.json")
    ]
    for package in ("hypothesis", "hypothesis-jsonschema", "jsonschema", "ruamel.yaml", "pytest"):
        digest.update(f"{package}={version(package)}".encode())
    source = directory / "chart-source.json"
    if source.exists():
        chart = ((suite_location or directory) / json.loads(source.read_text())["chart"]).resolve()
        # Include dependency archives and files read with Helm's .Files as well as templates.
        for file in sorted(chart.rglob("*")):
            if file.is_file() and not any(root in file.parents for root in (directory, *excluded)):
                digest.update(file.relative_to(chart).as_posix().encode())
                digest.update(hashlib.sha256(file.read_bytes()).digest())
    package_root = Path(__file__).resolve().parents[1]
    files += sorted(file for file in package_root.rglob("*.py") if "tests" not in file.relative_to(package_root).parts)
    for file in files:
        if file.is_file():
            digest.update(file.name.encode())
            digest.update(hashlib.sha256(file.read_bytes()).digest())
    return digest.hexdigest()


def read_outcomes(path: Path) -> dict[str, str]:
    """
    Load validated outcomes, treating missing or malformed caches as cold.

    Args:
        path (Path): JSON result file.

    Returns:
        dict[str, str]: Previously completed node outcomes.
    """
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict) or any(
            not isinstance(key, str) or value not in ("passed", "failed", "skipped") for key, value in data.items()
        ):
            raise ValueError("invalid outcomes")
        return dict(data)
    except (OSError, ValueError):
        return {}


def merge_outcomes(path: Path, baseline: dict[str, str], updates: dict[str, str]) -> dict[str, str]:
    """
    Merge concurrent cache publications without dropping independent outcomes or failures.

    Args:
        path (Path): Shared cache entry.
        baseline (dict[str, str]): Snapshot read before this run.
        updates (dict[str, str]): Outcomes completed by this run's workers.

    Returns:
        dict[str, str]: Atomically published union; conflicting concurrent failures win.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        current = read_outcomes(path)
        for node, outcome in updates.items():
            if current.get(node) != baseline.get(node) and current.get(node) == "failed":
                continue
            current[node] = outcome
        temporary = path.with_suffix(f".{uuid4().hex}.tmp")
        temporary.write_text(json.dumps(current, indent=2) + "\n")
        temporary.replace(path)
        return current


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> Iterator[None]:
    """
    Exclude cached successes while retaining failures and unseen properties.

    Args:
        config (pytest.Config): Active pytest configuration.
        items (list[pytest.Item]): Collected tests.

    Yields:
        None: Keyword selection and shard inventory finish before cached successes are removed.
    """
    yield
    source = os.environ.get("HYPOTHESIS_HELM_CACHE_READ")
    if not source:
        return
    outcomes = read_outcomes(Path(source))
    excluded = [item for item in items if outcomes.get(item.nodeid) == "passed"]
    items[:] = [item for item in items if outcomes.get(item.nodeid) != "passed"]
    config.hook.pytest_deselected(items=excluded)
    if excluded:
        destination = os.environ.get("HYPOTHESIS_HELM_CACHE_RESULTS")
        if destination:
            (Path(destination) / "deselected").touch()
        LOGGER.info("Reusing %s successful paths from cache", len(excluded))


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """
    Record failures in any phase and successes only after completed teardown.

    Args:
        report (pytest.TestReport): Setup, call, or teardown outcome.

    Returns:
        None: Completed results are atomically saved in a worker-specific file.
    """
    destination = os.environ.get("HYPOTHESIS_HELM_CACHE_RESULTS")
    if not destination:
        return
    if report.when == "call" and report.passed:
        CALLED.add(report.nodeid)
    previous = OUTCOMES.get(report.nodeid)
    if report.failed:
        OUTCOMES[report.nodeid] = "failed"
    elif previous != "failed" and report.skipped:
        OUTCOMES[report.nodeid] = "skipped"
    elif report.when == "teardown" and previous is None and report.nodeid in CALLED:
        OUTCOMES[report.nodeid] = "passed"
    if report.nodeid in OUTCOMES:
        target = Path(destination) / f"{os.getpid()}.json"
        temporary = target.with_suffix(f".{uuid4().hex}.tmp")
        temporary.write_text(json.dumps(OUTCOMES))
        temporary.replace(target)

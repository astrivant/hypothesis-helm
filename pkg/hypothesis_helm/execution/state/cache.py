"""
Persist completed property outcomes and select local retries.
"""

import fcntl
import hashlib
import json
import logging
import os
import shutil
import sys
from collections.abc import Iterator
from importlib.metadata import version
from pathlib import Path
from uuid import uuid4

import pytest

from hypothesis_helm.environment import env, set_env
from hypothesis_helm.execution.state.manifests import ManifestStore
from hypothesis_helm.schemas.configuration.policy import inherited_policy

__all__ = (
    "fingerprint",
    "merge_outcomes",
    "pytest_collection_modifyitems",
    "pytest_runtest_logreport",
    "pytest_runtest_protocol",
    "read_outcomes",
    "seed_key",
)


LOGGER = logging.getLogger(__name__)
OUTCOMES: dict[str, str] = {}
CALLED: set[str] = set()


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
    digest.update(env.get("HYPOTHESIS_HELM_MAX_DEPTH", "unrestricted").encode())
    digest.update(env.get("HYPOTHESIS_HELM_IGNORED_RULES", "[]").encode())
    digest.update(json.dumps(inherited_policy(), sort_keys=True).encode())
    from hypothesis_helm.compiler.randomness.toolchain import identity as renderer_identity

    # Go assets can change native execution even when every Python file is unchanged.
    digest.update(renderer_identity().encode())
    # Auto mode can change from native fallback to controlled draws after a local build.
    digest.update(str((Path(".cache/random-renderer") / renderer_identity() / "renderer").is_file()).encode())
    from hypothesis_helm_catalog.builder import DATA

    for catalog in sorted(DATA.glob("*.json")):
        digest.update(catalog.read_bytes())
    conformity = env.get("HYPOTHESIS_HELM_CONFORMITY")
    if conformity:
        settings = json.loads(conformity)
        if "cache_root" in settings:
            excluded = (*excluded, Path(settings["cache_root"]))
        digest.update(
            json.dumps(
                {k: v for k, v in settings.items() if k not in {"schemas", "cache_root", "catalog"}},
                sort_keys=True,
            ).encode()
        )
    files = sorted(directory.glob("*.py")) + [
        directory / name for name in ("values.coalesced.yaml", "values.inferred.schema.json", "chart-source.json", "input-domains.json")
    ]
    for package in ("hypothesis", "hypothesis-jsonschema", "jsonschema", "ruamel.yaml", "PyYAML", "pytest", "lupa"):
        digest.update(f"{package}={version(package)}".encode())
    source = directory / "chart-source.json"
    if source.exists():
        metadata = json.loads(source.read_text())
        chart = ((suite_location or directory) / metadata["chart"]).resolve()
        binary = shutil.which(metadata.get("helm", "helm"))
        digest.update(hashlib.sha256(Path(binary).read_bytes()).digest() if binary else b"helm-unavailable")
        # Include dependency archives and files read with Helm's .Files as well as templates.
        for file in sorted(chart.rglob("*")):
            if file.is_file() and not any(root in file.parents for root in (directory, *excluded)):
                digest.update(file.relative_to(chart).as_posix().encode())
                digest.update(hashlib.sha256(file.read_bytes()).digest())
    # Invalidate outcomes for changes anywhere in the core package, beyond execution/state.
    package_root = Path(__file__).resolve().parents[2]
    files += sorted(file for file in package_root.rglob("*.py") if "tests" not in file.relative_to(package_root).parts)
    files += sorted((package_root / "compiler" / "lua").glob("*.lua"))
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
    source = env.get("HYPOTHESIS_HELM_CACHE_READ")
    if not source:
        return
    outcomes = read_outcomes(Path(source))
    store = env.get("HYPOTHESIS_HELM_MANIFEST_STORE")
    required = env.get("HYPOTHESIS_HELM_MANIFEST_REQUIRED") == "1"
    excluded = [
        item
        for item in items
        if outcomes.get(item.nodeid) == "passed"
        and (not required or store is not None and ManifestStore(Path(store)).verified(item.nodeid) is not None)
    ]
    skipped = {item.nodeid for item in excluded}
    items[:] = [item for item in items if item.nodeid not in skipped]
    config.hook.pytest_deselected(items=excluded)
    if excluded:
        destination = env.get("HYPOTHESIS_HELM_CACHE_RESULTS")
        if destination:
            (Path(destination) / "deselected").touch()
            (Path(destination) / f"reused-{os.getpid()}.json").write_text(json.dumps(sorted(skipped)))
        LOGGER.info("Reusing %s successful paths from cache", len(excluded))


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item: pytest.Item, nextitem: pytest.Item | None) -> Iterator[None]:
    """
    Capture each property's manifests through teardown before publishing a reusable stream.

    Args:
        item (pytest.Item): Property about to execute.
        nextitem (pytest.Item | None): Next property, as supplied by pytest.

    Yields:
        None: Pytest executes the property's fixtures, examples and teardown.

    """
    root = env.get("HYPOTHESIS_HELM_MANIFEST_STORE")
    workspace = env.get("HYPOTHESIS_HELM_CACHE_RESULTS")
    if root is None or workspace is None:
        yield
        return
    capture = Path(workspace) / f"{uuid4().hex}.jsonl"
    capture.touch()
    previous = env.get("HYPOTHESIS_HELM_MANIFEST_CAPTURE")
    set_env("HYPOTHESIS_HELM_MANIFEST_CAPTURE", str(capture))
    try:
        yield
    finally:
        if previous is None:
            set_env("HYPOTHESIS_HELM_MANIFEST_CAPTURE", None)
        else:
            set_env("HYPOTHESIS_HELM_MANIFEST_CAPTURE", previous)
        try:
            if OUTCOMES.get(item.nodeid) == "passed":
                ManifestStore(Path(root)).publish(item.nodeid, capture)
        except OSError as exc:
            LOGGER.warning("Could not cache manifests for %s: %s", item.nodeid, exc)
        finally:
            capture.unlink(missing_ok=True)


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """
    Record failures in any phase and successes only after completed teardown.

    Args:
        report (pytest.TestReport): Setup, call, or teardown outcome.

    Returns:
        None: Completed results are atomically saved in a worker-specific file.
    """
    destination = env.get("HYPOTHESIS_HELM_CACHE_RESULTS")
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

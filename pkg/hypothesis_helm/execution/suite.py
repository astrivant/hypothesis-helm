"""
Run generated Python properties inside the Helm plugin's bundled environment.
"""

import fcntl
import hashlib
import json
import logging
import os
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal
from uuid import uuid4

from rich.console import Console

from hypothesis_helm.execution.cache import (
    fingerprint,
    merge_outcomes,
    read_outcomes,
    seed_key,
)
from hypothesis_helm.execution.environment import in_ci
from hypothesis_helm.execution.parallel import run_parallel, worker_limit
from hypothesis_helm.execution.processes import Processes
from hypothesis_helm.execution.render_hashes import (
    STATISTICS_DIRECTORY,
    summarize_process_statistics,
)
from hypothesis_helm.execution.sampling import DEFAULT_SAMPLING, Sampling
from hypothesis_helm.execution.sampling import ENVIRONMENT as SAMPLING_ENVIRONMENT
from hypothesis_helm.execution.sampling import REPORT as SAMPLING_REPORT
from hypothesis_helm.execution.structure import inspect_structure
from hypothesis_helm.execution.traversal import ALGORITHM, validate_strategy
from hypothesis_helm.integrations.sharding import Shard
from hypothesis_helm.reporting.output import MANIFEST_FD


def run_suite(
    directory: Path,
    *,
    seed: int = 0,
    traversal_strategy: str = "random",
    sampling: Sampling = DEFAULT_SAMPLING,
    match: str | None = None,
    collect_only: bool = False,
    jobs: int | Literal["auto"] = "auto",
    shard: Shard | None = None,
    artifact_dir: Path | None = None,
    cache_dir: Path | None = None,
    cache: bool = True,
    disable_schema_caching: bool = False,
    progress: bool = False,
    rerun: str = "auto",
    run_id: str | None = None,
) -> int:
    """
    Execute a saved generated suite with the plugin's Python and pytest.

    Pytest output streams to Helm's console. Its exit status is preserved, including
    failures, collection errors, and empty selections. Parent pytest configuration
    and unrelated auto-loaded plugins cannot change the generated test invocation.

    Args:
        directory (Path): Directory containing the generated test module.
        seed (int): Hypothesis seed applied to every property in this invocation.
        traversal_strategy (str): Seeded random, original linear, root-first, or leaf-first path order.
        sampling (Sampling): Optional retained percentage and minimum sample after filtering.
        match (str | None): Optional pytest keyword expression selecting value paths.
        collect_only (bool): Whether to list tests without invoking Helm rendering.
        jobs (int | Literal["auto"]): Fixed worker count or automatic PID throughput tuning.
        shard (Shard | None): Optional deterministic partition of the selected properties.
        artifact_dir (Path | None): Report root, defaulting to the suite directory.
        cache_dir (Path | None): Persistent cache root, defaulting to reports/cache.
        cache (bool): Whether to read and write cached path outcomes.
        disable_schema_caching (bool): Read the values structure baseline without replacing it.
        progress (bool): Force live progress even when stderr is redirected.
        rerun (str): Auto, all, or failed; auto retries failures outside CI.
        run_id (str | None): Common identifier for shards belonging to one final report.

    Returns:
        int: Pytest exit status, or 130 when the child is interrupted.
    """
    traversal_strategy = validate_strategy(traversal_strategy)
    if rerun not in {"auto", "all", "failed"}:
        raise ValueError("rerun must be auto, all, or failed")
    workers = worker_limit(jobs)
    directory = directory.resolve()
    module = directory / "test_chart_values.py"
    if not module.is_file():
        raise ValueError(f"no generated test suite found at {module}")
    results = (artifact_dir or directory).resolve()
    if shard is not None:
        results = results / "shards" / shard.name
    results.mkdir(parents=True, exist_ok=True)
    with (results / ".run.lock").open("a") as run_lock:
        fcntl.flock(run_lock, fcntl.LOCK_EX)
        started = time.time()
        tick = time.monotonic()
        (results / "report.json").unlink(missing_ok=True)
        suite_identity = (
            fingerprint(
                directory,
                seed,
                match,
                "all",
                ((cache_dir or results / "cache").resolve(), (artifact_dir or directory).resolve()),
            )
            if shard is not None
            else None
        )
        (results / "shard.json").unlink(missing_ok=True)
        (results / "concurrency.json").unlink(missing_ok=True)
        (results / "junit.xml").unlink(missing_ok=True)
        # A dedicated config file prevents accidental adoption of the caller's pytest
        # settings; the generated module and any suite-local conftest remain editable.
        config = results / "hypothesis-helm.pytest.ini"
        config.write_text("[pytest]\n")
        command = [
            str(Path(sys.executable).with_name("pytest")),
            "-c",
            str(config),
            "--rootdir",
            str(directory),
            "--confcutdir",
            str(directory),
            "-p",
            "hypothesis.extra.pytestplugin",
            "-p",
            "hypothesis_helm.reporting.progress",
            "--log-cli-level=INFO",
            "--log-cli-format=[%(levelname)s] %(message)s",
            f"--hypothesis-seed={seed}",
            "--junitxml",
            str(results / "junit.xml"),
            "-ra",
        ]
        if match is not None:
            command += ["-k", match]
        if collect_only:
            command.append("--collect-only")
        command.append(str(module))
        environment = dict(os.environ)
        environment["HYPOTHESIS_HELM_TRAVERSAL_STRATEGY"] = traversal_strategy
        environment["HYPOTHESIS_HELM_TRAVERSAL_SEED"] = str(seed)
        environment[SAMPLING_ENVIRONMENT] = json.dumps({"percent": sampling.percent, "minimum": sampling.minimum})
        environment[SAMPLING_REPORT] = str(results / "sampling.json")
        (results / "sampling.json").unlink(missing_ok=True)
        environment.pop("HYPOTHESIS_HELM_CACHE_READ", None)
        environment.pop("HYPOTHESIS_HELM_CACHE_RESULTS", None)
        cache_workspace = TemporaryDirectory(prefix="path-results-", dir=results)
        cache_results = Path(cache_workspace.name)
        hash_statistics = cache_results / "render-hashes"
        environment[STATISTICS_DIRECTORY] = str(hash_statistics)
        cache_file = None
        marker = None
        cached: dict[str, str] = {}
        retry = rerun == "failed" or (rerun == "auto" and not in_ci(environment))
        if cache and not collect_only:
            cache_root = (cache_dir or results / "cache").resolve()
            cache_root.mkdir(parents=True, exist_ok=True)
            marker = inspect_structure(directory, cache_root, seed)
            if marker is not None:
                logging.getLogger(__name__).info(
                    "Values structure %s: %s added paths, %s removed paths",
                    marker.status,
                    len(marker.added),
                    len(marker.removed),
                )
            cache_file = (
                cache_root
                / seed_key(seed)
                / (
                    fingerprint(
                        directory,
                        seed,
                        match,
                        str(shard),
                        (cache_root, (artifact_dir or directory).resolve()),
                    )
                    + ".json"
                )
            )
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cached = read_outcomes(cache_file)
            environment["HYPOTHESIS_HELM_CACHE_RESULTS"] = str(cache_results)
            if retry and cached:
                snapshot = cache_results / "prior.json"
                snapshot.write_text(json.dumps(cached))
                environment["HYPOTHESIS_HELM_CACHE_READ"] = str(snapshot)
                logging.getLogger(__name__).info("Retrying failed or incomplete paths from %s", cache_file)
            command[-1:-1] = ["-p", "hypothesis_helm.execution.cache"]
        environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        environment.pop("PYTEST_ADDOPTS", None)
        environment.pop("PYTEST_PLUGINS", None)
        environment.pop("HYPOTHESIS_HELM_COLLECT", None)
        environment.pop("HYPOTHESIS_HELM_COLLECT_DEPTHS", None)
        environment.pop("HYPOTHESIS_HELM_PROGRESS", None)
        environment.pop("HYPOTHESIS_HELM_FORCE_PROGRESS", None)
        if progress:
            environment["HYPOTHESIS_HELM_FORCE_PROGRESS"] = "1"
        environment.pop("HYPOTHESIS_HELM_MANIFEST_LOCK", None)
        environment.pop("HYPOTHESIS_HELM_SHARD", None)
        environment.pop("HYPOTHESIS_HELM_SHARD_REPORT", None)
        if shard is not None:
            environment["HYPOTHESIS_HELM_SHARD"] = f"{shard.index}/{shard.total}"
            environment["HYPOTHESIS_HELM_SHARD_REPORT"] = str(results / "shard.json")
            logging.getLogger(__name__).info("Running shard %s/%s", shard.index, shard.total)
        descriptor = MANIFEST_FD.get()
        environment.pop("HYPOTHESIS_HELM_MANIFEST_FD", None)
        if descriptor is not None:
            environment["HYPOTHESIS_HELM_MANIFEST_FD"] = str(descriptor)
        try:
            if workers > 1 and not collect_only:
                status, workers = run_parallel(
                    command,
                    directory,
                    environment,
                    descriptor,
                    workers,
                    adaptive=jobs == "auto",
                    force_progress=progress,
                    artifact_dir=results,
                )
            else:
                workers = 1
                environment["HYPOTHESIS_HELM_PROGRESS"] = "1"
                completed = Processes(interrupt_grace=5.0).run(
                    command,
                    cwd=directory,
                    env=environment,
                    check=False,
                    pass_fds=() if descriptor is None else (descriptor,),
                    stdout=None if descriptor is None else sys.stderr,
                )
                status = completed.returncode if completed.returncode >= 0 else 130
        except KeyboardInterrupt:
            logging.getLogger(__name__).info("Testing interrupted")
            status = 130
        if status == 5 and (cache_results / "deselected").exists():
            status, workers = 0, 0
            logging.getLogger(__name__).info("All selected paths previously passed; nothing to rerun")
        if cache_file is not None:
            updates: dict[str, str] = {}
            for result_file in cache_results.glob("[0-9]*.json"):
                updates.update(read_outcomes(result_file))
            merge_outcomes(cache_file, cached, updates)
        if marker is not None and not disable_schema_caching and status in (0, 1, 130):
            marker.save()
        render_statistics = summarize_process_statistics(hash_statistics)
        cache_workspace.cleanup()
        assignment = None
        if shard is not None and (results / "shard.json").is_file():
            assignment = json.loads((results / "shard.json").read_text())
            if status == 5 and assignment["matched"] > 0 and assignment["selected"] == 0:
                status = 0
                workers = 0
                logging.getLogger(__name__).info("Shard has no assigned tests")
        if status == 130:
            Console(stderr=True).show_cursor()
        if status == 130 and not (results / "junit.xml").exists():
            (results / "junit.xml").write_text(
                '<testsuites><testsuite name="hypothesis-helm" tests="0" failures="0" errors="0" skipped="0"/></testsuites>'
            )
        selected = set(assignment["tests"]) if assignment is not None else set()
        reused = sorted(node for node in selected if retry and cached.get(node) == "passed")
        report = {
            "run_id": run_id,
            "started_epoch": started,
            "elapsed_seconds": time.monotonic() - tick,
            "suite_fingerprint": suite_identity,
            "reused_properties": reused,
            "status": "interrupted"
            if status == 130
            else "collected"
            if status == 0 and collect_only
            else "passed"
            if status == 0
            else "failed",
            "exit_code": status,
            "suite": str(directory),
            "render_hashes": render_statistics,
            "ignored_rules": json.loads(environment.get("HYPOTHESIS_HELM_IGNORED_RULES", "[]")),
            "values_structure": marker.report() if marker is not None else None,
            "conformity": json.loads(environment["HYPOTHESIS_HELM_CONFORMITY"]) if "HYPOTHESIS_HELM_CONFORMITY" in environment else None,
            "shard": assignment,
            "cache": str(cache_file) if cache_file else None,
            "rerun": "failed" if retry else "all",
            "seed": seed,
            "sampling": json.loads((results / "sampling.json").read_text()) if (results / "sampling.json").exists() else None,
            "traversal_strategy": traversal_strategy,
            "traversal_algorithm": ALGORITHM,
            "workers": workers,
            "jobs": jobs,
            "match": match,
            "collect_only": collect_only,
            "junit": str(results / "junit.xml"),
            "junit_xml": (results / "junit.xml").read_text() if (results / "junit.xml").is_file() else None,
            "junit_sha256": hashlib.sha256((results / "junit.xml").read_bytes()).hexdigest() if (results / "junit.xml").is_file() else None,
            "concurrency": str(results / "concurrency.json") if (results / "concurrency.json").is_file() else None,
        }
        temporary = results / f"report.{uuid4().hex}.tmp"
        temporary.write_text(json.dumps(report, indent=2) + "\n")
        temporary.replace(results / "report.json")
        return status

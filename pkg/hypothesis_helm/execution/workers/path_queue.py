"""
Share one chart's ordered path queue across isolated Python workers and one deadline.
"""

import argparse
import fcntl
import hashlib
import json
import logging
import os
import shutil
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor, wait
from pathlib import Path

from hypothesis_helm.charts.model import Chart
from hypothesis_helm.compiler.asts.contracts import Contracts
from hypothesis_helm.compiler.passes.inputs import InputInventory
from hypothesis_helm.compiler.passes.rejections import RejectionPolicy
from hypothesis_helm.environment import env, refresh_env
from hypothesis_helm.exceptions.execution import ChartUnavailable, TimeLimitReached
from hypothesis_helm.execution.runtime.budget import execution_timer
from hypothesis_helm.execution.runtime.processes import Processes
from hypothesis_helm.execution.runtime.signals import DeferredSignals, Termination
from hypothesis_helm.reporting.console.logs import WorkerLogFormatter, WorkerLogs
from hypothesis_helm.reporting.console.output import MANIFEST_FD, manifest_format
from hypothesis_helm.reporting.console.progress import format_path
from hypothesis_helm.reporting.evidence.checkpoints import save
from hypothesis_helm.schemas.contracts import mapping, sequence
from hypothesis_helm.schemas.paths import ValuePath

__all__ = ("execute", "main")


def execute(context: dict[str, object], directory: Path, workers: int) -> list[dict[str, object]]:
    """
    Run persistent workers, stop descendants, and recover every claimed task in queue order.

    Args:
        context (dict[str, object]): Prepared chart, ordered paths, baseline and shared monotonic deadline.
        directory (Path): Fresh queue directory for this chart invocation.
        workers (int): Maximum worker count, capped by the number of available paths.

    Returns:
        list[dict[str, object]]: Claimed path records in dispatch order, followed by any queue-wide execution diagnostic.
    """
    installed = Path(sys.executable).with_name("hypothesis-helm-path-worker")
    binary = str(installed) if installed.is_file() else shutil.which("hypothesis-helm-path-worker")
    if binary is None:
        raise ValueError("hypothesis-helm-path-worker is missing; reinstall hypothesis-helm to install its worker entry point")
    directory.mkdir(parents=True, exist_ok=False)
    save(directory / "context.json", context)
    (directory / "cursor").write_text("0")
    owner = Processes(interrupt_grace=5.0)
    count = min(workers, len(sequence(context["paths"])))
    if count == 0:
        return []
    deadline = float(str(context["deadline"]))
    logs = WorkerLogs(directory, count)
    descriptor = MANIFEST_FD.get()
    environment = dict(env)
    if descriptor is not None:
        lock = directory / "manifests.lock"
        lock.touch()
        environment.update(
            HYPOTHESIS_HELM_MANIFEST_FD=str(descriptor),
            HYPOTHESIS_HELM_MANIFEST_FORMAT=manifest_format(),
            HYPOTHESIS_HELM_MANIFEST_LOCK=str(lock),
        )

    def run(slot: int) -> int:
        """
        Execute one owned interpreter with an isolated diagnostic log.

        Args:
            slot (int): Stable worker slot for this chart.

        Returns:
            int: Worker process exit status.
        """
        with (directory / f"worker-{slot}.log").open("w") as log:
            return owner.run(
                [binary, str(directory)],
                stdout=log,
                stderr=log,
                env=environment,
                pass_fds=() if descriptor is None else (descriptor,),
                check=False,
            ).returncode

    pool = ThreadPoolExecutor(max_workers=count, thread_name_prefix="chart-path")
    futures = []
    cancelled = False
    failed_early = False
    interrupted = False
    try:
        with Termination():
            futures = [pool.submit(run, slot) for slot in range(count)]
            pending = set(futures)
            while pending:
                done, pending = wait(pending, timeout=0.1)
                logs.drain()
                for future in done:
                    code = future.result()
                    if code in (130, 143, -signal.SIGINT, -signal.SIGTERM):
                        interrupted = True
                        (directory / "interrupted").touch()
                        (directory / "stop").touch()
                    if code and time.monotonic() < deadline and not (directory / "stop").exists():
                        raise RuntimeError(f"Path worker exited with status {code}; see {directory}")
                if time.monotonic() >= deadline or (directory / "stop").exists():
                    cancelled = True
                    failed_early = (directory / "stop").exists()
                    break
    except KeyboardInterrupt:
        interrupted = True
        (directory / "interrupted").touch()
        (directory / "stop").touch()
    except TimeLimitReached:
        cancelled = True
    finally:
        with DeferredSignals():
            try:
                if cancelled or interrupted:
                    # Publish cancellation before signalling children, so their
                    # shutdown handlers do not mistake cleanup for a user interrupt.
                    (directory / "stop").touch()
                # Each worker has the same deadline and owns Helm's separate process group.
                # Let its timer unwind and join Helm before introducing another signal.
                if cancelled and not failed_early:
                    wait(futures, timeout=5.0)
                owner.stop()
            finally:
                pool.shutdown(wait=True, cancel_futures=True)
                logs.drain()
    records = []
    interrupted = interrupted or (directory / "interrupted").exists()
    for marker in sorted(directory.glob("started-*.json")):
        started = mapping(json.loads(marker.read_text()))
        result = directory / marker.name.replace("started-", "result-")
        phase = (
            mapping(json.loads(result.read_text()))
            if result.exists()
            else {
                **started,
                "status": "interrupted" if interrupted else "cancelled" if failed_early else "time-limit" if cancelled else "error",
            }
        )
        checkpoint = Path(str(started["artifacts"])) / "observed-failure.json"
        if not result.exists() and checkpoint.is_file():
            evidence = mapping(json.loads(checkpoint.read_text()))
            reason = str(phase["status"])
            phase.update(evidence, **started, stop_reason=reason)
            if evidence.get("blocking") is False:
                # A nonfatal chart finding cannot turn worker loss or a timeout into success.
                phase["status"] = reason
            if interrupted:
                phase["status"] = "interrupted"
        records.append(phase)
    unavailable = directory / "execution-error.json"
    if unavailable.is_file() and not any(record.get("error_kind") == "execution" for record in records):
        # Another worker may stop during preparation, before owning any path.
        # Preserve its error separately, even if cleanup interrupted the worker that first lost the source.
        records.append({**mapping(json.loads(unavailable.read_text())), "phase": "execution", "kind": "execution"})
    return records


def main(argv: list[str] | None = None) -> int:
    """
    Claim unique paths from a shared queue and run bounded Hypothesis properties.

    Args:
        argv (list[str] | None): Internal queue directory argument.

    Returns:
        int: Zero after completion or coordinated shutdown, or 130 for an independent interrupt.
    """
    refresh_env()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    directory = args.directory
    try:
        with Termination():
            context = mapping(json.loads((directory / "context.json").read_text()))
            remaining = float(str(context["deadline"])) - time.monotonic()
            if remaining <= 0:
                return 0
            # Include worker preparation and strategy construction in the shared
            # chart deadline, even before a candidate reaches the renderer.
            with execution_timer(remaining):
                return _run_queue(directory, context)
    except TimeLimitReached:
        # The coordinator recovers any claimed path without a completed result.
        return 0
    except KeyboardInterrupt:
        if not (directory / "stop").exists():
            (directory / "interrupted").touch()
            (directory / "stop").touch()
            return 130
        return 0
    except ChartUnavailable as exc:
        save(
            directory / "execution-error.json",
            {"status": "error", "error_kind": "execution", "error": str(exc), "failure_type": type(exc).__name__, "attempts": 0},
        )
        (directory / "stop").touch()
        return 0


def _run_queue(directory: Path, context: dict[str, object]) -> int:
    """
    Process paths while retaining source ownership and reporting shared execution failures.

    Args:
        directory (Path): Queue with immutable input context and atomic ownership records.
        context (dict[str, object]): Prepared inputs and shared deadline, read once by the worker entry point.

    Returns:
        int: Zero once this worker stops claiming paths.
    """
    from hypothesis_helm.charts.testing.paths import GENERATION_ERRORS, path_strategy
    from hypothesis_helm.charts.testing.runner import check_chart

    chart = Chart(Path(str(context["chart"])), mapping(context["schema"]), mapping(context["defaults"]))
    chart.require_source()
    if "input_domains" in context:
        from hypothesis_helm.schemas.generation.domains import InputDomains

        domains = mapping(context["input_domains"])
        chart.domains = InputDomains(
            [mapping(rule) for rule in sequence(domains["constraints"])],
            [mapping(note) for note in sequence(domains["diagnostics"])],
            str(domains["identity"]),
            str(domains.get("character_sets", "ascii")),
            mapping(domains.get("generation", {})),
            str(domains.get("yaml_parser", "ruamel")),
        )
    inventory = InputInventory.build(chart)
    rejections = (
        RejectionPolicy(Contracts.build(chart.path, inventory.dependencies), chart.defaults, (chart.path / "values.schema.json").is_file())
        if context["filtering"]
        else None
    )
    paths = sequence(context["paths"])
    deadline = float(str(context["deadline"]))
    handler = logging.StreamHandler()
    handler.setFormatter(WorkerLogFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    with Termination():
        while time.monotonic() < deadline:
            with DeferredSignals(), (directory / "cursor").open("r+") as cursor:
                fcntl.flock(cursor, fcntl.LOCK_EX)
                index = int(cursor.read())
                if index >= len(paths) or (directory / "stop").exists() or time.monotonic() >= deadline:
                    break
                chart.require_source()
                item = mapping(paths[index])
                segments = sequence(item["path"])
                if not all(isinstance(segment, (str, int)) for segment in segments):
                    raise ValueError("path segments must be strings or integers")
                entry = ValuePath(tuple(segment for segment in segments if isinstance(segment, (str, int))), mapping(item["schema"]))
                key = hashlib.sha256(json.dumps(entry.path).encode()).hexdigest()[:20]
                artifacts = Path(str(context["artifacts"])) / "paths" / key
                phase: dict[str, object] = {
                    "phase": format_path(entry.path),
                    "kind": "value-path",
                    "path": list(entry.path),
                    "artifacts": str(artifacts),
                    "worker_pid": os.getpid(),
                    "queue_index": index,
                }
                # Record ownership before advancing the locked cursor, so interrupted claims remain visible in the report.
                save(directory / f"started-{index:08}.json", phase)
                cursor.seek(0)
                cursor.write(str(index + 1))
                cursor.truncate()
            # The cursor lock is released before rendering; other workers can now claim different paths.
            logging.info("Testing path %s (%d/%d)", phase["phase"], index + 1, len(paths))
            result = check_chart(
                chart,
                max_examples=int(str(context["max_examples"])),
                random_seed=int(str(context["seed"])),
                helm=str(context["helm"]),
                timeout=float(str(context["timeout"])),
                time_limit=max(0.000001, deadline - time.monotonic()),
                input_strategy=path_strategy(chart, entry, mapping(context["generation_schema"]), inventory.dependencies),
                input_inventory=inventory,
                artifact_dir=artifacts,
                fail_fast=bool(context["fail_fast"]),
                check_defaults=False,
                release=str(context["release"]),
                namespace=str(context["namespace"]),
                kube_version=str(context["kube_version"]) if context["kube_version"] is not None else None,
                allow_empty=bool(context["allow_empty"]),
                rejection_policy=rejections,
                protected_paths=(entry.path,),
                baseline_resources=[mapping(resource) for resource in sequence(context["resources"])],
            )
            result.pop("input_inventory", None)
            result.update(phase)
            if result.get("failure_type") in GENERATION_ERRORS:
                result["status"] = "generation-error"
            artifacts.mkdir(parents=True, exist_ok=True)
            save(artifacts / "report.json", result)
            save(directory / f"result-{index:08}.json", result)
            if result.get("error_kind") == "execution":
                save(directory / "execution-error.json", result)
                (directory / "stop").touch()
                break
            if result["status"] == "interrupted":
                (directory / "interrupted").touch()
                (directory / "stop").touch()
                break
            if result["status"] == "time-limit" or result.get("stop_reason") == "time-limit":
                break
            if result.get("fail_fast", context["fail_fast"]) and result["status"] == "failed":
                (directory / "stop").touch()
                break
    return 0

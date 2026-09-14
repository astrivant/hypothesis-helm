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
import sys
import time
from concurrent.futures import ThreadPoolExecutor, wait
from pathlib import Path

from hypothesis_helm.charts.model import Chart
from hypothesis_helm.compiler.asts.contracts import Contracts
from hypothesis_helm.compiler.passes.inputs import InputInventory
from hypothesis_helm.compiler.passes.rejections import RejectionPolicy
from hypothesis_helm.execution.processes import Processes
from hypothesis_helm.execution.signals import DeferredSignals, Termination
from hypothesis_helm.reporting.budget import TimeLimitReached
from hypothesis_helm.reporting.progress import format_path
from hypothesis_helm.schemas.contracts import mapping, sequence
from hypothesis_helm.schemas.paths import ValuePath


def save(path: Path, value: dict[str, object]) -> None:
    """
    Publish one worker record atomically without sharing a writable report.

    Args:
        path (Path): Destination owned by this task.
        value (dict[str, object]): JSON record.

    Returns:
        None: Readers see the previous complete record or the new complete record.
    """
    temporary = path.with_suffix(f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def execute(context: dict[str, object], directory: Path, workers: int) -> list[dict[str, object]]:
    """
    Run persistent workers, stop descendants, and recover every claimed task in queue order.

    Args:
        context (dict[str, object]): Prepared chart, ordered paths, baseline and shared monotonic deadline.
        directory (Path): Fresh queue directory for this chart invocation.
        workers (int): Maximum worker count, capped by the number of available paths.

    Returns:
        list[dict[str, object]]: Completed and interrupted path records in dispatch order.
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

    def run(slot: int) -> int:
        """
        Execute one owned interpreter with an isolated diagnostic log.

        Args:
            slot (int): Stable worker slot for this chart.

        Returns:
            int: Worker process exit status.
        """
        with (directory / f"worker-{slot}.log").open("w") as log:
            return owner.run([binary, str(directory)], stdout=log, stderr=log, check=False).returncode

    pool = ThreadPoolExecutor(max_workers=count, thread_name_prefix="chart-path")
    futures = []
    cancelled = False
    failed_early = False
    try:
        with Termination():
            futures = [pool.submit(run, slot) for slot in range(count)]
            pending = set(futures)
            while pending:
                done, pending = wait(pending, timeout=0.1)
                for future in done:
                    code = future.result()
                    if code and time.monotonic() < deadline and not (directory / "stop").exists():
                        raise RuntimeError(f"Path worker exited with status {code}; see {directory}")
                if time.monotonic() >= deadline or (directory / "stop").exists():
                    cancelled = True
                    failed_early = (directory / "stop").exists()
                    break
    except TimeLimitReached:
        cancelled = True
    finally:
        with DeferredSignals():
            try:
                # Each worker has the same deadline and owns Helm's separate process group.
                # Let its timer unwind and join Helm before introducing another signal.
                if cancelled and not failed_early:
                    wait(futures, timeout=5.0)
                owner.stop()
            finally:
                pool.shutdown(wait=True, cancel_futures=True)
    records = []
    for marker in sorted(directory.glob("started-*.json")):
        started = mapping(json.loads(marker.read_text()))
        result = directory / marker.name.replace("started-", "result-")
        phase = (
            mapping(json.loads(result.read_text()))
            if result.exists()
            else {**started, "status": "cancelled" if failed_early else "time-limit" if cancelled else "error"}
        )
        records.append(phase)
    return records


def main(argv: list[str] | None = None) -> int:
    """
    Claim unique paths from a shared queue and run bounded Hypothesis properties.

    Args:
        argv (list[str] | None): Internal queue directory argument.

    Returns:
        int: Zero after exhausting the queue or reaching its common deadline.
    """
    from hypothesis_helm.charts.paths import GENERATION_ERRORS, path_strategy
    from hypothesis_helm.charts.runner import check_chart

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    directory = args.directory
    context = mapping(json.loads((directory / "context.json").read_text()))
    chart = Chart(Path(str(context["chart"])), mapping(context["schema"]), mapping(context["defaults"]))
    inventory = InputInventory.build(chart)
    rejections = (
        RejectionPolicy(Contracts.build(chart.path), chart.defaults, (chart.path / "values.schema.json").is_file())
        if context["filtering"]
        else None
    )
    paths = sequence(context["paths"])
    deadline = float(str(context["deadline"]))
    logging.basicConfig(level=logging.INFO)
    with Termination():
        while time.monotonic() < deadline:
            with DeferredSignals(), (directory / "cursor").open("r+") as cursor:
                fcntl.flock(cursor, fcntl.LOCK_EX)
                index = int(cursor.read())
                if index >= len(paths) or (directory / "stop").exists() or time.monotonic() >= deadline:
                    break
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
                save(directory / f"started-{index:08}.json", phase)
                cursor.seek(0)
                cursor.write(str(index + 1))
                cursor.truncate()
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
            if result["status"] == "time-limit":
                break
            if context["fail_fast"] and result["status"] == "failed":
                (directory / "stop").touch()
                break
    return 0

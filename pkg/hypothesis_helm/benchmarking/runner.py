"""
Measure disjoint worker assignments through the real schema, compiler and Helm boundaries.
"""

import bisect
import copy
import hashlib
import json
import math
import resource
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import get_context
from pathlib import Path

from attrs import field, frozen
from jsonschema import validators

from hypothesis_helm.benchmarking.topology import expected_topology, validate_topology
from hypothesis_helm.benchmarking.workload import (
    expected_output,
    load_inputs,
    partition_indices,
    standard_values,
)
from hypothesis_helm.charts.runner import Chart, merge_values, render
from hypothesis_helm.compiler.pruning import Pruner
from hypothesis_helm.execution.render_hashes import RenderHashes
from hypothesis_helm.integrations.sharding import Shard
from hypothesis_helm.reporting.budget import TimeLimitReached, execution_timer
from hypothesis_helm.schemas.contracts import configuration_key, json_value, mapping, sequence
from hypothesis_helm.schemas.model import ValuesModel


@frozen
class Job:
    """
    Describe one replica's share of a benchmark point.

    Attributes:
        chart (str): Source chart path.
        indices (list[int]): Unique global input IDs owned by this replica.
        seed (int): Deterministic workload seed.
        multiplicity (int): Controlled output-equivalence multiplicity.
        pruning (bool): Whether exact compiler pruning is enabled.
        helm (str): Actual Helm executable.
        deadline (float): Shared monotonic deadline across all replicas in the point.
        values (str | None): Custom JSONL workload location.
        checkpoints (list[int]): Requested global-prefix observation boundaries.
        started (float): Shared parent start time for cumulative measurements.
    """

    chart: str
    indices: list[int]
    seed: int
    multiplicity: int
    pruning: bool
    helm: str
    deadline: float
    values: str | None = None
    checkpoints: list[int] = field(factory=list)
    started: float = 0.0


def execute_worker(job: Job) -> dict[str, object]:
    """
    Run a fresh local cache through actual validation, equivalence proofs and Helm.

    Args:
        job (Job): Disjoint assignment and common execution deadline.

    Returns:
        dict[str, object]: Measured successes, renders, proofs, remaining work and distribution.
    """
    started = time.perf_counter()
    attempted = render_invocations = 0
    ledger: list[tuple[bool, int | None, float | None, float, str | None]] = []
    hashes = RenderHashes(scope="benchmark-replica-local")
    input_histogram = [0] * 32
    render_histogram = [0] * 32
    status, error = "passed", None
    oracle_checks = 0
    received_mean = received_m2 = 0.0
    compiler = None
    try:
        if job.deadline <= started:
            raise TimeLimitReached()
        with execution_timer(job.deadline - started):
            chart = Chart.load(job.chart)
            inputs = load_inputs(chart, Path(job.values) if job.values else None)
            spec = mapping(json.loads((chart.path / "benchmark.json").read_text())) if inputs is None else None
            validator = validators.validator_for(chart.schema)(chart.schema)
            model = ValuesModel.from_schema(chart.schema)
            compiler = Pruner(chart.path, chart.defaults, model) if job.pruning else None
            context = configuration_key({"helm": job.helm, "release": "benchmark", "namespace": "default"})
            for index in job.indices:
                if time.perf_counter() >= job.deadline:
                    raise TimeLimitReached()
                values = (
                    inputs[index]
                    if inputs is not None
                    else standard_values(
                        index,
                        job.seed,
                        job.multiplicity,
                        int(str(spec["input_complexity"])) if spec else 100,
                        int(str(spec["output_bins"])) if spec else 256,
                    )
                )
                effective = merge_values(chart.defaults, values)
                attempted += 1
                validator.validate(json_value(effective))
                witness = compiler.candidate(values, effective, context) if compiler else None
                resources = compiler.lookup(witness, attempted) if compiler else None
                reused = resources is not None
                if resources is None:
                    remaining = job.deadline - time.perf_counter()
                    if remaining <= 0:
                        raise TimeLimitReached()
                    render_invocations += 1
                    resources = render(
                        chart,
                        values,
                        helm=job.helm,
                        release="benchmark",
                        timeout=min(30.0, remaining),
                        hashes=hashes,
                    )
                if not resources:
                    raise AssertionError("benchmark chart emitted no resources")
                pristine = copy.deepcopy(resources)
                bucket = None
                if spec is not None:
                    validate_topology(resources, effective, spec)
                    expected = expected_output(effective, spec)
                    data = mapping(resources[0]["data"])
                    if data["value"] != expected:
                        raise AssertionError("rendered quantile differs from the declared distribution")
                    edges = [float(str(value)) for value in sequence(spec["histogram_edges"])]
                    bucket = min(31, max(0, bisect.bisect_right(edges, float(expected)) - 1))
                if compiler:
                    compiler.remember(witness, attempted, pristine)
                received = float(str(mapping(resources[0]["data"])["value"])) if spec else None
                # Commit once so an alarm cannot expose partially updated success counters.
                projection = configuration_key(expected_topology(effective, spec)) if spec is not None and "topology" in spec else None
                ledger.append((reused, bucket, received, time.perf_counter(), projection))
    except TimeLimitReached:
        status = "time-limit"
    except Exception as exc:
        status, error = "failed", f"{type(exc).__name__}: {exc}"
    completed = len(ledger)
    rendered = sum(not reused for reused, _, _, _, _ in ledger)
    pruned = completed - rendered
    render_prefix = [0]
    oracle_prefix = [0]
    received_counts: dict[str, int] = {}
    topology_counts: dict[str, int] = {}
    for reused, bucket, received, _, projection in ledger:
        if projection is not None:
            topology_counts[projection] = topology_counts.get(projection, 0) + 1
        render_prefix.append(render_prefix[-1] + int(not reused))
        oracle_prefix.append(oracle_prefix[-1] + int(bucket is not None))
        if bucket is not None and received is not None:
            key = str(received)
            received_counts[key] = received_counts.get(key, 0) + 1
            oracle_checks += 1
            delta = received - received_mean
            received_mean += delta / oracle_checks
            received_m2 += delta * (received - received_mean)
            input_histogram[bucket] += 1
            render_histogram[bucket] += int(not reused)
    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result: dict[str, object] = {
        "peak_rss_bytes": peak_rss if sys.platform == "darwin" else peak_rss * 1024,
        "render_invocations": render_invocations,
        "last_completed_index": job.indices[completed - 1] if completed else None,
        "oracle_checks": oracle_checks,
        "received_mean": received_mean if oracle_checks else None,
        "received_stddev": math.sqrt(max(0.0, received_m2 / oracle_checks)) if oracle_checks else None,
        "status": status,
        "error": error,
        "assigned": len(job.indices),
        "attempted": attempted,
        "completed": completed,
        "remaining": len(job.indices) - completed,
        "rendered": rendered,
        "pruned": pruned,
        "assignment_sha256": hashlib.sha256(json.dumps(job.indices).encode()).hexdigest(),
        "first_index": job.indices[0] if job.indices else None,
        "last_index": job.indices[-1] if job.indices else None,
        "elapsed_seconds": time.perf_counter() - started,
        "render_hashes": hashes.snapshot(),
        "compiler_fallback": compiler.disabled if compiler else None,
        "input_histogram": input_histogram,
        "received_counts": received_counts,
        "topology_counts": topology_counts,
        "render_histogram": render_histogram,
    }

    checkpoints: list[dict[str, object]] = []
    for count in job.checkpoints:
        needed = bisect.bisect_left(job.indices, count)
        if needed > completed:
            break
        elapsed = ledger[needed - 1][3] - job.started if needed else 0.0
        checkpoints.append(
            {
                "requested_permutations": count,
                "assigned": needed,
                "attempted": needed,
                "completed": needed,
                "remaining": 0,
                "rendered": render_prefix[needed],
                "render_invocations": render_prefix[needed],
                "pruned": needed - render_prefix[needed],
                "oracle_checks": oracle_prefix[needed],
                "status": "passed",
                "elapsed_seconds": elapsed,
                "completed_per_second": needed / elapsed if elapsed else 0.0,
            }
        )
    result["checkpoints"] = checkpoints
    return result


def measure(
    chart: Path,
    count: int,
    replicas: int,
    pruning: bool,
    *,
    seed: int,
    multiplicity: int,
    time_limit: float,
    helm: str,
    shard: Shard | None,
    values: Path | None = None,
    checkpoints: list[int] | None = None,
) -> dict[str, object]:
    """
    Measure one capped benchmark point with fresh workers and a common deadline.

    Args:
        chart (Path): Chart being benchmarked.
        count (int): Global distinct permutation prefix size.
        replicas (int): Local parallel worker count.
        pruning (bool): Whether to enable exact-equivalence pruning.
        seed (int): Stable input generation seed.
        multiplicity (int): Inputs generated for each live output vector.
        time_limit (float): Shared wall-clock execution limit, including worker startup.
        helm (str): Real renderer executable.
        shard (Shard | None): CI partition applied before local replica assignment.
        values (Path | None): Custom JSONL overrides instead of the standard generator.
        checkpoints (list[int] | None): Cumulative boundaries for a single progressive worker.

    Returns:
        dict[str, object]: Aggregate real measurements and individual worker evidence.
    """
    if not math.isfinite(time_limit) or not 0 < time_limit <= 540:
        raise ValueError("benchmark time limit must be positive and at most 540 seconds")
    if checkpoints and replicas != 1:
        raise ValueError("progressive checkpoints require one local worker")
    assignments = partition_indices(count, shard, replicas)
    started = time.perf_counter()
    deadline = started + time_limit
    results: list[dict[str, object]] = []
    jobs = [
        Job(
            str(chart.resolve()),
            indices,
            seed,
            multiplicity,
            pruning,
            helm,
            deadline,
            str(values.resolve()) if values else None,
            checkpoints or [],
            started,
        )
        for indices in assignments
        if indices
    ]
    if jobs:
        with ProcessPoolExecutor(max_workers=len(jobs), mp_context=get_context("spawn")) as pool:
            futures = [pool.submit(execute_worker, job) for job in jobs]
            for future in as_completed(futures):
                results.append(future.result())
    elapsed = time.perf_counter() - started
    totals = {
        name: sum(int(str(result[name])) for result in results)
        for name in (
            "assigned",
            "attempted",
            "completed",
            "remaining",
            "rendered",
            "render_invocations",
            "pruned",
            "oracle_checks",
        )
    }
    status = (
        "failed"
        if any(result["status"] == "failed" for result in results)
        else "time-limit"
        if any(result["status"] == "time-limit" for result in results)
        else "passed"
    )
    return {
        "requested_permutations": count,
        "replicas": replicas,
        "active_replicas": len(jobs),
        "pruning": pruning,
        "status": status,
        "time_limit_seconds": time_limit,
        "elapsed_seconds": elapsed,
        "completed_per_second": totals["completed"] / elapsed if elapsed else 0,
        **totals,
        "workers": results,
        "shard": {"index": shard.index, "total": shard.total} if shard else None,
    }

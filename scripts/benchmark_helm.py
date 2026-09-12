"""
Run capped real Helm workloads and generate reproducible permutation and replica plots.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from hypothesis_helm.charts.runner import Chart
from hypothesis_helm.integrations.sharding import parse_shard_option, resolve_shard
from hypothesis_helm.reporting.budget import parse_time_limit
from hypothesis_helm.schemas.contracts import mapping, sequence

from scripts.benchmarking.runner import measure
from scripts.benchmarking.workload import MULTIPLICITY, VERSION, load_inputs, source_digest

ROOT = Path(__file__).resolve().parents[1]


def positive_counts(value: str) -> list[int]:
    """
    Parse sorted unique positive integers for workload sizes or replica counts.

    Args:
        value (str): Comma-separated positive integers.

    Returns:
        list[int]: Sorted distinct integers.
    """
    try:
        values = sorted({int(item) for item in value.split(",")})
        if values and values[0] > 0:
            return values
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("expected comma-separated positive integers")


def parser() -> argparse.ArgumentParser:
    """
    Build the standalone benchmark CLI.

    Returns:
        argparse.ArgumentParser: Workload, sharding, replication and plotting controls.
    """
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--chart", type=Path, default=ROOT / "examples/benchmark")
    result.add_argument("--values", type=Path, help="distinct JSONL overrides for a custom chart")
    result.add_argument("--output", type=Path, default=ROOT / "docs/benchmarks")
    result.add_argument("--helm", default="helm")
    result.add_argument(
        "--time-limit",
        type=parse_time_limit,
        default=540.0,
        help="shared per-point worker deadline; default and ceiling: 9m",
    )
    result.add_argument(
        "--step", type=int, default=50, help="linear progressive checkpoint interval"
    )
    result.add_argument("--max-permutations", type=int, default=200000)
    result.add_argument(
        "--counts", type=positive_counts, help="optional explicit prefix checkpoints"
    )
    result.add_argument("--scaling-counts", type=positive_counts, default=list(range(50, 501, 50)))
    result.add_argument(
        "--replicas",
        "--shards",
        dest="replicas",
        type=positive_counts,
        default=[1, 2, 3, 4],
        help="parallel worker shards on this host",
    )
    result.add_argument(
        "--repeats",
        type=int,
        default=1,
        help="independent repetitions; use at least 3 for variability",
    )
    result.add_argument("--seed", type=int, default=2026)
    result.add_argument("--multiplicity", type=int, default=MULTIPLICITY)
    result.add_argument("--shard", type=parse_shard_option, default="auto")
    result.add_argument("--suite", choices=["all", "progressive", "scaling"], default="all")
    result.add_argument(
        "--resume", action="store_true", help="reuse matching completed measurements"
    )
    result.add_argument("--plot-only", action="store_true", help="plot saved measurements only")
    return result


def code_digest() -> str:
    """
    Identify measured application and harness code, including uncommitted changes.

    Returns:
        str: SHA-256 fingerprint of execution and harness Python sources.
    """
    digest = hashlib.sha256()
    for base in (ROOT / "pkg/hypothesis_helm", ROOT / "scripts"):
        for path in sorted(base.rglob("*.py")):
            if "tests" not in path.parts:
                digest.update(str(path.relative_to(ROOT)).encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()


def save(output: Path, document: dict[str, object]) -> None:
    """
    Atomically persist measurements and a flat CSV after every completed benchmark point.

    Args:
        output (Path): Shard-specific artifact directory.
        document (dict[str, object]): Metadata and raw per-worker measurements.

    Returns:
        None: JSON retains raw evidence and CSV exposes aggregate plotting columns.
    """
    output.mkdir(parents=True, exist_ok=True)
    temporary = output / "results.json.tmp"
    temporary.write_text(json.dumps(document, indent=2) + "\n")
    temporary.replace(output / "results.json")
    points = [mapping(point) for point in sequence(document["points"])]
    fields = [
        "requested_permutations",
        "replicas",
        "repeat",
        "pruning",
        "status",
        "assigned",
        "oracle_checks",
        "attempted",
        "completed",
        "remaining",
        "rendered",
        "render_invocations",
        "pruned",
        "elapsed_seconds",
        "completed_per_second",
        "time_limit_seconds",
    ]
    with (output / "results.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(points)


def run(argv: list[str] | None = None) -> int:
    """
    Execute progressive and scaling matrices without mixing shards or workload identities.

    Args:
        argv (list[str] | None): CLI arguments or process arguments.

    Returns:
        int: Zero for successful measurements, one for chart failures or incomplete matrices.
    """
    args = parser().parse_args(argv)
    if (
        args.step < 1
        or args.max_permutations < 1
        or args.time_limit > 540
        or args.repeats < 1
        or args.multiplicity < 1
        or args.multiplicity & (args.multiplicity - 1)
    ):
        raise ValueError(
            "limit must be <= 9m; repeats positive; multiplicity a positive power of two"
        )
    shard, shard_source = resolve_shard(args.shard, os.environ)
    output = args.output / f"shard-{shard.name}" if shard else args.output
    if args.plot_only:
        from scripts.benchmarking.plots import plot

        plot(output, mapping(json.loads((output / "results.json").read_text())))
        return 0
    helm = shutil.which(args.helm)
    if helm is None:
        raise ValueError(f"Helm executable not found: {args.helm}")
    chart = Chart.load(args.chart)
    inputs = load_inputs(chart, args.values)
    spec = (
        mapping(json.loads((chart.path / "benchmark.json").read_text())) if inputs is None else None
    )
    available = 2 ** int(str(spec["input_complexity"])) if spec else len(inputs or [])
    shard_total = shard.total if shard else 1
    metadata: dict[str, object] = {
        "format_version": 1,
        "workload": VERSION if inputs is None else "custom-jsonl",
        "distribution": spec,
        "chart_sha256": source_digest(chart.path),
        "values_sha256": hashlib.sha256(args.values.read_bytes()).hexdigest()
        if args.values
        else None,
        "code_sha256": code_digest(),
        "seed": args.seed,
        "multiplicity": args.multiplicity,
        "time_limit_seconds": args.time_limit,
        "repeats": args.repeats,
        "counts": args.counts,
        "step": args.step,
        "max_permutations": args.max_permutations,
        "scaling_counts": args.scaling_counts,
        "replicas": args.replicas,
        "shard": {"index": shard.index, "total": shard.total} if shard else None,
        "shard_source": shard_source,
        "assignment": "global ID modulo shard total; contiguous local replica blocks",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "logical_cpus": os.cpu_count(),
        "helm": subprocess.check_output([helm, "version", "--short"], text=True).strip(),
        "matplotlib": importlib.metadata.version("matplotlib"),
        "cache_scope": (
            "fresh caches per scaling point and progressive trajectory; "
            "progressive checkpoints share their trajectory cache"
        ),
        "timing": (
            "wall time includes spawn, chart loading, input generation and validation; "
            "cleanup measured"
        ),
        "coverage": (
            "distinct seeded input prefixes; counts are not --permutations interaction strengths"
        ),
        "replicas_meaning": "parallel benchmark worker processes, not Kubernetes replicas",
    }
    points: list[object] = []
    if (output / "results.json").exists():
        if not args.resume:
            raise ValueError(f"{output}/results.json exists; use --resume or another --output")
        previous = mapping(json.loads((output / "results.json").read_text()))
        if previous["metadata"] != metadata:
            raise ValueError(
                "cannot resume: chart, code, workload, machine or shard settings changed"
            )
        points = sequence(previous["points"])
    document: dict[str, object] = {
        "metadata": metadata,
        "created_at": datetime.now(UTC).isoformat(),
        "points": points,
    }

    def point(
        count: int, replicas: int, pruning: bool, repeat: int, family: str
    ) -> dict[str, object]:
        """
        Measure or reuse an identical point and attach its explicit study memberships.

        Args:
            count (int): Global permutation count before CI assignment.
            replicas (int): Local parallel worker count.
            pruning (bool): Exact-equivalence pruning setting.
            repeat (int): Independent repetition number.
            family (str): Progressive, strong or weak scaling study.

        Returns:
            dict[str, object]: A matching measured point with immutable input identity.
        """
        if count > available:
            raise ValueError(
                f"requested {count} permutations but the workload contains {available}"
            )
        for item in points:
            saved = mapping(item)
            if saved.get("observation", "independent-run") != "independent-run":
                continue
            if (
                saved["requested_permutations"],
                saved["replicas"],
                saved["pruning"],
                saved["repeat"],
            ) == (
                count,
                replicas,
                pruning,
                repeat,
            ):
                families = sequence(saved["families"])
                if family not in families:
                    families.append(family)
                    save(output, document)
                return saved
        print(
            f"{family}: {count} global permutations, {replicas} local replicas, "
            f"pruning={pruning}, repeat={repeat + 1}, shard={metadata['shard']}",
            flush=True,
        )
        measured = measure(
            chart.path,
            count,
            replicas,
            pruning,
            seed=args.seed + repeat,
            multiplicity=args.multiplicity,
            time_limit=args.time_limit,
            helm=helm,
            shard=shard,
            values=args.values,
        )
        measured.update({"repeat": repeat, "families": [family], "observation": "independent-run"})
        points.append(measured)
        save(output, document)
        print(
            f"  {measured['status']}: {measured['completed']}/{measured['assigned']} completed; "
            f"{measured['render_invocations']} Helm invocations, "
            f"{measured['pruned']} proved equivalent; "
            f"{float(str(measured['elapsed_seconds'])):.2f}s",
            flush=True,
        )
        if measured["status"] == "failed":
            raise RuntimeError(f"benchmark chart failed; inspect {output}/results.json")
        return measured

    try:
        if args.suite in ("all", "progressive"):
            ceiling = min(args.max_permutations, available)
            targets = args.counts or list(range(args.step, ceiling + 1, args.step)) or [ceiling]
            if max(targets) > available:
                raise ValueError("prefix checkpoints exceed the finite workload size")
            for repeat in range(args.repeats):
                for pruning in (False, True):
                    identity = f"progressive-{repeat}-{int(pruning)}"
                    if any(mapping(item).get("trajectory") == identity for item in points):
                        continue
                    print(
                        f"progressive trajectory: checkpoints every {args.step} inputs, "
                        f"ceiling {args.time_limit:g}s, pruning={pruning}, "
                        f"shard={metadata['shard']}",
                        flush=True,
                    )
                    measured = measure(
                        chart.path,
                        max(targets),
                        1,
                        pruning,
                        seed=args.seed + repeat,
                        multiplicity=args.multiplicity,
                        time_limit=args.time_limit,
                        helm=helm,
                        shard=shard,
                        values=args.values,
                        checkpoints=targets,
                    )
                    measured.update(
                        {
                            "repeat": repeat,
                            "families": ["progressive-run"],
                            "observation": "progressive-run",
                            "trajectory": identity,
                        }
                    )
                    points.append(measured)
                    checkpoints = [
                        mapping(checkpoint)
                        for worker in sequence(measured["workers"])
                        for checkpoint in sequence(mapping(worker)["checkpoints"])
                    ]
                    for checkpoint in checkpoints:
                        points.append(
                            {
                                **checkpoint,
                                "replicas": 1,
                                "pruning": pruning,
                                "repeat": repeat,
                                "families": ["progressive"],
                                "observation": "shared-prefix",
                                "trajectory": identity,
                                "time_limit_seconds": args.time_limit,
                                "shard": metadata["shard"],
                                "workers": [],
                            }
                        )
                    completed_targets = {
                        int(str(row["requested_permutations"])) for row in checkpoints
                    }
                    if measured["status"] == "time-limit":
                        # These are two censored targets from the SAME observed execution window,
                        # not independent runs or extrapolated completion times.
                        for target in [
                            value for value in targets if value not in completed_targets
                        ][:2]:
                            assigned = (
                                len(range(shard.index - 1, target, shard.total))
                                if shard
                                else target
                            )
                            points.append(
                                {
                                    **measured,
                                    "requested_permutations": target,
                                    "assigned": assigned,
                                    "remaining": assigned - int(str(measured["completed"])),
                                    "families": ["progressive"],
                                    "observation": "shared-prefix-censored",
                                    "censoring_upper_target": max(targets),
                                    "workers": [],
                                }
                            )
                    save(output, document)
                    print(
                        f"  {measured['status']}: {measured['completed']} completed; "
                        f"{measured['render_invocations']} Helm invocations; "
                        f"{len(checkpoints)} completed checkpoints",
                        flush=True,
                    )
                    if measured["status"] == "failed":
                        raise RuntimeError("benchmark output failed; inspect saved worker evidence")
        if args.suite in ("all", "scaling"):
            if 1 not in args.replicas:
                raise ValueError("scaling requires a one-replica baseline")
            for repeat in range(args.repeats):
                for count in args.scaling_counts:
                    for replicas in args.replicas:
                        point(count * shard_total, replicas, True, repeat, "strong")
                        point(count * replicas * shard_total, replicas, True, repeat, "weak")
    except KeyboardInterrupt:
        save(output, document)
        print(f"Interrupted; completed points retained in {output}", file=sys.stderr)
        return 130
    from scripts.benchmarking.plots import plot

    plot(output, document)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())

"""
Scan manifest streams with core-sized GNU Parallel pools and local Kubernetes schemas.
"""

import argparse
import json
import os
import shutil
from pathlib import Path

from hypothesis_helm.execution.processes import Processes
from hypothesis_helm.integrations.sharding import Shard, parse_shard_option, resolve_shard
from hypothesis_helm.schemas.conformity import prepare
from hypothesis_helm.schemas.contracts import mapping

SUPPORTED = {"Pod", "Deployment", "StatefulSet", "DaemonSet"}


def worker_count(value: str) -> int:
    """
    Resolve automatic concurrency from the logical CPUs available to this process.

    Args:
        value (str): Auto or a positive worker count.

    Returns:
        int: Number of concurrent Kubesec processes on this runner.
    """
    if value == "auto":
        return os.process_cpu_count() or 1
    try:
        count = int(value)
        if count > 0:
            return count
    except ValueError:
        pass
    raise ValueError("Kubesec jobs must be auto or a positive integer")


def scan(
    manifests: Path,
    output: Path,
    configuration: str,
    *,
    jobs: str = "auto",
    executable: str = "kubesec",
    shard: Shard | None = None,
    pre_sharded: bool = False,
    validate_rest: bool = False,
) -> int:
    """
    Run each supported resource through GNU Parallel and retain every scan result.

    Args:
        manifests (Path): JSON Lines resource stream, possibly already owned by a shard.
        output (Path): Artifact root; shard coordinates select an isolated subdirectory.
        configuration (str): Prepared local conformity configuration serialized as JSON.
        jobs (str): Auto CPU count or explicit positive concurrency limit.
        executable (str): Installed Kubesec binary.
        shard (Shard | None): Partition coordinates for a shared input stream.
        pre_sharded (bool): Input is already selected; do not partition its records again.
        validate_rest (bool): Route unsupported resources to standalone Kubeconform.

    Returns:
        int: Zero if all scans succeed, one if any scan fails.
    """
    workers = worker_count(jobs)
    settings = mapping(json.loads(configuration))
    binary, parallel = shutil.which(executable), shutil.which("parallel")
    if not binary or not parallel:
        raise ValueError("Kubesec scanning requires kubesec and GNU Parallel")
    version = Processes().run([parallel, "--version"], capture_output=True, text=True, timeout=10)
    if version.returncode or not version.stdout.startswith("GNU parallel"):
        raise ValueError("parallel must be GNU Parallel")
    output = output.resolve()
    if shard:
        output = output / "shards" / shard.name
    output.mkdir(parents=True, exist_ok=True)
    records = output / "manifests"
    records.mkdir(exist_ok=True)
    tasks = output / "tasks.bin"
    selected, skipped = 0, 0
    remaining = output / "kubeconform.yaml"
    with (
        manifests.open() as source,
        tasks.open("wb") as destinations,
        remaining.open("w") as fallback,
    ):
        for index, line in enumerate(source):
            if not line.strip():
                continue
            if shard and not pre_sharded and index % shard.total != shard.index - 1:
                continue
            resource = mapping(json.loads(line))
            if resource.get("kind") not in SUPPORTED:
                skipped += 1
                if validate_rest:
                    fallback.write("---\n" + json.dumps(resource) + "\n")
                continue
            path = records / f"{index + 1:08d}.json"
            path.write_text(json.dumps(resource) + "\n")
            destinations.write(os.fsencode(path) + b"\0")
            selected += 1
    command = [
        parallel,
        "--plain",
        "--term-seq",
        "TERM,10000,KILL,1000",
        "--jobs",
        str(workers),
        "--halt",
        "never",
        "--null",
        "--arg-file",
        str(tasks),
        "--joblog",
        str(output / "joblog.tsv"),
        "--results",
        str(output / "results"),
        "--quote",
        "--replace",
        "__HH_MANIFEST__",
        binary,
        "scan",
        "--kubernetes-version",
        str(settings["version"]),
        "--schema-location",
        str(settings["schemas"]) + "/{{ .ResourceKind }}{{ .KindSuffix }}.json",
        "__HH_MANIFEST__",
    ]
    if any("__HH_MANIFEST__" in str(path) for path in (output, settings["schemas"], binary)):
        raise ValueError("reserved GNU Parallel replacement token in path")
    disposition = "routed to Kubeconform" if validate_rest else "skipped"
    print(f"Kubesec: {selected} resources, {workers} workers, {skipped} {disposition}")
    status = 0
    if selected:
        with (output / "parallel.stdout").open("w") as stdout:
            result = Processes(interrupt_grace=12).run(command, cwd=Path.cwd(), env={**os.environ, "GOMAXPROCS": "1"}, stdout=stdout)
        status = int(result.returncode != 0)
    conformity_status = 0
    if validate_rest and skipped:
        with (output / "kubeconform.json").open("w") as stdout:
            result = Processes().run(
                [
                    str(settings["executable"]),
                    "-strict",
                    "-n",
                    str(workers),
                    "-kubernetes-version",
                    str(settings["version"]),
                    "-schema-location",
                    str(settings["schemas"]) + "/{{ .ResourceKind }}{{ .KindSuffix }}.json",
                    "-output",
                    "json",
                    str(remaining),
                ],
                cwd=Path.cwd(),
                env=dict(os.environ),
                stdout=stdout,
            )
        conformity_status = int(result.returncode != 0)
    status = status or conformity_status
    report = {
        "status": "failed" if status else "passed",
        "scanned": selected,
        "skipped": 0 if validate_rest else skipped,
        "kubeconform_scanned": skipped if validate_rest else 0,
        "kubeconform_exit_code": conformity_status,
        "jobs": workers,
        "shard": shard.name if shard else None,
        "pre_sharded": pre_sharded,
        "schema_version": settings["version"],
        "schema_identity": settings["identity"],
    }
    (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    return status


def main() -> int:
    """
    Scan saved CI manifests against restored schemas with optional shard selection.

    Returns:
        int: Scan status or two for an invalid setup.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifests", type=Path)
    parser.add_argument("--output", type=Path, default=Path("reports/kubesec"))
    parser.add_argument("--jobs", default="auto")
    parser.add_argument("--shard", type=parse_shard_option, default="auto")
    parser.add_argument("--pre-sharded", action="store_true")
    parser.add_argument("--validate-rest", action="store_true", help="Validate other kinds with Kubeconform")
    parser.add_argument("--schema-version", default="latest")
    parser.add_argument("--schema-cache-dir", type=Path, default=Path(".cache/hypothesis-helm/schemas"))
    parser.add_argument("--schema-offline", action="store_true")
    parser.add_argument("--kubeconform-binary", default="kubeconform")
    parser.add_argument("--kubesec-binary", default="kubesec")
    args = parser.parse_args()
    try:
        worker_count(args.jobs)
        shard, _ = resolve_shard(args.shard, os.environ)
        configuration = prepare(args.schema_cache_dir, args.schema_version, args.kubeconform_binary, args.schema_offline)
        return scan(
            args.manifests,
            args.output,
            configuration,
            jobs=args.jobs,
            executable=args.kubesec_binary,
            shard=shard,
            pre_sharded=args.pre_sharded,
            validate_rest=args.validate_rest,
        )
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Kubesec setup failed: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())

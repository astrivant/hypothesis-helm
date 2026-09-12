"""
Run the composite GitHub Action through the Helm command and export artifact paths.
"""

import os
import sys
import uuid
from pathlib import Path

from hypothesis_helm.execution.processes import Processes
from hypothesis_helm.integrations.kubesec import scan
from hypothesis_helm.integrations.sharding import parse_shard_option, resolve_shard
from hypothesis_helm.schemas.conformity import prepare


def write_outputs(values: dict[str, str]) -> None:
    """
    Append action outputs without allowing newline-containing values to add output keys.

    Args:
        values (dict[str, str]): Output names and values.

    Returns:
        None: GitHub receives the action's result and artifact locations.
    """
    destination = os.environ.get("GITHUB_OUTPUT")
    if destination is not None:
        with Path(destination).open("a") as stream:
            for key, value in values.items():
                delimiter = "hypothesis_" + uuid.uuid4().hex
                stream.write(f"{key}<<{delimiter}\n{value}\n{delimiter}\n")


def main() -> int:
    """
    Translate action inputs into a Helm invocation while preserving failure status.

    Returns:
        int: Helm exit status, including 130 on interruption.
    """
    status = 2
    outputs: dict[str, str] = {}
    try:
        shard, source = resolve_shard(
            parse_shard_option(os.environ.get("HH_SHARD", "auto")), os.environ
        )
        root = Path(os.environ.get("HH_ARTIFACT_DIR", "reports/hypothesis-helm")).resolve()
        results = root / "shards" / shard.name if shard is not None else root
        results.mkdir(parents=True, exist_ok=True)
        manifests = results / "manifests.jsonl"
        outputs = {
            "report-dir": str(results),
            "junit-path": str(results / "junit.xml"),
            "manifest-path": str(manifests),
            "shard": f"{shard.index}/{shard.total}" if shard is not None else "none",
            "shard-id": shard.name if shard is not None else "unsharded",
            "shard-source": source,
        }
        command = [
            "helm",
            "hypothesis",
            "test",
            str(Path(os.environ.get("HH_CHART", ".")).resolve()),
            "--shard",
            outputs["shard"],
            "--jobs",
            os.environ.get("HH_JOBS", "auto"),
            "--max-examples",
            os.environ.get("HH_MAX_EXAMPLES", "100"),
            "--seed",
            os.environ.get("HH_SEED", "0"),
            "--timeout",
            os.environ.get("HH_TIMEOUT", "30"),
            "--artifact-dir",
            str(root),
            "--output",
            "json",
        ]
        security = os.environ.get("HH_KUBESEC", "false").lower() == "true"
        command += ["--rerun", "all" if security else os.environ.get("HH_RERUN", "auto")]
        cache_dir = os.environ.get("HH_CACHE_DIR")
        if cache_dir:
            command += ["--cache-dir", cache_dir]
        if os.environ.get("HH_DISABLE_SCHEMA_CACHING", "false").lower() == "true":
            command.append("--disable-schema-caching")
        if os.environ.get("HH_CACHE", "true").lower() == "false":
            command.append("--no-cache")
        if not security and os.environ.get("HH_KUBECONFORM", "true").lower() == "true":
            command += [
                "--kubeconform",
                "--schema-version",
                os.environ.get("HH_SCHEMA_VERSION", "latest"),
                "--schema-cache-dir",
                os.environ.get("HH_SCHEMA_CACHE_DIR", ".cache/hypothesis-helm/schemas"),
                "--kubeconform-binary",
                os.environ.get("HH_KUBECONFORM_BINARY", "kubeconform"),
            ]
            if os.environ.get("HH_SCHEMA_OFFLINE", "false").lower() == "true":
                command.append("--schema-offline")
        match = os.environ.get("HH_MATCH")
        if match:
            command += ["--match", match]
        with manifests.open("w") as stream:
            # Give the Helm parent time to stop its own pytest process groups.
            result = Processes(interrupt_grace=5.0).run(
                command, cwd=Path.cwd(), env=dict(os.environ), stdout=stream
            )
        status = result.returncode if result.returncode >= 0 else 130
        if security and status != 130:
            configuration = prepare(
                Path(os.environ.get("HH_SCHEMA_CACHE_DIR", ".cache/hypothesis-helm/schemas")),
                os.environ.get("HH_SCHEMA_VERSION", "latest"),
                os.environ.get("HH_KUBECONFORM_BINARY", "kubeconform"),
                offline=True,
            )
            security_status = scan(
                manifests,
                root / "kubesec",
                configuration,
                jobs=os.environ.get("HH_KUBESEC_JOBS", "auto"),
                executable=os.environ.get("HH_KUBESEC_BINARY", "kubesec"),
                shard=shard,
                pre_sharded=True,
                validate_rest=True,
            )
            security_dir = root / "kubesec"
            if shard:
                security_dir = security_dir / "shards" / shard.name
            outputs["kubesec-report-dir"] = str(security_dir)
            outputs["kubesec-exit-code"] = str(security_status)
            status = status or security_status
    except KeyboardInterrupt:
        print("Testing interrupted", file=sys.stderr)
        status = 130
    except Exception as exc:
        print(f"Action setup failed: {exc}", file=sys.stderr)
        status = status or 2
    finally:
        outputs["exit-code"] = str(status)
        write_outputs(outputs)
    return status


if __name__ == "__main__":
    raise SystemExit(main())

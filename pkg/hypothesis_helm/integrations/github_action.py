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
    Run the explicit Bash command while preserving shard outputs and failure status.

    Returns:
        int: Helm exit status, including 130 on interruption.
    """
    status = 2
    outputs: dict[str, str] = {}
    try:
        shard, source = resolve_shard(parse_shard_option(os.environ.get("HH_SHARD", "auto")), os.environ)
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
        security = os.environ.get("HH_KUBESEC", "false").lower() == "true"
        with manifests.open("w") as stream:
            # Give the Helm parent time to stop its own pytest process groups.
            result = Processes(interrupt_grace=10.0).run(
                ["bash", str(Path(__file__).with_suffix(".sh"))],
                cwd=Path.cwd(),
                env={
                    **os.environ,
                    **{
                        key: value.lower()
                        for key, value in os.environ.items()
                        if key
                        in {
                            "HH_KUBESEC",
                            "HH_KUBECONFORM",
                            "HH_CACHE",
                            "HH_SCHEMA_OFFLINE",
                            "HH_DISABLE_SCHEMA_CACHING",
                        }
                    },
                    "HH_ARTIFACT_DIR": str(root),
                    "HH_RESULT_DIR": str(results),
                    "HH_RESOLVED_SHARD": outputs["shard"],
                },
                stdout=stream,
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

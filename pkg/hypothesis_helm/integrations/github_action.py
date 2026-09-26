"""
Run the composite GitHub Action through the Helm command and export artifact paths.
"""

import json
import sys
import tempfile
import uuid
from pathlib import Path

from ruamel.yaml import YAML

from hypothesis_helm.environment import env, refresh_env, set_env
from hypothesis_helm.execution.runtime.processes import Processes
from hypothesis_helm.integrations.action_config import prepare_config
from hypothesis_helm.integrations.action_options import COMMANDS, normalize_options
from hypothesis_helm.integrations.incremental import select_rerun
from hypothesis_helm.integrations.kubesec import scan
from hypothesis_helm.integrations.sharding import Shard, parse_shard_option, resolve_shard
from hypothesis_helm.rules import ENVIRONMENT as RULE_ENVIRONMENT
from hypothesis_helm.rules import load_ignored
from hypothesis_helm.schemas.configuration.policy import ENVIRONMENT as INPUT_ENVIRONMENT
from hypothesis_helm.schemas.configuration.policy import load_policy
from hypothesis_helm.schemas.kubernetes.conformity import prepare

__all__ = ("main", "write_outputs")


def write_outputs(values: dict[str, str]) -> None:
    """
    Append action outputs without allowing newline-containing values to add output keys.

    Args:
        values (dict[str, str]): Output names and values.

    Returns:
        None: GitHub receives the action's result and artifact locations.
    """
    destination = env.get("GITHUB_OUTPUT")
    if destination is not None:
        with Path(destination).open("a") as stream:
            for key, value in values.items():
                delimiter = "hypothesis_" + uuid.uuid4().hex
                stream.write(f"{key}<<{delimiter}\n{value}\n{delimiter}\n")


def scan_with_policy(manifests: Path, root: Path, config: Path | None, shard: Shard | None, score_minimum: int) -> int:
    """
    Apply the same resource schemas and parser settings to post-test security validation.

    Args:
        manifests (Path): JSON Lines supplied to the security dispatcher.
        root (Path): Action artifact directory.
        config (Path | None): Effective configuration used by chart execution.
        shard (Shard | None): Partition already applied to the manifest stream.
        score_minimum (int): Inclusive Kubesec score threshold.

    Returns:
        int: Security status, restoring the caller's environment even after cancellation.
    """
    policy = load_policy(
        config,
        yaml_parser=env.get("HH_YAML_PARSER") or None,
        strict=env["HH_STRICT"].lower() == "true" if env.get("HH_STRICT") else None,
    )
    codes = [
        code.strip()
        for name in ("HH_IGNORE", "HH_DISABLE_CODES")
        for code in env.get(name, "").replace("\n", ",").split(",")
        if code.strip()
    ]
    ignored = load_ignored(config, codes)
    previous_policy = set_env(INPUT_ENVIRONMENT, json.dumps(policy))
    previous_rules = set_env(RULE_ENVIRONMENT, json.dumps(ignored))
    try:
        configuration = prepare(
            Path(env.get("HH_SCHEMA_CACHE_DIR", "schemas")),
            env.get("HH_SCHEMA_VERSION", "latest"),
            offline=True,
        )
        return scan(
            manifests,
            root / "kubesec",
            configuration,
            jobs=env.get("HH_KUBESEC_JOBS", "auto"),
            executable=env.get("HH_KUBESEC_BINARY", "kubesec"),
            shard=shard,
            pre_sharded=True,
            validate_rest=True,
            score_minimum=score_minimum,
            run_id=env.get("HH_RUN_ID", ""),
        )
    finally:
        set_env(INPUT_ENVIRONMENT, previous_policy)
        set_env(RULE_ENVIRONMENT, previous_rules)


def main() -> int:
    """
    Run the explicit Bash command while preserving shard outputs and failure status.

    Returns:
        int: Helm exit status, including 130 on interruption.
    """
    refresh_env()
    status = 2
    outputs: dict[str, str] = {}
    try:
        command = env.get("HH_COMMAND") or "test"
        if command not in COMMANDS:
            raise ValueError(f"command must be one of {', '.join(COMMANDS)}")
        requested_shard = env.get("HH_SHARD") or "auto"
        if command not in {"test", "run"} and requested_shard not in {"auto", "none"}:
            raise ValueError(f"command '{command}' does not support sharding")
        shard, source = resolve_shard(parse_shard_option(requested_shard if command in {"test", "run"} else "none"), env)
        root = Path(env.get("HH_ARTIFACT_DIR", ".cache/hypothesis-helm/runs")).resolve()
        results = root / "shards" / shard.name if shard is not None else root
        results.mkdir(parents=True, exist_ok=True)
        output_format = env.get("HH_OUTPUT_FORMAT") or "json"
        if output_format not in {"json", "yaml"}:
            raise ValueError("output-format must be json or yaml")
        rendering = command in {"test", "scan", "run"} and not any(
            env.get(key, "").lower() == "true" for key in ("HH_DRY_RUN", "HH_COLLECT_ONLY")
        )
        manifests = results / ("manifests.yaml" if output_format == "yaml" else "manifests.jsonl")
        captured = manifests if rendering else results / "command-output.txt"
        outputs = {
            "report-dir": str(results),
            "junit-path": str(results / "junit.xml"),
            "manifest-path": str(manifests) if rendering else "",
            "command-output": str(captured) if not rendering else "",
            "shard": f"{shard.index}/{shard.total}" if shard is not None else "none",
            "shard-id": shard.name if shard is not None else "unsharded",
            "shard-source": source,
        }
        security = env.get("HH_KUBESEC", "false").lower() == "true"
        if security and not rendering:
            raise ValueError("kubesec requires a test, scan, or run that renders manifests; omit dry-run and collect-only")
        score_minimum = int(env.get("HH_KUBESEC_SCORE_MINIMUM", "0")) if security else 0
        if score_minimum < 0:
            raise ValueError("Kubesec score minimum must be nonnegative")
        incremental = env.get("HH_INCREMENTAL", "false").lower() == "true"
        if incremental and command != "test":
            raise ValueError("incremental is supported by command: test; use base-ref for remote scans")
        environment = normalize_options(dict(env), command)
        chart = env.get("HH_SOURCE") or env.get("HH_CHART") or "."
        if command == "run" and (env.get("HH_EXPORT_MINIMAL_VALUES") == "true" or env.get("HH_COMMIT_MINIMAL_VALUES") == "true"):
            raise ValueError("minimal-values export requires chart sources, not a saved suite")
        if command == "scan" and env.get("HH_COMMIT_MINIMAL_VALUES") == "true":
            raise ValueError("commit-minimal-values requires local charts; use command: test")
        config = prepare_config(
            env.get("HH_CONFIG", ""),
            env.get("HH_CONFIG_INLINE", ""),
            Path(tempfile.mkdtemp(prefix="hypothesis-helm-action-", dir=env.get("RUNNER_TEMP"))) / "config.yaml",
        )
        outputs["effective-config"] = str(config) if config else ""
        environment.update(
            HH_COMMAND=command,
            HH_SOURCE=chart,
            HH_CONFIG=str(config) if config else "",
            HH_ARTIFACT_DIR=str(root),
            HH_RESULT_DIR=str(results),
            HH_SHARD=outputs["shard"],
            HH_OUTPUT_FORMAT=output_format,
        )
        if not environment.get("HH_LOG_FILE"):
            # Audit and dry-run stdout is saved too; keep their diagnostics visible in
            # the job log just as they are for commands that stream manifests.
            environment["HH_LOG_FILE"] = "/dev/stderr"
        environment.setdefault("HH_CACHE_DIR", "")
        if not environment["HH_CACHE_DIR"] and command in {"test", "run"}:
            environment["HH_CACHE_DIR"] = str(results / "cache")
        if command == "generate":
            environment["HH_SUITE_OUTPUT"] = env.get("HH_SUITE_OUTPUT") or str(results / "generated-tests")
            outputs["suite-path"] = str(Path(environment["HH_SUITE_OUTPUT"]).resolve())
        for key, default in (("HH_REPORT", "scan.md"), ("HH_EXPORT_TOPOLOGICAL_GRAPH", "topology.json")):
            if environment.get(key, "").lower() == "true":
                environment[key] = str(results / default)
        if environment.get("HH_REPORT"):
            stem = Path(environment["HH_REPORT"]).resolve()
            if stem.suffix.lower() in {".md", ".pdf"}:
                stem = stem.with_suffix("")
            outputs["report-path"] = f"{stem}.md"
            outputs["pdf-path"] = f"{stem}.pdf"
            outputs["report-images"] = f"{stem}-*.png"
        if command == "scan" and env.get("HH_EXPORT_MINIMAL_VALUES") == "true":
            environment["HH_REMOTE_MINIMAL_VALUES"] = env.get("HH_MINIMAL_VALUES_FILENAME") or "values-minimal.yaml"
        rerun = env.get("HH_RERUN") or "auto"
        recursive = False
        suite_requested = any(
            environment.get(key)
            for key in (
                "HH_PATHS",
                "HH_WHOLE_CHART",
                "HH_EXHAUSTIVE",
                "HH_MATCH",
                "HH_COLLECT_ONLY",
                "HH_DRY_RUN",
                "HH_DISABLE_SCHEMA_CACHING",
            )
        )
        if command == "test" and not suite_requested:
            from hypothesis_helm.charts.repositories.scan import discover_charts

            local = Path(chart)
            recursive = (
                not (local / "Chart.yaml").is_file()
                or not (local / "values.schema.json").is_file()
                or any(environment.get(key) for key in ("HH_REPORT", "HH_CHART_TIMEOUT", "HH_SCAN_TIMEOUT", "HH_BASE_REF"))
                or environment.get("HH_VALUES", "values.yaml") not in {"", "values.yaml"}
                or len(discover_charts(local)) > 1
            )
        if command in {"test", "run"} and not recursive:
            rerun = select_rerun(
                Path(chart),
                incremental=incremental,
                rerun=rerun,
                base_ref=env.get("HH_BASE_REF") or None,
                report=results / "git-comparison.json",
            )
        if incremental and not recursive:
            # Saved suites consume the resolved comparison here; recursive tests perform it per chart.
            environment.pop("HYPOTHESIS_HELM_BASE_REF", None)
            environment.pop("HH_BASE_REF", None)
        if recursive and shard is not None:
            # Distributed jobs publish JSON/JUnit; the aggregate job owns the final Markdown/PDF.
            for key in ("report-path", "pdf-path", "report-images"):
                outputs.pop(key, None)
        environment["HH_RERUN"] = rerun
        outputs["effective-config-ready"] = "true"
        with captured.open("w") as stream:
            # Give the Helm parent time to stop its own pytest process groups.
            result = Processes(interrupt_grace=10.0).run(
                ["bash", str(Path(__file__).with_suffix(".sh"))],
                cwd=Path.cwd(),
                env=environment,
                stdout=stream,
            )
        status = result.returncode if result.returncode >= 0 else 130
        if security and status != 130:
            if output_format == "yaml":
                # Kubesec's dispatcher consumes JSON Lines. Preserve the selected YAML
                # stream too, and convert one document at a time rather than buffering it.
                converted = results / "manifests.jsonl"
                with manifests.open() as source_stream, converted.open("w") as target_stream:
                    for document in YAML(typ="safe").load_all(source_stream):
                        if document is not None:
                            target_stream.write(json.dumps(document) + "\n")
                manifests = converted
            security_status = scan_with_policy(manifests, root, config, shard, score_minimum)
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

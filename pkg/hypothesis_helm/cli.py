"""
Command-line and Helm plugin entry point.
"""

import argparse
import json
import logging
import os
import shutil
import sys
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from hypothesis_helm.charts.generate import generate_tests
from hypothesis_helm.charts.generated import RenderOptions
from hypothesis_helm.charts.runner import Chart, audit, check_chart
from hypothesis_helm.execution.estimate import estimate_suite
from hypothesis_helm.execution.suite import run_suite
from hypothesis_helm.integrations.sharding import parse_shard_option, resolve_shard
from hypothesis_helm.reporting.budget import parse_time_limit
from hypothesis_helm.reporting.output import MANIFEST_FD
from hypothesis_helm.reporting.progressive import plot_progression
from hypothesis_helm.schemas.conformity import ENVIRONMENT, prepare
from hypothesis_helm.schemas.factors import factor_space
from hypothesis_helm.schemas.finite import NonFiniteSchema
from hypothesis_helm.schemas.groups import parse_group


def parse_jobs(value: str) -> int | Literal["auto"]:
    """
    Parse automatic throughput tuning or a positive fixed worker count.

    Args:
        value (str): Value supplied to the jobs option.

    Returns:
        int | Literal["auto"]: Validated concurrency setting.
    """
    if value == "auto":
        return "auto"
    try:
        count = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("jobs must be auto or a positive integer") from exc
    if count < 1:
        raise argparse.ArgumentTypeError("jobs must be auto or a positive integer")
    return count


def argument_parser(prog: str | None = None) -> argparse.ArgumentParser:
    """
    Build the CLI parser for execution and generated documentation.

    Args:
        prog (str | None): Stable executable name for documentation, or the process default.

    Returns:
        argparse.ArgumentParser: Complete command tree without executing a command.
    """
    parser = argparse.ArgumentParser(
        prog=prog, description="Audit and property-test Helm chart values."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser(
        "generate", help="generate one typed Python property test per values path"
    )
    generate.add_argument("chart", type=Path)
    generate.add_argument("--output", type=Path, default=Path("generated-tests"))
    generate.add_argument("--max-examples", type=int, default=100)
    inspect = commands.add_parser("audit", help="discover value references and schema gaps")
    inspect.add_argument("chart", type=Path)
    inspect.add_argument(
        "--strict", action="store_true", help="fail on any finding or unresolved access"
    )
    run = commands.add_parser("run", help="run a saved generated Python suite")
    run.add_argument("suite", type=Path)
    run.add_argument("--seed", type=int, default=0)
    run.add_argument("--match", help="select tests by value-path keyword")
    run.add_argument("--collect-only", action="store_true")
    run.add_argument("--artifact-dir", type=Path, help="report directory for a saved suite")
    test = commands.add_parser("test", help="select finite coverage or generate per-path tests")
    test.add_argument(
        "chart",
        type=Path,
        nargs="?",
        default=Path("."),
        help="chart directory (defaults to the current directory)",
    )
    test.add_argument("--max-examples", type=int, default=100)
    test.add_argument(
        "--time-limit",
        type=parse_time_limit,
        metavar="DURATION",
        help="whole-chart execution budget, e.g. 30s or 3m (default: 3m); excludes planning",
    )
    modes = test.add_mutually_exclusive_group()
    modes.add_argument("--paths", action="store_true", help="force generated per-path testing")
    modes.add_argument(
        "--exhaustive", action="store_true", help="enumerate finite whole-chart inputs"
    )
    modes.add_argument("--whole-chart", action="store_true", help="sample whole-chart inputs")
    modes.add_argument(
        "--permutations", type=int, metavar="N", help="cover every valid N-way finite interaction"
    )
    test.add_argument(
        "--prune-equivalent",
        action="store_true",
        help="skip Helm only for proved output equivalence to a successful render",
    )
    test.add_argument("--match", help="select generated tests by value-path keyword")
    test.add_argument("--collect-only", action="store_true", help="generate and list tests")
    test.add_argument(
        "--max-cases",
        type=int,
        default=10000,
        help="bound exhaustive domains or permutation suites and factor domains",
    )
    test.add_argument(
        "--max-candidates", type=int, default=100000, help="bound permutation planning work"
    )
    test.add_argument(
        "--exhaustive-threshold",
        type=int,
        default=10000,
        help="enumerate finite spaces smaller than this count; 0 disables promotion",
    )
    test.add_argument(
        "--exhaustive-group",
        type=parse_group,
        action="append",
        default=[],
        metavar="PATH,PATH",
        help="require exhaustive coverage of a group of value paths or containers; repeatable",
    )
    test.add_argument(
        "--no-infer-groups", action="store_true", help="disable inferred exhaustive groups"
    )
    test.add_argument(
        "--max-group-cases",
        type=int,
        default=256,
        help="bound automatically inferred group domains",
    )
    test.add_argument("--seed", type=int, default=0)
    test.add_argument("--timeout", type=float, default=30)
    test.add_argument("--helm", default="helm")
    test.add_argument("--release", default="hypothesis")
    test.add_argument("--namespace", default="default")
    test.add_argument("--kube-version")
    test.add_argument("--allow-empty", action="store_true")
    test.add_argument("--artifact-dir", type=Path, default=Path("reports/hypothesis-helm"))
    schemas = commands.add_parser("schemas", help="prepare the sparse Kubernetes schema cache")
    schemas.add_argument("--schema-version", default="latest")
    schemas.add_argument(
        "--schema-cache-dir", type=Path, default=Path(".cache/hypothesis-helm/schemas")
    )
    schemas.add_argument("--schema-offline", action="store_true")
    schemas.add_argument("--kubeconform-binary", default="kubeconform")
    for command in (test, run):
        command.add_argument(
            "--dry-run",
            action="store_true",
            help="plot coverage and forecast filtering or cached property work without execution",
        )
        command.add_argument(
            "--kubeconform", action="store_true", help="validate Kubernetes API schemas"
        )
        command.add_argument(
            "--schema-version", default="latest", help="Kubernetes schema version: latest or X.Y.Z"
        )
        command.add_argument(
            "--schema-cache-dir", type=Path, default=Path(".cache/hypothesis-helm/schemas")
        )
        command.add_argument(
            "--schema-offline",
            action="store_true",
            help="reuse cached schemas without network access",
        )
        command.add_argument("--kubeconform-binary", default="kubeconform")
        command.add_argument(
            "--cache-dir", type=Path, help="persistent path-result cache directory"
        )
        command.add_argument(
            "--disable-schema-caching",
            action="store_true",
            help="compare values structure against the cached baseline without updating it",
        )
        command.add_argument(
            "--progress",
            action="store_true",
            help="force a live progress bar on stderr, including redirected output",
        )
        command.add_argument("--no-cache", action="store_true", help="disable path-result caching")
        command.add_argument(
            "--rerun",
            choices=("auto", "all", "failed"),
            default="auto",
            help="auto: rerun failures locally; run all paths in CI",
        )
        command.add_argument(
            "--shard",
            type=parse_shard_option,
            default="auto",
            help="auto (default): detect CI node; INDEX/TOTAL: explicit shard; none: disable",
        )
        command.add_argument(
            "--jobs",
            "-j",
            type=parse_jobs,
            default="auto",
            help="auto (default): PID throughput tuning; N: fixed worker count; 1: serial",
        )
        command.add_argument(
            "--output",
            "-o",
            choices=("json",),
            help="stream one rendered manifest per JSON line on stdout; reports go to stderr",
        )
    for command in (generate, test, run):
        command.add_argument(
            "--strict",
            action="store_true",
            help="require all configurable fields in source values.yaml and a clean audit",
        )
    return parser


def main(argv: list[str] | None = None) -> int:
    """
    Dispatch chart auditing, generation, and property checks.

    Args:
        argv (list[str] | None): Command-line arguments, or the process arguments when omitted.

    Returns:
        int: Process exit status, zero on success.
    """
    args = argument_parser().parse_args(argv)
    logger = logging.getLogger("hypothesis_helm")
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    previous_level = logger.level
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    stack = ExitStack()
    descriptor = None
    token = None
    if getattr(args, "output", None) == "json" and not getattr(args, "dry_run", False):
        descriptor = os.dup(sys.stdout.fileno())
        token = MANIFEST_FD.set(descriptor)
        stack.enter_context(redirect_stdout(sys.stderr))
    previous_conformity = os.environ.pop(ENVIRONMENT, None)
    try:
        if args.command == "schemas":
            print(
                prepare(
                    args.schema_cache_dir,
                    args.schema_version,
                    args.kubeconform_binary,
                    args.schema_offline,
                )
            )
            return 0
        if args.command in ("generate", "test", "run") and args.strict:
            source = args.chart if args.command != "run" else None
            if source is None:
                metadata = args.suite / "chart-source.json"
                if not metadata.is_file():
                    raise ValueError(
                        "--strict run requires chart-source.json; regenerate the suite"
                    )
                source = args.suite / json.loads(metadata.read_text())["chart"]
            strict_report = audit(Chart.load(source))
            if strict_report["findings"] or strict_report["unresolved"]:
                print(
                    json.dumps(
                        dict(strict_report, status="failed", reason="strict audit failed"), indent=2
                    )
                )
                return 1
        if args.command in ("test", "run"):
            if args.kubeconform and not args.collect_only and not args.dry_run:
                os.environ[ENVIRONMENT] = prepare(
                    args.schema_cache_dir,
                    args.schema_version,
                    args.kubeconform_binary,
                    args.schema_offline,
                )
            args.shard, shard_source = resolve_shard(args.shard, os.environ)
            if args.shard is not None:
                logger.info(
                    "Shard %s/%s selected from %s",
                    args.shard.index,
                    args.shard.total,
                    shard_source,
                )
        if args.command == "test":
            if args.prune_equivalent:
                if args.paths or args.match is not None or args.collect_only:
                    raise ValueError("--prune-equivalent applies to whole-chart testing only")
                if not args.whole_chart and not args.exhaustive:
                    if args.permutations is None:
                        args.permutations = 2
            if args.exhaustive_threshold < 0 or args.max_group_cases < 1:
                raise ValueError(
                    "exhaustive threshold must be nonnegative and group limit positive"
                )
            if args.exhaustive_group and (args.paths or args.whole_chart or args.exhaustive):
                raise ValueError("--exhaustive-group requires automatic or permutation coverage")
            if not (
                args.paths or args.whole_chart or args.exhaustive or args.permutations is not None
            ):
                if args.exhaustive_group:
                    args.permutations = 2
                elif (
                    args.match is None
                    and not args.collect_only
                    and args.shard is None
                    and args.jobs in ("auto", 1)
                ):
                    try:
                        factor_space(Chart.load(args.chart).schema, args.max_cases)
                    except NonFiniteSchema as exc:
                        logger.info(
                            "Using per-path testing: finite automatic coverage unavailable: %s", exc
                        )
                    else:
                        args.permutations = 2
                        logger.info(
                            "Automatic finite coverage: full enumeration below %d, "
                            "otherwise pairs and groups",
                            args.exhaustive_threshold,
                        )
                else:
                    logger.info(
                        "Using per-path testing for the requested filter, "
                        "collection or parallel controls"
                    )
        if (
            args.command == "test"
            and args.time_limit is not None
            and args.permutations is None
            and not args.whole_chart
            and not args.exhaustive
        ):
            raise ValueError("--time-limit applies to whole-chart testing, not per-path suites")
        if (
            args.command in ("test", "run")
            and args.dry_run
            and getattr(args, "permutations", None) is None
        ):
            if (
                args.collect_only
                or getattr(args, "whole_chart", False)
                or getattr(args, "exhaustive", False)
                or getattr(args, "permutations", None) is not None
            ):
                raise ValueError(
                    "--dry-run applies to per-path suites and cannot combine with --collect-only"
                )
            if args.command == "test" and args.timeout <= 0:
                raise ValueError("timeout must be positive")
            schema_state = None
            if args.kubeconform:
                schema_state = {
                    "status": "unavailable",
                    "requested_version": args.schema_version,
                    "cache_dir": str(args.schema_cache_dir.resolve()),
                    "refresh_required": not args.schema_offline,
                }
                try:
                    if not (args.schema_cache_dir.expanduser() / "repository" / ".git").exists():
                        raise ValueError("schema checkout is not cached")
                    configuration = prepare(
                        args.schema_cache_dir,
                        args.schema_version,
                        args.kubeconform_binary,
                        True,
                        read_only=True,
                    )
                    os.environ[ENVIRONMENT] = configuration
                    schema_state.update(
                        status="cached", resolved_version=json.loads(configuration)["version"]
                    )
                except (ValueError, OSError) as exc:
                    schema_state["reason"] = str(exc)
                if not args.schema_offline:
                    schema_state["note"] = (
                        "Estimate uses cached schemas; an online refresh "
                        "may invalidate prior successes."
                    )
            logical = args.suite if args.command == "run" else args.artifact_dir
            if args.command == "test" and args.shard:
                logical = logical / "shards" / args.shard.name
            logical = logical.resolve()
            with TemporaryDirectory(prefix="hypothesis-helm-plan-") as temporary:
                source = logical
                if args.command == "test":
                    source = Path(temporary)
                    if logical.exists():
                        shutil.copytree(
                            logical,
                            source,
                            dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns(
                                "cache", "__pycache__", ".pytest_cache", ".hypothesis"
                            ),
                        )
                    generate_tests(
                        args.chart,
                        source,
                        max_examples=args.max_examples,
                        suite_location=logical,
                        options=RenderOptions(
                            timeout=args.timeout,
                            helm=args.helm,
                            release=args.release,
                            namespace=args.namespace,
                            kube_version=args.kube_version,
                            allow_empty=args.allow_empty,
                        ),
                    )
                estimate = estimate_suite(
                    source,
                    suite_location=logical,
                    seed=args.seed,
                    match=args.match,
                    jobs=args.jobs,
                    shard=args.shard,
                    artifact_dir=args.artifact_dir,
                    cache_dir=args.cache_dir,
                    cache=not args.no_cache,
                    rerun=args.rerun,
                    schema_state=schema_state,
                )
            plot_progression(estimate)
            print(json.dumps(estimate, indent=2))
            return 0
        if args.command == "run":
            return run_suite(
                args.suite,
                seed=args.seed,
                match=args.match,
                collect_only=args.collect_only,
                jobs=args.jobs,
                shard=args.shard,
                cache_dir=args.cache_dir,
                cache=not args.no_cache,
                disable_schema_caching=args.disable_schema_caching,
                progress=args.progress,
                rerun=args.rerun,
                artifact_dir=args.artifact_dir,
            )
        chart = Chart.load(args.chart)
        if args.command == "generate":
            report = generate_tests(chart, args.output, max_examples=args.max_examples)
            status = 0
        elif args.command == "audit":
            report = audit(chart)
            status = 1 if args.strict and (report["findings"] or report["unresolved"]) else 0
        elif not args.whole_chart and not args.exhaustive and args.permutations is None:
            if args.timeout <= 0:
                raise ValueError("timeout must be positive")
            generated = args.artifact_dir
            if args.shard is not None:
                generated = generated / "shards" / args.shard.name
            report = generate_tests(
                chart,
                generated,
                max_examples=args.max_examples,
                options=RenderOptions(
                    timeout=args.timeout,
                    helm=args.helm,
                    release=args.release,
                    namespace=args.namespace,
                    kube_version=args.kube_version,
                    allow_empty=args.allow_empty,
                ),
            )
            print(f"Generated {report['tests']} value-path tests in {generated}", flush=True)
            diagnostics = report["diagnostics"]
            if diagnostics:
                print("Review paths.json for unresolved or inferred template values.", flush=True)
            return run_suite(
                generated,
                seed=args.seed,
                match=args.match,
                collect_only=args.collect_only,
                jobs=args.jobs,
                shard=args.shard,
                cache_dir=args.cache_dir,
                cache=not args.no_cache,
                disable_schema_caching=args.disable_schema_caching,
                progress=args.progress,
                rerun=args.rerun,
                artifact_dir=args.artifact_dir,
            )
        else:
            if args.shard is not None:
                raise ValueError("--shard applies to per-path suites only")
            if args.jobs not in ("auto", 1):
                raise ValueError("--jobs applies to per-path suites; whole-chart modes are serial")
            if args.match is not None or args.collect_only:
                raise ValueError("--match and --collect-only apply to per-path tests only")
            report = check_chart(
                chart,
                max_examples=args.max_examples,
                random_seed=args.seed,
                timeout=args.timeout,
                helm=args.helm,
                release=args.release,
                namespace=args.namespace,
                kube_version=args.kube_version,
                allow_empty=args.allow_empty,
                artifact_dir=args.artifact_dir,
                exhaustive=args.exhaustive,
                max_cases=args.max_cases,
                permutations=args.permutations,
                max_candidates=args.max_candidates,
                exhaustive_threshold=args.exhaustive_threshold,
                exhaustive_groups=tuple(args.exhaustive_group),
                infer_exhaustive_groups=not args.no_infer_groups,
                max_group_cases=args.max_group_cases,
                dry_run=args.dry_run,
                time_limit=args.time_limit if args.time_limit is not None else 180.0,
                prune_equivalent=args.prune_equivalent,
            )
            status = (
                0
                if report["status"] in ("passed", "dry-run")
                else 124
                if report["status"] == "time-limit"
                else 1
            )
        if getattr(args, "dry_run", False):
            plot_progression(report)
        print(json.dumps(report, indent=2))
        return status
    except KeyboardInterrupt:
        logger.info("Testing interrupted")
        return 130
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc), "type": type(exc).__name__}))
        return 2
    finally:
        os.environ.pop(ENVIRONMENT, None)
        if previous_conformity is not None:
            os.environ[ENVIRONMENT] = previous_conformity
        stack.close()
        if token is not None:
            MANIFEST_FD.reset(token)
        if descriptor is not None:
            os.close(descriptor)
        logger.removeHandler(handler)
        logger.setLevel(previous_level)


if __name__ == "__main__":
    raise SystemExit(main())

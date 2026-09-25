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

from hypothesis_helm.charts.inspection.audit import audit, audit_findings
from hypothesis_helm.charts.model import Chart
from hypothesis_helm.charts.repositories.scan import discover_charts, scan
from hypothesis_helm.charts.suites.generate import generate_tests
from hypothesis_helm.charts.suites.runtime import RenderOptions
from hypothesis_helm.charts.testing.runner import check_chart
from hypothesis_helm.compiler.passes.exports import export_repository
from hypothesis_helm.compiler.passes.graph import export_graph
from hypothesis_helm.compiler.passes.inputs import load_input_chart
from hypothesis_helm.compiler.passes.minimum import export_minimal
from hypothesis_helm.environment import env, refresh_env, set_env
from hypothesis_helm.exceptions.execution import ChartUnavailable
from hypothesis_helm.exceptions.schemas import NonFiniteSchema
from hypothesis_helm.execution.planning import DEFAULT_PERMUTATIONS
from hypothesis_helm.execution.planning.estimate import estimate_suite
from hypothesis_helm.execution.planning.sampling import Sampling
from hypothesis_helm.execution.planning.sensitivity import validate_order
from hypothesis_helm.execution.planning.traversal import STRATEGIES, validate_strategy
from hypothesis_helm.execution.runtime.budget import parse_time_limit
from hypothesis_helm.execution.runtime.signals import Termination
from hypothesis_helm.execution.suite import run_suite
from hypothesis_helm.findings.generator import FindingGenerator
from hypothesis_helm.findings.severity import LEVELS, audit_blocks, log_level
from hypothesis_helm.findings.suppressions import SuppressionCapture
from hypothesis_helm.integrations.sharding import parse_shard_option, resolve_shard
from hypothesis_helm.reporting.console.logs import LogFormatter
from hypothesis_helm.reporting.console.output import MANIFEST_FD, MANIFEST_FORMAT
from hypothesis_helm.reporting.console.summary import print_summary
from hypothesis_helm.reporting.coverage.progressive import plot_progression
from hypothesis_helm.reporting.evidence.changes import replay_file
from hypothesis_helm.reporting.reports.shards import aggregate
from hypothesis_helm.rules import ENVIRONMENT as RULE_ENVIRONMENT
from hypothesis_helm.rules import load_ignored, may_check
from hypothesis_helm.schemas.configuration.policy import ENVIRONMENT as INPUT_ENVIRONMENT
from hypothesis_helm.schemas.configuration.policy import load_policy
from hypothesis_helm.schemas.configuration.selectors import SourceScope, chart_identity, source_identity
from hypothesis_helm.schemas.contracts import mapping, sequence
from hypothesis_helm.schemas.generation.factors import factor_space
from hypothesis_helm.schemas.generation.groups import parse_group
from hypothesis_helm.schemas.kubernetes.conformity import ENVIRONMENT, prepare

__all__ = ("ExamplesAction", "FailAction", "FilterAction", "argument_parser", "local_discovery", "main", "parse_code_list", "parse_jobs")


class FailAction(argparse.Action):
    """
    Keep Boolean fail-fast scheduling while accepting an optional severity threshold.
    """

    def __call__(
        self, parser: argparse.ArgumentParser, namespace: argparse.Namespace, values: object, option_string: str | None = None
    ) -> None:
        """
        Record the explicit CLI threshold separately from the scheduling switch.

        Args:
            parser (argparse.ArgumentParser): Owning command parser.
            namespace (argparse.Namespace): Parsed execution settings.
            values (object): Validated severity, or info for bare --fail.
            option_string (str | None): Original flag spelling.

        Returns:
            None: Fail-fast remains Boolean for existing schedulers.
        """
        namespace.fail = True
        namespace.fail_level = str(values)


class ExamplesAction(argparse.Action):
    """
    Distinguish an explicit CLI example budget from its command-specific default.
    """

    def __call__(
        self, parser: argparse.ArgumentParser, namespace: argparse.Namespace, values: object, option_string: str | None = None
    ) -> None:
        """
        Record the override without changing more specific branch budgets.

        Args:
            parser (argparse.ArgumentParser): Owning command parser.
            namespace (argparse.Namespace): Parsed command settings.
            values (object): Integer budget validated by argparse.
            option_string (str | None): Original option spelling.

        Returns:
            None: The global config can distinguish this value from a fallback.
        """
        setattr(namespace, self.dest, values)
        namespace.max_examples_explicit = True


class FilterAction(argparse.Action):
    """
    Keep the filter preset exclusive with individually composable filtering options.
    """

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: object,
        option_string: str | None = None,
    ) -> None:
        """
        Reject mixed preset and individual options in either argument order.

        Args:
            parser (argparse.ArgumentParser): Parser reporting usage errors.
            namespace (argparse.Namespace): Options parsed so far.
            values (object): Parsed option value.
            option_string (str | None): Spelling supplied by the user.

        Returns:
            None: Store the option after checking preset exclusivity.
        """
        if self.dest in {"filter", "filter_adaptive"}:
            if getattr(namespace, "individual_filter", None):
                parser.error(f"{option_string} cannot be combined with individual filtering options")
            other = "filter_adaptive" if self.dest == "filter" else "filter"
            if getattr(namespace, other, False):
                parser.error("--filter and --filter-adaptive cannot be combined")
        else:
            if getattr(namespace, "filter", False) or getattr(namespace, "filter_adaptive", False):
                parser.error(f"{option_string} cannot be combined with a filter preset")
            namespace.individual_filter = option_string
        setattr(namespace, self.dest, True if self.nargs == 0 else values)


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


def parse_code_list(value: str) -> list[str]:
    """
    Split comma-delimited finding codes, allowing surrounding whitespace.

    Args:
        value (str): Comma-delimited CLI argument.

    Returns:
        list[str]: Nonempty identifiers, validated against the catalog when loading policy.
    """
    codes = [code.strip() for code in value.split(",")]
    if not all(codes):
        raise argparse.ArgumentTypeError("codes must be a comma-delimited list without empty entries, for example HH2006,HH2003")
    return codes


def argument_parser(prog: str | None = None) -> argparse.ArgumentParser:
    """
    Build the CLI parser for execution and generated documentation.

    Args:
        prog (str | None): Stable executable name for documentation, or the process default.

    Returns:
        argparse.ArgumentParser: Complete command tree without executing a command.
    """
    parser = argparse.ArgumentParser(prog=prog, description="Audit and property-test Helm chart values.")
    parser.add_argument(
        "--generate-config", action="store_true", help="print the default .hypothesis-helm.yaml template to stdout and exit"
    )
    commands = parser.add_subparsers(dest="command")
    rules = commands.add_parser(
        "rules",
        help="list classified chart findings and diagnostics",
        description=(
            "List the finding codes used to report chart defects, schema gaps, and testing limitations. "
            "Use these codes to configure which findings to ignore."
        ),
    )
    rules.add_argument("--format", choices=("text", "json", "config", "markdown"), default="text", help="catalog output format")
    replay = commands.add_parser(
        "replay-changes",
        help="verify and replay saved values or manifest changes",
        description=(
            "Reconstruct the overrides, values, or manifests saved with a failing test case. "
            "Verify the baseline and replay the recorded changes to produce JSON."
        ),
    )
    replay.add_argument("record", type=Path, help="changes.json from a failing case")
    replay.add_argument("--section", choices=("overrides", "values", "manifests"), default="overrides")
    replay.add_argument("--baseline", type=Path, help="baseline JSON file; overrides default to an empty map")
    replay.add_argument("--output", type=Path, help="write reconstructed JSON to this file; default: stdout")
    merge = commands.add_parser(
        "aggregate",
        help="verify piped shard reports and write one final report",
        description=(
            "Combine reports from parallel CI shards into one Markdown and PDF report. "
            "Check that the inputs belong to the requested run and account for the expected shards."
        ),
    )
    merge.add_argument("reports", nargs="*", type=Path, help="JSON files or artifact roots; default: stdin")
    merge.add_argument("--shards", type=int, required=True)
    merge.add_argument("--run-id", required=True, help="identifier shared by this run's shards")
    merge.add_argument("--output-dir", type=Path, help="new report directory; default: docs/reports/aggregate")
    exports = commands.add_parser(
        "export-minimal-values",
        help="write example values beside each discovered chart",
        description=(
            "Create an example minimal values file beside each chart found in a local directory. "
            "Also save a verification record describing what was checked and any remaining limitations."
        ),
    )
    exports.add_argument("source", type=Path)
    exports.add_argument("--filename", default="values-minimal.yaml", help="YAML basename only")
    exports.add_argument("--helm", default="helm")
    exports.add_argument("--timeout", type=parse_time_limit, default=30)
    exports.add_argument("--minimal-values-timeout", type=parse_time_limit, default=30)
    exports.add_argument("--files-list", type=Path, help="write NUL-delimited exported YAML and proof paths")
    repository = commands.add_parser(
        "scan",
        help="fetch and test charts from remote Git or Helm repositories",
        description=(
            "Fetch charts from a remote Git repository, Helm repository, or OCI chart reference, then test generated values "
            "and report findings for each chart. Use test for charts already on disk."
        ),
    )
    repository.add_argument(
        "directory", metavar="SOURCE", help="Git URL, Helm repo[/chart], public index.yaml URL, or OCI chart; local paths use test"
    )
    repository.add_argument("--helm-repository", action="store_true", help="interpret SOURCE as a Helm repository name or HTTP(S) base URL")
    repository.add_argument("--chart-version", help="Helm chart version or constraint; default: latest stable release per chart")
    repository.add_argument(
        "--clone-timeout",
        "--source-timeout",
        type=parse_time_limit,
        default=180,
        help="Git checkout or Helm source preparation budget, also bounded by --scan-timeout (default: 3m)",
    )
    repository.add_argument(
        "--report",
        nargs="?",
        const="",
        metavar="PATH",
        help="write Markdown and PDF; default: docs/reports/<dir>_<epoch>_report",
    )
    repository.add_argument("--artifact-dir", type=Path, default=Path(".cache/hypothesis-helm/scans"))
    repository.add_argument("--helm", default="helm")
    repository.add_argument(
        "--values",
        type=Path,
        default=Path("values.yaml"),
        help="baseline file relative to each chart, or an absolute path",
    )
    repository.add_argument(
        "--timeout",
        type=float,
        default=30,
        help="seconds per Helm lint, render, or dependency build",
    )
    repository.add_argument(
        "--chart-timeout",
        "--time-limit",
        dest="chart_timeout",
        type=parse_time_limit,
        default=180,
        help="property-test execution budget per chart (default: 3m)",
    )
    repository.add_argument(
        "--scan-timeout",
        type=parse_time_limit,
        help="scan budget excluding dependency preparation; default: unlimited",
    )
    repository.add_argument("--max-examples", type=int, action=ExamplesAction, default=10)
    repository.add_argument("--cache-dir", type=Path, help="completed chart-result cache; default: .cache/hypothesis-helm/charts")
    repository.add_argument("--no-cache", action="store_true", help="disable completed chart-result caching")
    repository.add_argument("--jobs", "-j", type=parse_jobs, default="auto", help="path workers per chart; auto: available CPUs")
    repository.add_argument(
        "--permutations",
        type=int,
        help="finite interaction strength; non-finite charts fall back to path sampling",
    )
    repository.add_argument(
        "--filter",
        action=FilterAction,
        nargs=0,
        default=False,
        help="filter finite charts with failure expansion; otherwise filter generated inputs before path traversal",
    )
    repository.add_argument(
        "--fail",
        action=FailAction,
        nargs="?",
        const="info",
        default=False,
        choices=tuple(LEVELS),
        help="stop at this severity or higher and exit 1; bare flag: any finding; lower findings remain reported",
    )
    repository.add_argument("--seed", type=int, default=0)
    repository.add_argument(
        "--build-dependencies",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="build locked dependencies in temporary chart copies",
    )
    generate = commands.add_parser(
        "generate",
        help="generate one typed Python property test per values path",
        description=(
            "Create a reusable Python property-test suite for a local chart, with one test per values path. "
            "Input types come from the chart schema or are inferred from its values; execute the saved suite with run."
        ),
    )
    generate.add_argument("chart", type=Path)
    generate.add_argument("--output", type=Path, default=Path("generated-tests"))
    generate.add_argument("--max-examples", type=int, action=ExamplesAction, default=100)
    inspect = commands.add_parser(
        "audit",
        help="discover value references and schema gaps",
        description=(
            "Inspect a local chart's values, schema, and template references to identify missing types, undocumented paths, "
            "and limits on what can be analyzed. Use this to understand the input space before testing."
        ),
    )
    inspect.add_argument("chart", type=Path)
    inspect.add_argument(
        "--fail",
        action=FailAction,
        nargs="?",
        const="info",
        default=False,
        choices=tuple(LEVELS),
        help="fail on audit findings at this severity or higher; bare flag: any finding",
    )
    inspect.add_argument("--artifact-dir", type=Path, default=Path(".cache/hypothesis-helm/audits"), help="audit export directory")
    run = commands.add_parser(
        "run",
        help="run a saved generated Python suite",
        description=(
            "Execute a property-test suite previously created by generate. "
            "Generate values for its selected paths, render the chart, and record any findings."
        ),
    )
    run.add_argument("suite", type=Path)
    run.add_argument("--seed", type=int, default=0)
    run.add_argument("--match", help="select tests by value-path keyword")
    run.add_argument("--collect-only", action="store_true")
    run.add_argument("--artifact-dir", type=Path, help="report directory for a saved suite")
    test = commands.add_parser(
        "test",
        help="discover and test local charts recursively",
        description=(
            "Test a local chart or recursively discover charts in a local directory. "
            "Generate values, render the charts, and report findings with the inputs that triggered them."
        ),
    )
    test.add_argument(
        "chart",
        type=Path,
        nargs="?",
        default=Path("."),
        help="local chart or directory containing charts (default: current directory)",
    )
    test.add_argument(
        "--report", nargs="?", const="", metavar="PATH", help="write combined Markdown/PDF; default: docs/reports/<dir>_<epoch>_report"
    )
    for command in (test, repository):
        command.add_argument(
            "--pca-samples",
            type=int,
            default=64,
            metavar="N",
            help="with --report, measure up to N reference configurations per chart for output PCA; 0 disables it (default: 64)",
        )
        command.add_argument(
            "--pca-timeout",
            type=parse_time_limit,
            default=60,
            help="additional output-PCA measurement budget per chart with --report (default: 1m)",
        )
        command.add_argument(
            "--max-mutations",
            type=int,
            metavar="N",
            help="with --report, measure sensitivity for up to N fields per chart and all their pairs (opt-in)",
        )
        command.add_argument(
            "--sensitivity-timeout",
            type=parse_time_limit,
            default=180,
            help="additional sensitivity measurement budget per chart with --max-mutations (default: 3m)",
        )
    test.add_argument("--values", type=Path, default=Path("values.yaml"), help="baseline file relative to each chart, or an absolute path")
    test.add_argument("--chart-timeout", type=parse_time_limit, help="property-test budget per discovered chart (default: 3m)")
    test.add_argument(
        "--scan-timeout", type=parse_time_limit, help="total local discovery/testing budget, excluding dependency preparation"
    )
    test.add_argument(
        "--build-dependencies", action=argparse.BooleanOptionalAction, default=None, help="build dependencies in isolated copies"
    )
    test.add_argument(
        "--fail",
        action=FailAction,
        nargs="?",
        const="info",
        default=False,
        choices=tuple(LEVELS),
        help="stop at this severity or higher and exit 1; bare flag: any finding; lower findings remain reported",
    )
    test.add_argument("--max-examples", type=int, action=ExamplesAction, default=10)
    test.add_argument(
        "--time-limit",
        type=parse_time_limit,
        metavar="DURATION",
        help="whole-chart execution budget, e.g. 30s or 3m (default: 3m); excludes planning",
    )
    modes = test.add_mutually_exclusive_group()
    modes.add_argument("--paths", action="store_true", help="force generated per-path testing")
    modes.add_argument("--exhaustive", action="store_true", help="enumerate finite whole-chart inputs")
    modes.add_argument("--whole-chart", action="store_true", help="sample whole-chart inputs")
    modes.add_argument(
        "--permutations", type=int, metavar="N", help="cover valid N-way finite interactions; non-finite charts fall back to path sampling"
    )
    filters = test.add_argument_group(
        "filtering",
        "Use --filter or the individual methods below; random filtering is independent.",
    )
    filters.add_argument(
        "--filter",
        action=FilterAction,
        nargs=0,
        default=False,
        help="enable --filter-topology 2 and --expand-failures",
    )
    test.add_argument(
        "--filter-random",
        dest="trim",
        type=int,
        default=0,
        metavar="N",
        help="retain a seeded quarter of finite permutation cases per step; default: 0",
    )
    filters.add_argument(
        "--filter-topology",
        dest="trim_topology",
        action=FilterAction,
        type=int,
        default=0,
        metavar="N",
        help="thin symbolic output/branch regions; retain representatives and unknowns; combines with --filter-random",
    )
    filters.add_argument(
        "--expand-failures",
        action=FilterAction,
        nargs=0,
        default=False,
        help="test omitted members of failed symbolic regions within the execution budget",
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
    test.add_argument("--max-candidates", type=int, default=100000, help="bound permutation planning work")
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
    test.add_argument("--no-infer-groups", action="store_true", help="disable inferred exhaustive groups")
    test.add_argument(
        "--max-group-cases",
        type=int,
        default=256,
        help="bound automatically inferred group domains",
    )
    test.add_argument("--seed", type=int, default=0)
    for target in (test, repository):
        target.add_argument(
            "--filter-adaptive",
            action=FilterAction,
            nargs=0,
            default=False,
            help="enable --filter and retain 70%% subject to measured topology sample floors; unmatched charts keep all filtered cases",
        )
        target.add_argument("--sampling-calibration", type=Path, help="override the packaged adaptive-sampling calibration JSON")
        target.add_argument(
            "--sensitivity-order",
            type=int,
            metavar="N",
            help="maximum measured interaction order for sensitivity-first; 1..permutations, default: min(2, permutations)",
        )
    for testing in (run, test, repository):
        testing.add_argument(
            "--sample-random",
            type=float,
            default=100,
            metavar="PERCENT",
            help="retain this percentage after filtering; default: 100 (disabled); recall depends on selected inputs",
        )
        testing.add_argument(
            "--sample-min-cases",
            type=int,
            default=128,
            metavar="N",
            help="retain at least N eligible cases, or all when fewer exist (default: 128)",
        )
        testing.add_argument(
            "--traversal-strategy",
            type=validate_strategy,
            choices=STRATEGIES,
            default="random",
            help="seeded random (default), linear, root-first, leaf-first, or sensitivity-first (finite coverage defaults to pairs)",
        )
    test.add_argument("--timeout", type=float, default=30)
    test.add_argument("--helm", default="helm")
    test.add_argument("--release", default="hypothesis")
    test.add_argument("--namespace", default="default")
    test.add_argument("--kube-version")
    test.add_argument("--allow-empty", action="store_true")
    test.add_argument("--artifact-dir", type=Path, default=Path(".cache/hypothesis-helm/runs"))
    schemas = commands.add_parser(
        "schemas",
        help="prepare the sparse Kubernetes schema cache",
        description=(
            "Prepare a local cache of Kubernetes API schemas for built-in manifest validation. "
            "Select a Kubernetes version to download, or use --schema-offline to reuse schemas already cached."
        ),
    )
    schemas.add_argument("--schema-version", default="latest")
    schemas.add_argument("--schema-cache-dir", type=Path, default=Path("schemas"))
    schemas.add_argument("--schema-offline", action="store_true")
    for command in (test, repository, run, generate):
        command.add_argument(
            "--strict",
            action=argparse.BooleanOptionalAction,
            default=None,
            help="require schemas for custom resources; otherwise skip schema validation when their schema is missing",
        )
    for command in (test, repository, run, exports):
        command.add_argument(
            "--validate-schemas", action="store_true", help="validate rendered resources against the local Kubernetes schema cache"
        )
        command.add_argument("--schema-version", default="latest", help="Kubernetes schema version: latest or X.Y.Z")
        command.add_argument("--schema-cache-dir", type=Path, default=Path("schemas"))
        command.add_argument(
            "--schema-offline",
            action="store_true",
            help="reuse cached schemas without network access",
        )
    for command in (test, repository):
        command.add_argument("--base-ref", help="Git comparison ref for repository tests; overrides CI target or previous trunk commit")
    for command in (test, run):
        command.add_argument(
            "--dry-run",
            action="store_true",
            help="plot coverage and forecast filtering or cached property work without execution",
        )
        command.add_argument("--cache-dir", type=Path, help="persistent path-result cache directory")
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
        command.add_argument("--run-id", help="common identifier for shards merged into one report")
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
            help="workers per chart; auto: CPU count for repository/exhaustive tests, PID tuning for suites; 1: serial",
        )
    for command in (test, run, repository):
        command.add_argument(
            "--output-format",
            "-o",
            choices=("json", "yaml"),
            help="stream rendered manifests as JSON lines or YAML documents on stdout; logs and reports go to stderr",
        )
    for command in (test, run, repository, inspect):
        command.add_argument(
            "--export-suppressions",
            action="store_true",
            help="write categorized suppressions.yaml in each chart's artifacts after testing; review before applying",
        )
    for command in (generate, run):
        command.add_argument(
            "--fail",
            action=FailAction,
            nargs="?",
            const="info",
            default=False,
            choices=tuple(LEVELS),
            help="stop at this severity or higher and exit 1; bare flag: any finding; lower findings remain reported",
        )
    for command in (repository, inspect, generate, test):
        command.add_argument(
            "--export-topological-graph",
            nargs="?",
            const="",
            metavar="FILENAME",
            help="export input references, control flow and observed manifests as JSON and DOT",
        )
        command.add_argument(
            "--minimal-values-timeout",
            type=parse_time_limit,
            default=30,
            help="verification and minimization budget for values export (default: 30s)",
        )
        command.add_argument(
            "--export-minimal-values",
            nargs="?",
            const="",
            metavar="FILENAME",
            help="export example values with validation status and missing fields; default: "
            "values-minimal-<checksum>-<epoch>.yaml (scan: separate files per chart)",
        )
    for command in (repository, inspect, generate, test, run):
        command.add_argument(
            "--log-color",
            nargs="?",
            const="always",
            default="never",
            choices=("auto", "always", "never"),
            help="color log severity labels; bare flag: always; auto: terminals unless NO_COLOR is set; default: never",
        )
        command.add_argument(
            "--log-file", default="-", metavar="PATH", help="append logs to PATH; default: stdout (-), or stderr when streaming manifests"
        )
        command.add_argument(
            "--config", type=Path, help="finding and input-domain policy YAML; default: .hypothesis-helm.yaml in the working directory"
        )
        command.add_argument(
            "--character-sets", choices=("ascii", "unicode"), help="generated text alphabet; overrides config; default: ascii"
        )
        command.add_argument(
            "--renderer-policy",
            choices=("auto", "native", "strict"),
            help="auto controls supported random inputs with visible native fallback (default); native uses Helm; strict requires replay",
        )
        command.add_argument(
            "--yaml-parser",
            choices=("ruamel", "ruamel-safe", "pyyaml"),
            help="manifest parser backend; overrides yaml_parser in config; default: ruamel, or the saved suite's parser",
        )
        command.add_argument(
            "--ignore", action="append", default=[], metavar="CODE", help="disable one built-in check; repeat to add codes"
        )
        command.add_argument(
            "--disable-codes",
            dest="ignore",
            action="extend",
            type=parse_code_list,
            metavar="CODE[,CODE...]",
            help="disable comma-delimited finding codes; adds to --ignore and the config file; repeatable",
        )
    return parser


def local_discovery(args: argparse.Namespace) -> bool:
    """
    Select recursive local execution while retaining single-chart suite controls.

    Args:
        args (argparse.Namespace): Local test options with resolved shard coordinates.

    Returns:
        bool: Whether repository discovery should handle this invocation.
    """
    args.chart = args.chart.expanduser()
    if not args.chart.is_dir():
        raise ValueError("test requires a local directory; use scan for remote Git or Helm sources")
    unsupported = {
        "--paths": args.paths,
        "--whole-chart": args.whole_chart,
        "--exhaustive": args.exhaustive,
        "--match": args.match is not None,
        "--collect-only": args.collect_only,
        "--dry-run": args.dry_run,
        "--shard": args.shard is not None,
        "--disable-schema-caching": args.disable_schema_caching,
        "--rerun": args.rerun != "auto",
        "--run-id": args.run_id is not None,
    }
    recursive = (
        not (args.chart / "Chart.yaml").is_file()
        or not (args.chart / "values.schema.json").is_file()
        or args.report is not None
        or args.values != Path("values.yaml")
        or args.chart_timeout is not None
        or args.scan_timeout is not None
        or args.build_dependencies is not None
        or (args.fail and not any(unsupported.values()))
        or args.base_ref is not None
        or bool(env.get("HYPOTHESIS_HELM_BASE_REF"))
        or (not any(unsupported.values()) and len(discover_charts(args.chart)) > 1)
    )
    finite_requested = args.filter or args.permutations is not None or args.traversal_strategy == "sensitivity-first"
    if finite_requested and not recursive and not any(unsupported.values()):
        try:
            factor_space(Chart.load(args.chart).generation_schema(), args.max_cases)
        except NonFiniteSchema:
            recursive = True
    if not recursive:
        return False
    incompatible = [name for name, enabled in unsupported.items() if enabled]
    if incompatible:
        raise ValueError(f"{', '.join(incompatible)} require single-chart suite execution; run test on an individual schema-backed chart")
    if args.chart_timeout is not None and args.time_limit is not None:
        raise ValueError("use either --chart-timeout or --time-limit for recursive testing")
    args.directory = str(args.chart)
    args.chart_timeout = args.chart_timeout or args.time_limit or 180.0
    args.build_dependencies = True if args.build_dependencies is None else args.build_dependencies
    args.clone_timeout = 180.0
    args.chart_version = None
    args.helm_repository = False
    return True


def main(argv: list[str] | None = None) -> int:
    """
    Dispatch chart auditing, generation, and property checks.

    Args:
        argv (list[str] | None): Command-line arguments, or the process arguments when omitted.

    Returns:
        int: Process exit status, zero on success.
    """
    refresh_env()
    parser = argument_parser()
    invocation = list(sys.argv[1:] if argv is None else argv)
    arguments = invocation.copy()
    for index, argument in enumerate(arguments):
        if argument == "--":
            break
        if argument == "--fail" and (index + 1 == len(arguments) or arguments[index + 1] not in LEVELS):
            arguments[index] = "--fail=info"
    args = parser.parse_args(arguments)
    args.invocation = invocation
    if getattr(args, "pca_samples", 0) < 0:
        parser.error("--pca-samples must be nonnegative")
    if getattr(args, "max_mutations", None) is not None:
        if args.max_mutations < 1:
            parser.error("--max-mutations must be positive")
        if args.report is None:
            parser.error("--max-mutations requires --report")
    if args.generate_config:
        if args.command is not None:
            parser.error("--generate-config cannot be combined with a command")
        print(FindingGenerator.render("config"), end="")
        return 0
    if args.command is None:
        parser.error("a command is required unless --generate-config is used")
    if getattr(args, "export_suppressions", False) and (getattr(args, "dry_run", False) or getattr(args, "collect_only", False)):
        parser.error("--export-suppressions requires chart execution or an audit, not --dry-run or --collect-only")
    if hasattr(args, "traversal_strategy"):
        try:
            if args.traversal_strategy == "sensitivity-first" and (
                args.command == "run" or any(getattr(args, mode, False) for mode in ("paths", "whole_chart", "exhaustive"))
            ):
                raise ValueError(
                    "sensitivity-first requires finite permutation testing, not saved suites, --paths, --whole-chart or --exhaustive"
                )
            validate_order(args.traversal_strategy, getattr(args, "sensitivity_order", None), getattr(args, "permutations", None))
        except ValueError as error:
            parser.error(str(error))
    if getattr(args, "sampling_calibration", None) is not None and not args.filter_adaptive:
        parser.error("--sampling-calibration requires --filter-adaptive")
    if getattr(args, "filter_adaptive", False):
        if args.sample_random != 100 or args.sample_min_cases != 128:
            parser.error("--filter-adaptive determines the percentage and sample floor; omit manual sampling options")
        args.filter = True
    if hasattr(args, "sample_random"):
        Sampling(
            args.sample_random,
            args.sample_min_cases,
            getattr(args, "filter_adaptive", False),
            str(args.sampling_calibration) if getattr(args, "sampling_calibration", None) else None,
        )
    logger = logging.getLogger("hypothesis_helm")
    handler: logging.Handler | None = None
    previous_level = logger.level
    logger.setLevel(logging.INFO)
    stack = ExitStack()
    stack.enter_context(Termination())
    descriptor = None
    token = None
    format_token = None
    previous_rules = env.get(RULE_ENVIRONMENT)
    previous_inputs = set_env(INPUT_ENVIRONMENT, None)
    previous_conformity = set_env(ENVIRONMENT, None)
    try:
        streaming = getattr(args, "output_format", None) in ("json", "yaml") and not getattr(args, "dry_run", False)
        if streaming:
            descriptor = os.dup(sys.stdout.fileno())
            token = MANIFEST_FD.set(descriptor)
            format_token = MANIFEST_FORMAT.set(args.output_format)
            stack.enter_context(redirect_stdout(sys.stderr))
        destination = getattr(args, "log_file", "-")
        if destination == "-":
            handler = logging.StreamHandler(sys.stdout)
        elif destination in ("/dev/stderr", "/dev/stdout"):
            handler = logging.StreamHandler(sys.stderr if destination == "/dev/stderr" else sys.stdout)
        else:
            path = Path(destination).expanduser()
            path.parent.mkdir(parents=True, exist_ok=True)
            handler = logging.FileHandler(path, encoding="utf-8")
        color_mode = getattr(args, "log_color", "never")
        stream = getattr(handler, "stream", None)
        color = color_mode == "always" or (color_mode == "auto" and "NO_COLOR" not in env and stream is not None and stream.isatty())
        handler.setFormatter(LogFormatter(color=color))
        logger.addHandler(handler)
        if args.command == "rules":
            print(FindingGenerator.render(args.format), end="")
            return 0
        if hasattr(args, "ignore"):
            args.input_policy = load_policy(
                args.config,
                character_sets=args.character_sets,
                yaml_parser=args.yaml_parser,
                strict=getattr(args, "strict", None),
                max_examples=args.max_examples if getattr(args, "max_examples_explicit", False) else None,
            )
            if args.renderer_policy is not None:
                args.input_policy["hypothesis"] = {
                    **mapping(args.input_policy.get("hypothesis", {})),
                    "renderer_policy": args.renderer_policy,
                }
            if hasattr(args, "max_examples"):
                args.max_examples = int(str(mapping(args.input_policy.get("hypothesis", {})).get("max_examples", args.max_examples)))
            finding_policy = mapping(args.input_policy["findings"])
            if hasattr(args, "fail"):
                if args.fail:
                    finding_policy["fail_on"] = args.fail_level
                args.fail = finding_policy.get("fail_on") is not None or any(
                    mapping(mapping(rule).get("findings", {})).get("fail_on") is not None
                    for rule in sequence(args.input_policy.get("input_constraints", []))
                )
            set_env(INPUT_ENVIRONMENT, json.dumps(args.input_policy, sort_keys=True))
            args.ignored_rules = load_ignored(args.config, args.ignore)
            set_env(RULE_ENVIRONMENT, json.dumps(args.ignored_rules))
            if args.ignored_rules:
                logger.info("Disabled checks: %s", ", ".join(args.ignored_rules))
        else:
            set_env(RULE_ENVIRONMENT, None)
        if args.command == "replay-changes":
            replay_file(args.record, args.baseline, args.section, args.output)
            return 0
        if args.command == "aggregate":
            return aggregate(args.reports, args.shards, args.run_id, args.output_dir)
        if args.command == "export-minimal-values":
            if args.validate_schemas and may_check("HH1108"):
                set_env(ENVIRONMENT, prepare(args.schema_cache_dir, args.schema_version, args.schema_offline))
            return export_repository(
                args.source,
                args.filename,
                helm=args.helm,
                timeout=args.timeout,
                budget=args.minimal_values_timeout,
                files_list=args.files_list,
            )
        if args.command == "scan":
            if args.validate_schemas and may_check("HH1108"):
                set_env(ENVIRONMENT, prepare(args.schema_cache_dir, args.schema_version, args.schema_offline))
            return scan(args)
        if args.command == "test":
            selector = args.shard
            args.shard, _ = resolve_shard(args.shard, env)
            if local_discovery(args):
                if args.validate_schemas and may_check("HH1108"):
                    set_env(ENVIRONMENT, prepare(args.schema_cache_dir, args.schema_version, args.schema_offline))
                return scan(args)
            args.shard = selector
        minimal_values = None
        if args.command == "schemas":
            print(
                prepare(
                    args.schema_cache_dir,
                    args.schema_version,
                    args.schema_offline,
                )
            )
            return 0
        if args.command == "run":
            source_record = args.suite / "chart-source.json"
            if source_record.is_file():
                source_document = mapping(json.loads(source_record.read_text()))
                if "source" in source_document:
                    stack.enter_context(SourceScope(str(source_document["source"])))
        finding_report = None
        if args.command in ("generate", "test", "run") and args.fail:
            source = args.chart if args.command != "run" else None
            if source is None:
                metadata = args.suite / "chart-source.json"
                if not metadata.is_file():
                    raise ValueError("--fail run requires chart-source.json; regenerate the suite")
                source = args.suite / json.loads(metadata.read_text())["chart"]
            finding_report = audit_findings(Chart.load(source))
            for item in [*sequence(finding_report.get("findings", [])), *sequence(finding_report.get("unresolved", []))]:
                finding = mapping(item)
                logger.log(
                    log_level(str(finding["severity"])),
                    "[%s] Audit finding: %s; path=%s; severity=%s",
                    finding["code"],
                    finding.get("message", finding.get("issue", "Unresolved value access")),
                    finding.get("path", []),
                    finding["severity"],
                )
            if audit_blocks(finding_report):
                if getattr(args, "export_suppressions", False):
                    destination = args.artifact_dir or args.suite
                    selector, _ = resolve_shard(args.shard, env)
                    if selector is not None:
                        destination = destination / "shards" / selector.name
                    SuppressionCapture(destination, enabled=True).write(
                        finding_report, name=chart_identity(source), source=source_identity(source)
                    )
                failure = dict(finding_report, status="failed", reason="input audit findings (--fail)")
                if args.command == "test" and not args.dry_run:
                    args.artifact_dir.mkdir(parents=True, exist_ok=True)
                    artifact = args.artifact_dir / "audit.json"
                    artifact.write_text(json.dumps(failure, indent=2) + "\n")
                    print_summary(failure, artifact)
                else:
                    print(json.dumps(failure, indent=2))
                return 1
        if args.command in ("test", "run"):
            if args.validate_schemas and may_check("HH1108") and not args.collect_only and not args.dry_run:
                set_env(
                    ENVIRONMENT,
                    prepare(
                        args.schema_cache_dir,
                        args.schema_version,
                        args.schema_offline,
                    ),
                )
            args.shard, shard_source = resolve_shard(args.shard, env)
            if args.shard is not None:
                logger.info(
                    "Shard %s/%s selected from %s",
                    args.shard.index,
                    args.shard.total,
                    shard_source,
                )
        if args.command in ("audit", "generate", "test") and args.export_minimal_values is not None:
            original = load_input_chart(args.chart)
            minimal_values = export_minimal(
                original,
                Path(args.export_minimal_values) if args.export_minimal_values else None,
                helm=getattr(args, "helm", "helm"),
                timeout=getattr(args, "timeout", 30),
                budget=args.minimal_values_timeout,
            )
            logger.info("Minimal input baseline: %s", minimal_values["yaml"])
        topological_graph = None
        if args.command in ("audit", "generate", "test") and args.export_topological_graph is not None:
            topological_graph = export_graph(
                load_input_chart(args.chart),
                Path(args.export_topological_graph) if args.export_topological_graph else None,
                helm=getattr(args, "helm", "helm"),
                timeout=getattr(args, "timeout", 30),
            )
        if args.command == "test":
            # Recursive scans resolve automatic coverage per chart. This branch handles a single finite chart.
            if args.traversal_strategy == "sensitivity-first" and args.permutations is None:
                args.permutations = DEFAULT_PERMUTATIONS
            if args.filter:
                args.trim_topology = 2
                args.expand_failures = True
            if args.trim < 0 or args.trim_topology < 0:
                raise ValueError("--filter-random and --filter-topology must be nonnegative")
            if args.expand_failures and (args.paths or args.whole_chart or args.exhaustive or args.match is not None or args.collect_only):
                raise ValueError("--expand-failures requires finite permutation testing")
            if args.trim or args.trim_topology or args.expand_failures:
                if args.paths or args.whole_chart or args.exhaustive:
                    raise ValueError("--filter-random and --filter-topology apply to finite --permutations planning only")
                if args.permutations is None:
                    args.permutations = DEFAULT_PERMUTATIONS
            if args.prune_equivalent:
                if args.paths or args.match is not None or args.collect_only:
                    raise ValueError("--prune-equivalent applies to whole-chart testing only")
                if not args.whole_chart and not args.exhaustive:
                    if args.permutations is None:
                        args.permutations = DEFAULT_PERMUTATIONS
            if args.exhaustive_threshold < 0 or args.max_group_cases < 1:
                raise ValueError("exhaustive threshold must be nonnegative and group limit positive")
            if args.exhaustive_group and (args.paths or args.whole_chart or args.exhaustive):
                raise ValueError("--exhaustive-group requires automatic or permutation coverage")
            if not (args.paths or args.whole_chart or args.exhaustive or args.permutations is not None):
                if args.exhaustive_group:
                    args.permutations = DEFAULT_PERMUTATIONS
                elif args.match is None and not args.collect_only and args.shard is None and args.jobs in ("auto", 1):
                    try:
                        factor_space(Chart.load(args.chart).generation_schema(), args.max_cases)
                    except NonFiniteSchema as exc:
                        logger.info("Using per-path testing: finite automatic coverage unavailable: %s", exc)
                    else:
                        args.permutations = DEFAULT_PERMUTATIONS
                        logger.info(
                            "Automatic finite coverage: full enumeration below %d, otherwise pairs and groups",
                            args.exhaustive_threshold,
                        )
                else:
                    logger.info("Using per-path testing for the requested filter, collection or parallel controls")
        if (
            args.command == "test"
            and args.time_limit is not None
            and args.permutations is None
            and not args.whole_chart
            and not args.exhaustive
        ):
            raise ValueError("--time-limit applies to whole-chart testing, not per-path suites")
        if args.command in ("test", "run") and args.dry_run and getattr(args, "permutations", None) is None:
            if (
                args.collect_only
                or getattr(args, "whole_chart", False)
                or getattr(args, "exhaustive", False)
                or getattr(args, "permutations", None) is not None
            ):
                raise ValueError("--dry-run applies to per-path suites and cannot combine with --collect-only")
            if args.command == "test" and args.timeout <= 0:
                raise ValueError("timeout must be positive")
            schema_state = None
            if args.validate_schemas and may_check("HH1108"):
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
                        True,
                        read_only=True,
                    )
                    set_env(ENVIRONMENT, configuration)
                    schema_state.update(status="cached", resolved_version=json.loads(configuration)["version"])
                except (ValueError, OSError) as exc:
                    schema_state["reason"] = str(exc)
                if not args.schema_offline:
                    schema_state["note"] = "Estimate uses cached schemas; an online refresh may invalidate prior successes."
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
                            ignore=shutil.ignore_patterns("cache", "__pycache__", ".pytest_cache", ".hypothesis"),
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
                    traversal_strategy=args.traversal_strategy,
                    sampling=Sampling(
                        args.sample_random,
                        args.sample_min_cases,
                        getattr(args, "filter_adaptive", False),
                        str(args.sampling_calibration) if getattr(args, "sampling_calibration", None) else None,
                    ),
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
                traversal_strategy=args.traversal_strategy,
                sampling=Sampling(
                    args.sample_random,
                    args.sample_min_cases,
                    getattr(args, "filter_adaptive", False),
                    str(args.sampling_calibration) if getattr(args, "sampling_calibration", None) else None,
                ),
                match=args.match,
                collect_only=args.collect_only,
                fail_fast=args.fail,
                jobs=args.jobs,
                shard=args.shard,
                cache_dir=args.cache_dir,
                cache=not args.no_cache,
                disable_schema_caching=args.disable_schema_caching,
                run_id=args.run_id,
                progress=args.progress,
                rerun=args.rerun,
                artifact_dir=args.artifact_dir,
                export_suppressions=args.export_suppressions,
                audit_report=finding_report,
            )
        chart = load_input_chart(args.chart) if args.command == "audit" else Chart.load(args.chart)
        capture = stack.enter_context(
            SuppressionCapture(
                getattr(args, "artifact_dir", None) or Path(".cache/hypothesis-helm/audits"),
                enabled=getattr(args, "export_suppressions", False)
                and (args.command == "audit" or args.whole_chart or args.exhaustive or args.permutations is not None),
            )
        )
        if args.command == "generate":
            report = generate_tests(chart, args.output, max_examples=args.max_examples)
            status = 0
        elif args.command == "audit":
            report = audit_findings(chart) if args.fail else audit(chart)
            if args.fail and not audit_blocks(report):
                report = audit(chart)
            status = 1 if args.fail and audit_blocks(report) else 0
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
                traversal_strategy=args.traversal_strategy,
                sampling=Sampling(
                    args.sample_random,
                    args.sample_min_cases,
                    getattr(args, "filter_adaptive", False),
                    str(args.sampling_calibration) if getattr(args, "sampling_calibration", None) else None,
                ),
                match=args.match,
                collect_only=args.collect_only,
                fail_fast=args.fail,
                jobs=args.jobs,
                shard=args.shard,
                cache_dir=args.cache_dir,
                cache=not args.no_cache,
                disable_schema_caching=args.disable_schema_caching,
                run_id=args.run_id,
                progress=args.progress,
                rerun=args.rerun,
                artifact_dir=args.artifact_dir,
                export_suppressions=args.export_suppressions,
                audit_report=finding_report,
            )
        else:
            if args.shard is not None:
                raise ValueError("--shard applies to per-path suites only")
            if not args.exhaustive and args.jobs not in ("auto", 1):
                raise ValueError("--jobs applies to per-path suites and exhaustive testing; other whole-chart modes are serial")
            if args.match is not None or args.collect_only:
                raise ValueError("--match and --collect-only apply to per-path tests only")
            report = check_chart(
                chart,
                max_examples=args.max_examples,
                random_seed=args.seed,
                traversal_strategy=args.traversal_strategy,
                sampling=Sampling(
                    args.sample_random,
                    args.sample_min_cases,
                    getattr(args, "filter_adaptive", False),
                    str(args.sampling_calibration) if getattr(args, "sampling_calibration", None) else None,
                ),
                timeout=args.timeout,
                helm=args.helm,
                release=args.release,
                namespace=args.namespace,
                kube_version=args.kube_version,
                allow_empty=args.allow_empty,
                artifact_dir=args.artifact_dir,
                exhaustive=args.exhaustive,
                jobs=((os.process_cpu_count() or 1) if args.jobs == "auto" else args.jobs) if args.exhaustive else 1,
                max_cases=args.max_cases,
                permutations=args.permutations,
                sensitivity_order=args.sensitivity_order,
                trim=args.trim,
                trim_topology=args.trim_topology,
                expand_failures=args.expand_failures,
                max_candidates=args.max_candidates,
                exhaustive_threshold=args.exhaustive_threshold,
                exhaustive_groups=tuple(args.exhaustive_group),
                infer_exhaustive_groups=not args.no_infer_groups,
                max_group_cases=args.max_group_cases,
                dry_run=args.dry_run,
                time_limit=args.time_limit if args.time_limit is not None else 180.0,
                prune_equivalent=args.prune_equivalent,
                filter_rejections=args.filter,
                fail_fast=args.fail,
            )
            from hypothesis_helm.charts.testing.coverage import require_attempts

            require_attempts(report)
            status = (
                0
                if report["status"] in ("passed", "dry-run", "ignored", "findings")
                else 130
                if report["status"] == "interrupted"
                else 124
                if report["status"] == "time-limit"
                else 1
            )
        if finding_report is not None:
            report["audit"] = finding_report
            if getattr(args, "artifact_dir", None) is not None:
                args.artifact_dir.mkdir(parents=True, exist_ok=True)
                (args.artifact_dir / "audit.json").write_text(json.dumps(finding_report, indent=2) + "\n")
        if getattr(args, "dry_run", False):
            plot_progression(report)
        if minimal_values is not None:
            report["minimal_values"] = minimal_values
        if topological_graph is not None:
            report["topological_graph"] = topological_graph
        if capture.enabled and not getattr(args, "dry_run", False):
            capture.write(report, name=chart_identity(chart.path), source=source_identity(chart.path), defaults=chart.defaults)
        if args.command == "test" and not args.dry_run:
            artifact = args.artifact_dir / "report.json"
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_text(json.dumps(report, indent=2) + "\n")
            print_summary(report, artifact)
        else:
            print(json.dumps(report, indent=2))
        return status
    except KeyboardInterrupt:
        logger.info("Testing interrupted")
        return 130
    except (Exception, ChartUnavailable) as exc:
        print(json.dumps({"status": "error", "error": str(exc), "type": type(exc).__name__}))
        return 2
    finally:
        set_env(RULE_ENVIRONMENT, None)
        set_env(INPUT_ENVIRONMENT, None)
        if previous_inputs is not None:
            set_env(INPUT_ENVIRONMENT, previous_inputs)
        if previous_rules is not None:
            set_env(RULE_ENVIRONMENT, previous_rules)
        set_env(ENVIRONMENT, None)
        if previous_conformity is not None:
            set_env(ENVIRONMENT, previous_conformity)
        stack.close()
        if token is not None:
            MANIFEST_FD.reset(token)
        if format_token is not None:
            MANIFEST_FORMAT.reset(format_token)
        if descriptor is not None:
            os.close(descriptor)
        if handler is not None:
            logger.removeHandler(handler)
            handler.close()
        logger.setLevel(previous_level)


if __name__ == "__main__":
    raise SystemExit(main())

"""
Discover and exercise independent charts in a repository tree.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
from collections import Counter
from contextlib import ExitStack
from pathlib import Path

from hypothesis_helm.charts import yamlio
from hypothesis_helm.charts.audit import audit
from hypothesis_helm.charts.cache import ChartCache
from hypothesis_helm.charts.changes import comparison
from hypothesis_helm.charts.model import Chart
from hypothesis_helm.charts.paths import check_paths
from hypothesis_helm.charts.registry import prepare_helm_source
from hypothesis_helm.charts.repository import RepositorySource, remote_name
from hypothesis_helm.charts.runner import check_chart
from hypothesis_helm.compiler.passes.graph import export_graph
from hypothesis_helm.compiler.passes.inputs import load_input_chart
from hypothesis_helm.compiler.passes.minimum import export_minimal
from hypothesis_helm.execution.processes import Processes
from hypothesis_helm.execution.sampling import Sampling
from hypothesis_helm.reporting.budget import TimeLimitReached, execution_timer
from hypothesis_helm.reporting.errors import chart_errors, deduplicate_errors
from hypothesis_helm.reporting.repository import write_reports
from hypothesis_helm.rules import ignored, ignored_codes, record_ignored
from hypothesis_helm.schemas.contracts import mapping
from hypothesis_helm.schemas.factors import factor_space
from hypothesis_helm.schemas.finite import NonFiniteSchema

LOGGER = logging.getLogger(__name__)
VERSION = re.compile(r"^v?(0|[1-9]\d*)(?:\.(0|[1-9]\d*))?(?:\.(0|[1-9]\d*))?(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")


def discover_charts(root: Path, *, deadline: float | None = None) -> list[dict[str, object]]:
    """
    Discover metadata files without following directory symlinks.

    Args:
        root (Path): Repository or chart directory to inspect recursively.
        deadline (float | None): Optional monotonic scan deadline, preserving partial discovery.

    Returns:
        list[dict[str, object]]: Deterministically ordered valid and invalid candidates.
    """
    if not root.is_dir():
        raise ValueError(f"Not a directory: {root}")
    results: list[dict[str, object]] = []
    try:
        with ExitStack() as scope:
            if deadline is not None:
                scope.enter_context(execution_timer(max(0.000001, deadline - time.monotonic())))
            for directory, children, files in os.walk(root, followlinks=False):
                if deadline is not None and time.monotonic() >= deadline:
                    break
                children[:] = sorted(name for name in children if name not in {".git", ".venv", ".cache", "__pycache__"})
                if "Chart.yaml" not in files:
                    continue
                path = Path(directory)
                record: dict[str, object] = {
                    "chart": str(path.relative_to(root)),
                    "status": "pending",
                }
                try:
                    metadata = yamlio.load((path / "Chart.yaml").read_text())
                    if not isinstance(metadata, dict):
                        raise ValueError("Chart.yaml must contain a mapping")
                    if metadata.get("apiVersion") not in ("v1", "v2"):
                        raise ValueError("apiVersion must be v1 or v2")
                    name = metadata.get("name")
                    if not isinstance(name, str) or not name.strip() or name in (".", "..") or "/" in name or "\\" in name:
                        raise ValueError("name must be a nonempty chart basename")
                    version = metadata.get("version")
                    if not isinstance(version, str) or VERSION.fullmatch(version) is None:
                        raise ValueError("version must be a Helm-compatible semantic version string")
                    kind = metadata.get("type", "application")
                    if kind not in ("application", "library"):
                        raise ValueError("type must be application or library")
                    record.update(name=name, version=version, kind=kind)
                except Exception as exc:
                    record.update(status="invalid-metadata", error=str(exc))
                results.append(record)
    except TimeLimitReached:
        pass
    return sorted(results, key=lambda item: str(item["chart"]))


def exercise_chart(path: Path, args: argparse.Namespace, artifacts: Path) -> dict[str, object]:
    """
    Run baseline checks before sampling schema-described values.

    Args:
        path (Path): Chart directory, optionally an isolated dependency-build copy.
        args (argparse.Namespace): Scan execution settings.
        artifacts (Path): Per-chart reproducer and statistics destination.

    Returns:
        dict[str, object]: Results distinguishing blocked execution and limited coverage.
    """
    baseline = Processes().run([args.helm, "lint", str(path)], capture_output=True, text=True, timeout=args.timeout)
    artifacts.mkdir(parents=True, exist_ok=True)
    diagnostic = baseline.stdout + baseline.stderr
    (artifacts / "lint.txt").write_text(diagnostic)
    if baseline.returncode and ignored("HH1012"):
        record_ignored("HH1012", diagnostic)
    if baseline.returncode and not ignored("HH1012"):
        status = (
            "missing-dependencies"
            if "dependencies" in diagnostic.lower() and ("missing" in diagnostic.lower() or "not found" in diagnostic.lower())
            else "baseline-failed"
        )
        return {"status": status, "code": "HH1012", "error": diagnostic, "coverage": "defaults only"}
    has_schema = (path / "values.schema.json").is_file()
    try:
        chart = (
            Chart.load(path)
            if has_schema
            else Chart(
                path,
                {"type": "object"},
                mapping(yamlio.load((path / "values.yaml").read_text()) or {}),
            )
        )
    except Exception as exc:
        return {"status": "unsupported-schema", "error": str(exc), "coverage": "lint only"}
    filtering: dict[str, object] = {"requested": args.filter, "applied": False}
    if getattr(args, "strict", False):
        findings = audit(chart)
        if findings["findings"] or findings["unresolved"]:
            return {"status": "failed", "error": "Strict input audit failed", "audit": findings, "coverage": "audit only"}
    strength = args.permutations
    try:
        factor_space(chart.schema, 10000)
    except NonFiniteSchema as exc:
        filtering["reason"] = f"Finite filtering unavailable: {exc}"
        if args.filter:
            LOGGER.info("%s; filtering generation before value-path traversal", filtering["reason"])
        if strength is not None or any(
            getattr(args, option, False) for option in ("trim", "trim_topology", "expand_failures", "prune_equivalent", "exhaustive_group")
        ):
            return {"status": "unsupported-schema", "error": str(exc), "coverage": "lint only"}
    else:
        strength = strength or 2
    if strength is None:
        result = check_paths(
            chart,
            budget=min(args.chart_timeout, max(0.000001, args.scan_deadline - time.monotonic()))
            if args.scan_deadline is not None
            else args.chart_timeout,
            max_examples=args.max_examples,
            jobs=(os.process_cpu_count() or 1) if getattr(args, "jobs", 1) == "auto" else getattr(args, "jobs", 1),
            seed=args.seed,
            helm=args.helm,
            timeout=args.timeout,
            artifacts=artifacts,
            fail_fast=args.fail,
            filtering=args.filter,
            traversal_strategy=args.traversal_strategy,
            sampling=Sampling(
                getattr(args, "sample_random", 100),
                getattr(args, "sample_min_cases", 128),
                getattr(args, "filter_adaptive", False),
                str(args.sampling_calibration) if getattr(args, "sampling_calibration", None) else None,
            ),
            release=getattr(args, "release", "hypothesis"),
            namespace=getattr(args, "namespace", "default"),
            kube_version=getattr(args, "kube_version", None),
            allow_empty=getattr(args, "allow_empty", False),
        )
        return {
            **result,
            "coverage": "unique discovered paths; time-bounded property testing",
            "schema_source": "declared" if has_schema else "inferred generation; no values schema",
            "lint": "ignored" if baseline.returncode else "passed",
        }
    filtering["applied"] = args.filter and strength is not None
    result = check_chart(
        chart,
        max_examples=args.max_examples,
        random_seed=args.seed,
        traversal_strategy=args.traversal_strategy,
        sampling=Sampling(
            getattr(args, "sample_random", 100),
            getattr(args, "sample_min_cases", 128),
            getattr(args, "filter_adaptive", False),
            str(args.sampling_calibration) if getattr(args, "sampling_calibration", None) else None,
        ),
        helm=args.helm,
        timeout=args.timeout,
        time_limit=min(args.chart_timeout, max(0.000001, args.scan_deadline - time.monotonic()))
        if args.scan_deadline is not None
        else args.chart_timeout,
        permutations=strength,
        trim=getattr(args, "trim", 0),
        trim_topology=2 if filtering["applied"] else getattr(args, "trim_topology", 0),
        expand_failures=bool(filtering["applied"]) or getattr(args, "expand_failures", False),
        prune_equivalent=getattr(args, "prune_equivalent", False),
        filter_rejections=bool(args.filter),
        max_cases=getattr(args, "max_cases", 10000),
        max_candidates=getattr(args, "max_candidates", 100000),
        exhaustive_threshold=getattr(args, "exhaustive_threshold", 10000),
        exhaustive_groups=tuple(getattr(args, "exhaustive_group", [])),
        infer_exhaustive_groups=not getattr(args, "no_infer_groups", False),
        max_group_cases=getattr(args, "max_group_cases", 256),
        release=getattr(args, "release", "hypothesis"),
        namespace=getattr(args, "namespace", "default"),
        kube_version=getattr(args, "kube_version", None),
        allow_empty=getattr(args, "allow_empty", False),
        fail_fast=args.fail,
        artifact_dir=artifacts,
    )
    return {
        **result,
        "coverage": "schema-generated values",
        "lint": "ignored" if baseline.returncode else "passed",
        "filtering": filtering,
    }


def scan(args: argparse.Namespace) -> int:
    """
    Scan all charts and preserve partial results on interruption.

    Args:
        args (argparse.Namespace): Parsed scan options.

    Returns:
        int: Zero for complete property success, one for failures, two for incomplete coverage.
    """
    if args.max_examples < 1 or not math.isfinite(args.timeout) or args.timeout <= 0:
        raise ValueError("max-examples and timeout must be positive and finite")
    if args.permutations is not None and args.permutations < 1:
        raise ValueError("permutations must be positive")
    if shutil.which(args.helm) is None:
        raise ValueError(f"Helm executable not found: {args.helm}")
    started = time.time()
    scan_started = time.monotonic()
    args.scan_deadline = scan_started + args.scan_timeout if args.scan_timeout is not None else None
    with ExitStack() as scope:
        if args.command == "test":
            root = Path(args.directory).expanduser().resolve()
            return scan_checkout(args, RepositorySource(str(root), root, root.name, False, kind="local"), started, scan_started)
        if not args.helm_repository and Path(args.directory).expanduser().exists():
            raise ValueError("scan accepts remote sources only; use test for local charts and directories")
        source = prepare_helm_source(
            str(args.directory),
            scope,
            helm=args.helm,
            timeout=args.clone_timeout,
            deadline=args.scan_deadline,
            force=args.helm_repository,
            version=args.chart_version,
        )
        if source is None:
            if remote_name(str(args.directory)) is None:
                raise ValueError("scan requires a remote Git or Helm source; use test for local directories")
            if args.chart_version is not None:
                raise ValueError("--chart-version requires a Helm repository or OCI chart source")
            source = RepositorySource.prepare(str(args.directory), scope, args.clone_timeout, args.scan_deadline)
        return scan_checkout(args, source, started, scan_started)


def scan_checkout(args: argparse.Namespace, source: RepositorySource, started: float, scan_started: float) -> int:
    """
    Exercise a prepared source and write reports before its checkout is released.

    Args:
        args (argparse.Namespace): Scan execution and reporting options.
        source (RepositorySource): Local tree and original repository provenance.
        started (float): Scan start epoch, including checkout time.
        scan_started (float): Monotonic start for total elapsed time.

    Returns:
        int: Scan exit status, including checkout failure or timeout.
    """
    root = source.root
    changes: dict[str, object] = (
        comparison(root, getattr(args, "base_ref", None)) if source.status == "ready" else {"status": "unavailable"}
    )
    records = discover_charts(root, deadline=args.scan_deadline) if source.status == "ready" else []
    if source.kind == "helm":
        for package in source.packages:
            matches = [record for record in records if str(record["chart"]).split("/")[0] == package["chart"]]
            for record in matches:
                record["package"] = package
            if not matches:
                records.append({**package, "status": "pending" if package["status"] == "downloaded" else package["status"]})
    discovery_complete = source.status == "ready" and (args.scan_deadline is None or time.monotonic() < args.scan_deadline)
    timed_out = source.status in {"clone-timeout", "source-timeout", "scan-timeout"} or (
        source.status == "ready" and not discovery_complete
    )
    output = args.artifact_dir.resolve() / f"{source.name}_{int(started)}"
    output.mkdir(parents=True, exist_ok=True)
    if source.remote:
        (output / "checkout.txt").write_text(source.diagnostic)
    interrupted = source.status == "interrupted"
    failed_early = False
    for index, record in enumerate(records):
        if source.status != "ready":
            break
        if args.scan_deadline is not None and time.monotonic() >= args.scan_deadline:
            timed_out = True
            break
        if record["status"] != "pending":
            continue
        path = root / str(record["chart"])
        artifacts = output / f"{index:04d}"
        record["artifacts"] = str(artifacts)
        tick = time.monotonic()
        cache = ChartCache()
        LOGGER.info("Chart %d/%d: %s", index + 1, len(records), record["chart"])
        try:
            with ExitStack() as scope:
                if args.scan_deadline is not None:
                    remaining = args.scan_deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeLimitReached()
                    scope.enter_context(execution_timer(remaining))
                selected = args.values if args.values.is_absolute() else path / args.values
                if not selected.is_file():
                    record.update(
                        status="missing-values",
                        result="N/A",
                        error=f"Selected values file not found: {selected}",
                    )
                    continue
                with tempfile.TemporaryDirectory(prefix="hypothesis-helm-scan-") as temporary:
                    copy = Path(temporary) / "chart"
                    shutil.copytree(path, copy, symlinks=False)
                    baseline = selected.read_text()
                    loaded = yamlio.load(baseline)
                    if loaded is not None and not isinstance(loaded, dict):
                        record.update(
                            status="invalid-values",
                            result="N/A",
                            error=f"Selected values must contain a mapping: {selected}",
                        )
                        continue
                    # Unlink copied symlinks before writing to keep the source chart untouched.
                    (copy / "values.yaml").unlink(missing_ok=True)
                    (copy / "values.yaml").write_text(baseline)
                    record["values_file"] = (
                        str(selected.relative_to(root)) if source.remote and selected.is_relative_to(root) else str(selected)
                    )
                    if args.build_dependencies:
                        # Suspend our scan alarm; dependency preparation has its own command timeout.
                        scope.close()
                        LOGGER.info("Preparing dependencies for %s (excluded from testing budgets)", record["chart"])
                        preparation_started = time.monotonic()
                        try:
                            built = Processes().run(
                                [args.helm, "dependency", "build", str(copy)],
                                capture_output=True,
                                text=True,
                                timeout=args.timeout,
                            )
                        finally:
                            preparation_seconds = time.monotonic() - preparation_started
                            record["dependency_preparation_seconds"] = preparation_seconds
                            if args.scan_deadline is not None:
                                args.scan_deadline += preparation_seconds
                        if args.scan_deadline is not None:
                            remaining = args.scan_deadline - time.monotonic()
                            if remaining <= 0:
                                raise TimeLimitReached()
                            scope.enter_context(execution_timer(remaining))
                        artifacts.mkdir(parents=True, exist_ok=True)
                        (artifacts / "dependencies.txt").write_text(built.stdout + built.stderr)
                        if built.returncode:
                            record.update(status="dependency-build-failed", error=built.stdout + built.stderr)
                            continue
                    if record["kind"] == "library":
                        record.update(
                            status="skipped-library",
                            result="N/A",
                            coverage="not a standalone application",
                        )
                        continue
                    cache = ChartCache.prepare(copy, path, args, changes)
                    record["cache"] = {"key": cache.key, "reused": cache.reusable, "reason": cache.reason}
                    if cache.reusable:
                        record.update(
                            status="cached-pass",
                            result="CACHED PASS",
                            attempts=0,
                            coverage="reused completed tests with identical inputs and settings; no new tests executed",
                        )
                        continue
                    if args.export_minimal_values is not None:
                        input_chart = load_input_chart(copy)
                        target = None
                        if args.export_minimal_values:
                            filename = Path(args.export_minimal_values)
                            target = filename.parent / str(record["chart"]) / filename.name
                            protected = {(path / name).resolve() for name in ("values.yaml", "values.schema.json", "Chart.yaml")} | {
                                selected.resolve()
                            }
                            if target.resolve() in protected:
                                raise ValueError("Minimal-values output must not overwrite source chart inputs")
                        record["minimal_values"] = export_minimal(
                            input_chart,
                            target,
                            directory=artifacts,
                            helm=args.helm,
                            timeout=args.timeout,
                            budget=args.minimal_values_timeout,
                            build_dependencies=False,
                        )
                        record["input_inventory"] = mapping(record["minimal_values"])["input_inventory"]
                    if args.export_topological_graph is not None:
                        target = None
                        if args.export_topological_graph:
                            filename = Path(args.export_topological_graph)
                            target = filename.parent / str(record["chart"]) / filename.name
                            if target.resolve() in {
                                (path / "values.schema.json").resolve(),
                                selected.resolve(),
                            }:
                                raise ValueError("Graph export must not overwrite source chart inputs")
                        record["topological_graph"] = export_graph(
                            load_input_chart(copy),
                            target,
                            directory=artifacts,
                            helm=args.helm,
                            timeout=args.timeout,
                        )
                    testing_started = time.monotonic()
                    try:
                        result = exercise_chart(copy, args, artifacts)
                    finally:
                        record["testing_seconds"] = time.monotonic() - testing_started
                    result.pop("chart", None)
                    record.update(result)
                    record["error_diagnostics"] = chart_errors(record, copy)
        except TimeLimitReached:
            record.update(status="scan-timeout", error="Total scan deadline reached")
            timed_out = True
            break
        except KeyboardInterrupt:
            record.update(status="interrupted", error="Interrupted by user")
            interrupted = True
            break
        except subprocess.TimeoutExpired as exc:
            record.update(status="timeout", error=str(exc))
        except Exception as exc:
            record.update(status="error", error=str(exc), failure_type=type(exc).__name__)
        finally:
            record["elapsed_seconds"] = time.monotonic() - tick
            if args.scan_deadline is not None and time.monotonic() >= args.scan_deadline:
                timed_out = True
                if record["status"] in {"time-limit", "timeout"}:
                    record.update(status="scan-timeout", error="Total scan deadline reached")
            if not cache.reusable:
                cache.publish(record)
            LOGGER.info(
                "%s: %s; testing %.2fs; dependency preparation %.2fs; %d charts remain",
                record["chart"],
                record["status"],
                record.get("testing_seconds", 0.0),
                record.get("dependency_preparation_seconds", 0.0),
                len(records) - index - 1,
            )
        if args.fail and record["status"] in {"baseline-failed", "failed", "error"}:
            failed_early = True
            LOGGER.info("Stopping scan after failure in %s (--fail)", record["chart"])
            break
    for record in records:
        record.setdefault("dependency_preparation_seconds", 0.0)
        record.setdefault("testing_seconds", 0.0)
        if failed_early and record["status"] == "pending":
            record["error"] = "Not started: --fail stopped the scan after a chart failure"
        if timed_out and record["status"] == "pending":
            record["error"] = "Not started: total scan deadline reached"
        if source.status != "ready" and record["status"] == "pending":
            record["error"] = "Not started: source preparation did not complete"
        record.setdefault(
            "filtering",
            {
                "requested": args.filter,
                "applied": False,
                "reason": "Chart did not enter finite permutation testing",
            },
        )
        record.setdefault(
            "result",
            "PASS" if record["status"] == "passed" else "FAIL" if record["status"] in {"baseline-failed", "failed"} else "N/A",
        )
    counts = dict(Counter(str(record["status"]) for record in records))
    report: dict[str, object] = {
        "title": "Remote Helm chart scan" if source.remote else "Local Helm chart tests",
        "directory": source.location,
        "started_epoch": int(started),
        "elapsed_seconds": time.monotonic() - scan_started,
        "dependency_preparation_seconds": sum(float(str(record["dependency_preparation_seconds"])) for record in records),
        "testing_seconds": sum(float(str(record["testing_seconds"])) for record in records),
        "scan_status": source.status
        if source.status != "ready"
        else "interrupted"
        if interrupted
        else "scan-timeout"
        if timed_out
        else "failed-early"
        if failed_early
        else "completed",
        "discovery_complete": discovery_complete,
        "unstarted_charts": counts.get("pending", 0),
        "charts_discovered": len(records),
        "counts": counts,
        "charts": records,
        "git_comparison": changes,
        "ignored_rules": ignored_codes(),
        "settings": {
            "ignored_rules": ignored_codes(),
            "max_examples": args.max_examples,
            "jobs": getattr(args, "jobs", 1),
            "worker_model": "sequential charts, concurrent path properties",
            "filter": args.filter,
            "fail": args.fail,
            "permutations": args.permutations,
            "chart_timeout_seconds": args.chart_timeout,
            "scan_timeout_seconds": args.scan_timeout,
            "scan_timeout_excludes_dependency_preparation": True,
            "helm": args.helm,
            "seed": args.seed,
            "traversal_strategy": args.traversal_strategy,
            "sampling": {
                "percent": getattr(args, "sample_random", 100),
                "minimum": getattr(args, "sample_min_cases", 128),
                "aggressive": getattr(args, "filter_adaptive", False),
            },
            "build_dependencies": args.build_dependencies,
            "values": str(args.values),
            "clone_timeout_seconds": args.clone_timeout,
            "chart_version": args.chart_version,
        },
    }
    if source.remote:
        report["source"] = {
            "url": source.location,
            "revision": source.revision,
            "checkout_status": source.status,
        }
        report["summary"] = [f"Repository commit: {source.revision or 'unavailable'}"]
        if source.status != "ready":
            report["error"] = source.diagnostic
            report["summary"] = [
                "Repository checkout did not complete; chart discovery was not performed.",
                source.diagnostic,
            ]
        if source.kind == "helm":
            report["source"] = {
                "url": source.location,
                "kind": "helm",
                "preparation_status": source.status,
                "inventory_complete": source.inventory_complete,
                "packages": source.packages,
            }
            report["summary"] = [
                "Helm packages: latest stable release per chart unless --chart-version selects another version.",
                "Package versions and SHA-256 checksums are recorded in the JSON report.",
            ]
            if source.status != "ready":
                report["summary"] = ["Helm source preparation did not complete; available results are retained.", source.diagnostic]
    summary = report.setdefault("summary", [])
    assert isinstance(summary, list)
    summary.append(
        f"Git comparison: {changes['base_ref']} ({changes['base_commit']}); {counts.get('cached-pass', 0)} cached chart successes reused."
        if changes["status"] == "resolved"
        else "Git comparison unavailable; no charts skipped using previous test results."
    )
    deduplicate_errors(report)
    (output / "scan.json").write_text(json.dumps(report, indent=2) + "\n")
    if args.report is not None:
        stem = Path(args.report) if args.report else Path(f"{source.name}_{int(started)}_report")
        write_reports(report, stem)
    print(json.dumps(report, indent=2))
    if interrupted:
        return 130
    if timed_out:
        return 124
    if source.status in {"clone-failed", "source-failed"}:
        return 1
    if len(records) == 1 and records[0]["status"] == "missing-values":
        return 1
    if any(status in counts for status in ("invalid-metadata", "baseline-failed", "failed", "error")):
        return 1
    return 0 if records and set(counts) <= {"passed", "cached-pass", "ignored"} else 2

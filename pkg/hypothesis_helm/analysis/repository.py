"""
Measure bounded, chart-specific sensitivity panels for an existing repository report.
"""

import argparse
import hashlib
import json
import math
import shutil
import tempfile
import textwrap
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextvars import copy_context
from pathlib import Path

from jsonschema import validators

from hypothesis_helm.analysis.reference import measure_reference
from hypothesis_helm.analysis.sensitivity import Mutation, analyze
from hypothesis_helm.charts.suites.runtime import RenderOptions
from hypothesis_helm.charts.testing.rendering import render
from hypothesis_helm.charts.values import yamlio
from hypothesis_helm.compiler.passes.inputs import load_input_chart
from hypothesis_helm.compiler.randomness.model import RandomInputs
from hypothesis_helm.compiler.randomness.policy import policy as renderer_policy
from hypothesis_helm.compiler.randomness.policy import prepare as prepare_renderer
from hypothesis_helm.environment import refresh_env
from hypothesis_helm.execution.runtime.budget import parse_time_limit
from hypothesis_helm.execution.runtime.processes import Processes
from hypothesis_helm.reporting.console.progress import format_path
from hypothesis_helm.reporting.reports.figures import SENSITIVITY_FIELDS_KEY, SENSITIVITY_PAIRS_KEY
from hypothesis_helm.reporting.reports.links import Publication
from hypothesis_helm.reporting.reports.repository import write_reports
from hypothesis_helm.schemas.contracts import json_value, mapping, sequence

__all__ = ("main", "measure_chart", "mutations", "plot_panel", "prepare_figures")


def mutations(values: dict[str, object], schema: dict[str, object], limit: int, seed: int) -> list[Mutation]:
    """
    Select reproducible scalar changes without inventing arbitrary strings or collection shapes.

    Args:
        values (dict[str, object]): Supplied baseline values.
        schema (dict[str, object]): Authored acceptance contract.
        limit (int): Maximum distinct input paths to measure.
        seed (int): Stable path-order seed.

    Returns:
        list[Mutation]: Schema-valid Boolean flips and adjacent integer changes on unique existing paths.
    """
    if limit < 1:
        raise ValueError("mutation limit must be positive")
    candidates: list[Mutation] = []
    pending: list[tuple[object, tuple[str | int, ...]]] = [(values, ())]
    while pending:
        value, path = pending.pop()
        if isinstance(value, dict):
            pending.extend((child, (*path, str(key))) for key, child in value.items())
        elif isinstance(value, list):
            pending.extend((child, (*path, index)) for index, child in enumerate(value))
        elif type(value) is bool:
            candidates.append(Mutation(format_path(path), path, not value))
        elif type(value) is int:
            candidates.extend(Mutation(format_path(path), path, value + delta) for delta in (1, -1))
    candidates.sort(key=lambda mutation: hashlib.sha256(f"{seed}:{mutation.name}".encode()).digest())
    validator = validators.validator_for(schema)(schema)
    selected: list[Mutation] = []
    paths: set[tuple[str | int, ...]] = set()
    for candidate in candidates:
        if candidate.path not in paths and validator.is_valid(json_value(candidate.apply(values))):
            selected.append(candidate)
            paths.add(candidate.path)
            if len(selected) == limit:
                break
    return selected


def measure_chart(
    source: Path,
    *,
    helm: str,
    limit: int,
    seed: int,
    seconds: float,
    stopped: threading.Event,
    values_filename: Path = Path("values.yaml"),
    build_dependencies: bool = True,
    render_options: RenderOptions | None = None,
    pca_samples: int = 0,
    pca_seconds: float = 60,
    scan_record: dict[str, object] | None = None,
    scan_settings: dict[str, object] | None = None,
) -> dict[str, object]:
    """
    Prepare a private source copy and compare only outputs with a repeatable baseline.

    Args:
        source (Path): Original chart directory, never modified.
        helm (str): Helm executable.
        limit (int): Mutation-path budget; all unordered pairs within it are measured.
        seed (int): Reproducible path-selection seed.
        seconds (float): Sensitivity budget excluding dependency preparation.
        stopped (threading.Event): Coordinator cancellation signal checked before each render.
        values_filename (Path): Selected baseline, relative to the chart or an absolute filename.
        build_dependencies (bool): Whether to prepare locked dependencies in the private copy.
        render_options (RenderOptions | None): Scan renderer context and per-invocation timeout.
        pca_samples (int): Additional reference configurations; zero disables output PCA measurements.
        pca_seconds (float): Separate per-chart reference measurement budget.
        scan_record (dict[str, object] | None): Recorded chart selection and artifacts.
        scan_settings (dict[str, object] | None): Recorded filtering and sampling configuration.

    Returns:
        dict[str, object]: Actual measurements or an explicit reason measurements were unavailable.
    """
    empty: dict[str, object] = {"status": "unavailable", "mutations": [], "interactions": [], "sequence": [], "renders": 0}
    reference = None
    options = render_options or RenderOptions(helm=helm)
    try:
        with tempfile.TemporaryDirectory(prefix="hypothesis-helm-sensitivity-") as temporary:
            target = Path(temporary) / "chart"
            shutil.copytree(source, target)
            metadata = mapping(yamlio.load((target / "Chart.yaml").read_text()))
            if metadata.get("type") == "library":
                return {**empty, "reason": "Library chart: no standalone rendered baseline."}
            if stopped.is_set():
                return {**empty, "reason": "Analysis cancelled."}
            selected_values = values_filename if values_filename.is_absolute() else source / values_filename
            (target / "values.yaml").write_text(selected_values.read_text())
            if metadata.get("dependencies") and build_dependencies:
                prepared = Processes().run([helm, "dependency", "build", str(target)], capture_output=True, timeout=options.timeout)
                if prepared.returncode:
                    return {**empty, "reason": "Dependency preparation failed.", "diagnostic": prepared.stderr}
            chart = load_input_chart(target)
            validators.validator_for(chart.schema)(chart.schema).validate(json_value(chart.defaults))
            selected = mutations(chart.defaults, chart.schema, limit, seed) if limit else []
            if not selected and not pca_samples:
                return {**empty, "reason": "No schema-valid Boolean or integer mutations were available."}
            if renderer_policy(chart) != "native":
                prepare_renderer(chart, helm, force=True, stopped=stopped)
            deadline = time.monotonic() + (pca_seconds if pca_samples else seconds)

            def invoke(values: dict[str, object]) -> object:
                """
                Render one configuration within the remaining measurement budget.

                Args:
                    values (dict[str, object]): Complete selected input.

                Returns:
                    object: Validated manifests with supported randomness controlled.
                """
                remaining = deadline - time.monotonic()
                if stopped.is_set() or remaining <= 0:
                    raise TimeoutError("Sensitivity measurement stopped")
                with RandomInputs() as draws:
                    output = render(
                        chart,
                        values,
                        helm=helm,
                        timeout=min(options.timeout, remaining),
                        stream=False,
                        release=options.release,
                        namespace=options.namespace,
                        kube_version=options.kube_version,
                    )
                    if draws.fallback_reason:
                        raise ValueError("Uncontrolled renderer effects: " + draws.fallback_reason)
                    return output

            baseline = invoke(chart.defaults)
            if baseline != invoke(chart.defaults):
                return {
                    **empty,
                    "renders": 2,
                    "reason": "Repeated baseline renders differed; output changes cannot be attributed to inputs.",
                }
            if pca_samples:
                reference = measure_reference(
                    chart,
                    mutations(chart.defaults, chart.schema, max(1, pca_samples - 1), seed),
                    invoke,
                    scan_record or {},
                    scan_settings or {},
                    limit=pca_samples,
                    seconds=max(0.001, deadline - time.monotonic()),
                )
            if not selected:
                return {
                    **empty,
                    "status": "not-requested" if not limit else "unavailable",
                    "reason": "Sensitivity not requested" if not limit else "No schema-valid scalar changes were available",
                    "output_space": reference,
                    "baseline_verification_renders": 2,
                }
            # PCA has its own measurement budget and does not consume either
            # the scan's test budget or the requested sensitivity budget.
            if pca_samples:
                deadline = time.monotonic() + seconds
            result = analyze(
                chart.defaults,
                chart.schema,
                selected,
                invoke,
                max_mutations=limit,
                max_pairs=math.comb(len(selected), 2),
                time_limit=max(0.001, deadline - time.monotonic()),
            )
            result["baseline_verification_renders"] = 2
            if reference is not None:
                result["output_space"] = reference
            return result
    except Exception as error:
        return {**empty, "reason": str(error), "error_type": type(error).__name__, "output_space": reference}


def _field_path(row: dict[str, object]) -> str:
    """
    Preserve the exact field identity for the numbered figure caption.

    Args:
        row (dict[str, object]): Measured mutation with its path or a legacy name.

    Returns:
        str: Full field path, including array indices and quoted keys.
    """
    return (
        format_path(tuple(part if isinstance(part, int) else str(part) for part in sequence(row["path"])))
        if "path" in row
        else str(row["name"])
    )


def plot_panel(document: dict[str, object], destination: Path, title: str) -> None:
    """
    Save a compact chart-specific interaction panel without fabricating missing measurements.

    Args:
        document (dict[str, object]): Sensitivity observations or an unavailable status.
        destination (Path): Published PNG path.
        title (str): Exact chart identity.

    Returns:
        None: A heatmap with a numbered field key, or a compact absence message, is written.
    """
    import numpy as np
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    rows = [mapping(row) for row in sequence(document.get("mutations", []))]
    # Embed the key in the PNG so republishing a report cannot pair these
    # numbers with a different run's paths or require a separate data file.
    fields = [_field_path(row) for row in rows]
    pairs = [mapping(row) for row in sequence(document.get("interactions", [])) if "mixed_difference_l1" in mapping(row)]
    metadata = {SENSITIVITY_FIELDS_KEY: json.dumps(fields), SENSITIVITY_PAIRS_KEY: str(len(pairs))}
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not pairs:
        # Reports replace this asset with ordinary text using the pair count.
        # Direct image consumers also get a message without an empty plot frame.
        figure = Figure(figsize=(8, 0.55))
        FigureCanvasAgg(figure)
        figure.text(0.5, 0.5, "No comparable pairs", ha="center", va="center", fontsize=16)
        figure.savefig(destination, dpi=170, metadata=metadata)
        return
    figure = Figure(figsize=(8, 6.5), layout="constrained")
    FigureCanvasAgg(figure)
    axis = figure.subplots()
    # Rows and columns represent the same field set, so preserve equal scales.
    axis.set_box_aspect(1)
    measured = sum("distance" in row for row in rows)
    positions = {str(row["name"]): index for index, row in enumerate(rows)}
    matrix = np.full((max(1, len(rows)), max(1, len(rows))), np.nan)
    for pair in pairs:
        a, b = [positions[str(name)] for name in sequence(pair["mutations"])]
        matrix[a, b] = matrix[b, a] = int(str(pair["mixed_difference_l1"]))
    image = axis.imshow(
        np.ma.masked_invalid(matrix),
        origin="lower",
        aspect="equal",
        cmap="viridis",
        vmin=0,
        vmax=max(1, float(np.nanmax(matrix))),
        extent=(0.5, len(rows) + 0.5, 0.5, len(rows) + 0.5),
    )
    colorbar = figure.colorbar(image, ax=axis, shrink=0.5)
    colorbar.set_label(r"$\|\Delta_i\Delta_j f\|_1$", fontsize=16)
    colorbar.ax.tick_params(labelsize=14)
    axis.set(
        title="Field interactions",
        xlabel="Field number (see caption)" if rows else "",
        ylabel="Field number" if rows else "",
    )
    axis.title.set_fontsize(16)
    axis.xaxis.label.set_fontsize(16)
    axis.yaxis.label.set_fontsize(16)
    axis.tick_params(labelsize=14)
    if rows:
        # Larger samples retain every matrix cell and appendix path, with sparse tick labels to stay readable in the PDF.
        ticks = sorted({*range(1, len(rows) + 1, max(1, math.ceil(len(rows) / 12))), len(rows)})
        axis.set_xticks(ticks)
        axis.set_yticks(ticks)
        axis.set(xlim=(0.5, len(rows) + 0.5), ylim=(0.5, len(rows) + 0.5))
    heading = textwrap.fill(title, width=60, break_on_hyphens=False)
    figure.suptitle(f"{heading}\n{measured} measured changes; {len(pairs)} pairs ({document['status']})", fontsize=18)
    if document.get("reason"):
        # Explain missing evidence in the published image, not only in the local JSON.
        reason = textwrap.shorten(" ".join(str(document["reason"]).split()), width=210, placeholder="...")
        figure.supxlabel("\n".join(textwrap.wrap(reason, 65)), fontsize=14)
    # Lay out the full-width heading first, then shrink only the plotted data.
    # Freezing the layout keeps savefig from stretching the heatmap back again.
    figure.canvas.draw()
    figure.set_layout_engine(None)
    position = axis.get_position()
    axis.set_position(
        (position.x0 + position.width * 0.1, position.y0 + position.height * 0.1, position.width * 0.8, position.height * 0.8)
    )
    bar_position = colorbar.ax.get_position()
    colorbar.ax.set_position(
        (axis.get_position().x1 + 0.025, bar_position.y0 + bar_position.height * 0.1, bar_position.width, bar_position.height * 0.8)
    )
    figure.savefig(destination, dpi=170, metadata=metadata)


def prepare_figures(
    report: dict[str, object],
    *,
    output: Path,
    cache: Path,
    source_root: Path,
    jobs: int = 6,
    limit: int = 8,
    seed: int = 0,
    seconds: float = 180,
    helm: str = "helm",
    repository: str | None = None,
    verify_source: bool = True,
    values_filename: Path = Path("values.yaml"),
    build_dependencies: bool = True,
    render_options: RenderOptions | None = None,
    progress: Callable[[str], None] | None = None,
    pca_samples: int = 64,
    pca_seconds: float = 60,
) -> None:
    """
    Measure chart jobs concurrently and publish figures serially to avoid Matplotlib thread races.

    Args:
        report (dict[str, object]): Scan whose chart sections will receive these figures.
        output (Path): Published chart-topology study root, with chart-relative subdirectories.
        cache (Path): Local raw measurement directory.
        source_root (Path): Local chart repository matching the recorded scan revision.
        jobs (int): Maximum concurrent chart measurements.
        limit (int): Maximum measured paths per chart.
        seed (int): Reproducible input path ordering.
        seconds (float): Per-chart measurement limit, excluding dependency preparation.
        helm (str): Helm executable.
        repository (str | None): Published study namespace, such as bitnami or prometheus.
        verify_source (bool): Require a clean matching checkout when enriching a previously saved scan.
        values_filename (Path): Selected values file for each chart, or one absolute baseline.
        build_dependencies (bool): Prepare dependencies before measuring each private copy.
        render_options (RenderOptions | None): Renderer settings inherited from an active scan.
        progress (Callable[[str], None] | None): Progress sink; default prints standalone command updates.
        pca_samples (int): Reference sample ceiling per chart, or zero to skip PCA.
        pca_seconds (float): Separate reference measurement deadline per chart.

    Returns:
        None: Each chart receives actual sensitivity evidence or an explicit unavailable panel.
    """
    if jobs < 1 or limit < 0 or pca_samples < 0 or not (limit or pca_samples):
        raise ValueError("jobs must be positive; at least one nonnegative measurement limit must be enabled")
    if not math.isfinite(seconds) or seconds <= 0 or not math.isfinite(pca_seconds) or pca_seconds <= 0:
        raise ValueError("measurement time must be finite and positive")
    source = mapping(report.get("source", {}))
    if verify_source and source.get("kind") == "git" and source.get("revision"):
        revision = Processes().run(["git", "-C", str(source_root), "rev-parse", "HEAD"], capture_output=True, check=True, timeout=10)
        if revision.stdout.strip() != source["revision"]:
            raise ValueError("Chart checkout differs from the scan revision; use the recorded source before measuring sensitivity")
        changes = Processes().run(["git", "-C", str(source_root), "status", "--porcelain"], capture_output=True, check=True, timeout=10)
        if changes.stdout.strip():
            raise ValueError("Chart checkout has unrecorded changes; use a clean copy of the scan revision")
    charts = [mapping(chart) for chart in sequence(report["charts"])]
    stopped = threading.Event()
    pool = ThreadPoolExecutor(max_workers=jobs)
    futures = {}
    try:
        for chart in charts:
            name = str(chart["chart"])
            if chart.get("status") in {
                "pending",
                "cached-pass",
                "skipped-library",
                "missing-values",
                "invalid-metadata",
                "dependency-build-failed",
            }:
                if pca_samples:
                    chart["output_space"] = {"status": "unavailable", "reason": "No fresh chart tests in this scan", "observations": []}
                continue
            relative = Path(name)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"Unsafe chart path: {name}")
            futures[
                pool.submit(
                    copy_context().run,
                    measure_chart,
                    source_root / relative,
                    helm=helm,
                    limit=limit,
                    seed=seed,
                    seconds=seconds,
                    stopped=stopped,
                    values_filename=values_filename,
                    build_dependencies=build_dependencies,
                    render_options=render_options,
                    pca_samples=pca_samples,
                    pca_seconds=pca_seconds,
                    scan_record=chart,
                    scan_settings=mapping(report.get("settings", {})),
                )
            ] = chart
        for index, future in enumerate(as_completed(futures), 1):
            chart = futures[future]
            name = str(chart["chart"])
            document = future.result()
            document["context"] = {
                "chart": name,
                "source": report.get("source"),
                "seed": seed,
                "maximum_mutations": limit,
                "values": str(values_filename),
                "seconds": seconds,
                "measured_epoch": time.time(),
            }
            directory = cache / name
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "sensitivity.json").write_text(json.dumps(document, indent=2) + "\n")
            if pca_samples:
                chart["output_space"] = document.get("output_space") or {
                    "status": "unavailable",
                    "reason": document.get("reason", "No comparable baseline"),
                    "observations": [],
                }
            # Existing studies use bitnami/name and prometheus/name, while the
            # source checkouts use bitnami/name and charts/name respectively.
            source_path = Path(name)
            relative = Path(*source_path.parts[1:]) if source_path.parts and source_path.parts[0] in {repository, "charts"} else source_path
            study_path = Path(repository) / relative if repository else source_path
            destination = output / study_path / "sensitivity.png"
            chart["report_figures"] = mapping(chart.get("report_figures", {}))
            if limit:
                plot_panel(document, destination, name)
                mapping(chart["report_figures"])["sensitivity"] = str(destination.resolve())
            topology = output / study_path / "topology.png"
            if topology.is_file():
                mapping(chart["report_figures"])["topology"] = str(topology.resolve())
            reference_count = mapping(chart.get("output_space", {})).get("measured", 0)
            message = (
                f"[{index}/{len(futures)}] {name}: {document['status']}; "
                f"{document.get('renders', 0)} sensitivity renders; {reference_count} PCA observations"
            )
            if progress is None:
                print(message, flush=True)
            else:
                progress(message)
    except BaseException:
        stopped.set()
        raise
    finally:
        pool.shutdown(wait=True, cancel_futures=True)


def main(argv: list[str] | None = None) -> int:
    """
    Enrich saved scan reports without rerunning the scan or changing its findings.

    Args:
        argv (list[str] | None): Explicit command-line arguments.

    Returns:
        int: Zero after publication, or 130 after graceful interruption.
    """
    refresh_env()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scan", type=Path, help="existing scan.json")
    parser.add_argument("--report", required=True, type=Path, help="Markdown/PDF output stem")
    parser.add_argument("--source-root", type=Path, help="local chart repository; defaults to the scan directory")
    parser.add_argument("--output", type=Path, default=Path("studies/chart-topologies"))
    parser.add_argument("--cache", type=Path, default=Path(".cache/report-figures"))
    parser.add_argument("--jobs", type=int, default=6)
    parser.add_argument("--max-mutations", type=int, default=8)
    parser.add_argument("--time-limit", type=parse_time_limit, default=180)
    parser.add_argument("--pca-samples", type=int, default=64, help="bounded reference configurations per chart; 0 disables PCA")
    parser.add_argument(
        "--pca-timeout", type=parse_time_limit, default=60, help="additional PCA measurement budget per chart (default: 1m)"
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--helm", default="helm")
    parser.add_argument("--repository", choices=("bitnami", "prometheus"), help="namespace used by the published topology study")
    parser.add_argument("--publication-url", help="optional public GitHub repository for links")
    args = parser.parse_args(argv)
    report = mapping(json.loads(args.scan.read_text()))
    try:
        prepare_figures(
            report,
            output=args.output,
            cache=args.cache / str(report["started_epoch"]),
            source_root=args.source_root or Path(str(report["directory"])),
            jobs=args.jobs,
            limit=args.max_mutations,
            seconds=args.time_limit,
            seed=args.seed,
            helm=args.helm,
            repository=args.repository,
            pca_samples=args.pca_samples,
            pca_seconds=args.pca_timeout,
        )
    except KeyboardInterrupt:
        return 130
    enriched = args.cache / str(report["started_epoch"]) / "report.json"
    enriched.parent.mkdir(parents=True, exist_ok=True)
    publication = Publication(Path.cwd(), args.publication_url, "main") if args.publication_url else None
    write_reports(report, args.report, publication=publication, artifact_links=False)
    enriched.write_text(json.dumps(report, indent=2) + "\n")
    return 0

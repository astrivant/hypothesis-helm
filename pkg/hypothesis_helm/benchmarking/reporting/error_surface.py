"""
Plot paired error-rate measurements without extrapolating incomplete runs or zero-error recall.
"""

import csv
import json
import math
import statistics
from pathlib import Path

from hypothesis_helm.benchmarking.reporting.plots import finish
from hypothesis_helm.benchmarking.reporting.variation import repeated_line
from hypothesis_helm.benchmarking.studies.error_surface import METRICS
from hypothesis_helm.schemas.contracts import mapping, sequence


def plot(output: Path, document: dict[str, object]) -> None:
    """
    Draw paired means and standard deviations, retaining exact observed ranges in the table.

    Args:
        output (Path): Study artifact destination.
        document (dict[str, object]): Actual measurements, including partial rows and oracle counts.

    Returns:
        None: PNG/SVG heatmaps and CSV summaries accompany a concise study guide.
    """
    from hypothesis_helm.benchmarking.reporting.labels import current_labels

    document = mapping(current_labels(document))

    import numpy as np
    from matplotlib import pyplot as plt

    metadata = mapping(document["metadata"])
    rows = [mapping(row) for row in sequence(document["rows"])]
    methods = [str(method) for method in sequence(metadata["methods"])]
    rates = [float(str(rate)) for rate in sequence(metadata["error_rates"])]
    labels = {
        "depth": "Nested conditions",
        "redundancy": "Unused input fields",
        "clustering": "Failure clustering",
    }
    metric_labels = {
        "total_seconds": "Total measured seconds",
        "render_invocations": "Helm renders",
        "error_recall": "Erroneous inputs detected (%)",
        "additional_executed": "Additional inputs checked after failures",
    }
    lines = [
        "# Error rate and filtering",
        "",
        "[Benchmarking](../../benchmarks/README.md)",
        "",
        "Measured axes in this run: " + ", ".join(mapping(metadata["axes"])) + ". The default refresh runs all three axes.",
        "",
        "Each surface changes error rate and one other parameter. Every method receives the same chart, assertion, and traversal seed.",
        "Errors are seeded, input-aware assertions checked against actual Helm output. Templates stay fixed across error rates and seeds.",
        "A failing assignment expects a corrected quantile value. This measures semantic property failures, not YAML parse failures.",
        "Built-in lint and schema checks that depend only on rendered output can have different failure clustering.",
        "Equal rendered manifests may pass for one input and fail for another; cached manifests still undergo the input-aware assertion.",
        "",
        "**Depth:** vary nested conditions around one resource, keeping two quantile selector fields.",
        "**Redundancy:** vary unused fields with no nested conditions; every unused Boolean doubles equivalent-input multiplicity.",
        "**Clustering:** keep the chart fixed with two quantile selectors and no nested conditions, and vary failure placement.",
        "Clustering zero orders assignments uniformly at random; one orders them by the number of switches differing from a seeded centre.",
        "Intermediate controls blend random priority with this distance. They are placement controls, not "
        "measured correlation coefficients.",
        "The ledger records the fraction of single-switch neighbours of failing inputs that also fail.",
        "",
        "Error counts round down to whole assignments. Higher rates add failures to the same seeded ordering; actual rates are recorded.",
        "The oracle is independent of selection: a failure enters the scheduler only after its input is evaluated.",
        "",
        f"Fixed settings: {metadata['input_fields']} Boolean fields, strength {metadata['permutations']}, {metadata['workers']} worker, "
        f"{metadata['repeats']} paired seeds, and {metadata['time_limit_seconds']} seconds per method's execution.",
        "Small domains are fully enumerated before filtering. Each method starts with fresh compiler and "
        "render caches; OS caches can be warm.",
        "Method order is shuffled within every paired comparison. Total time includes planning and execution.",
        "Chart generation, oracle-population construction, and independent reference enumeration are excluded from method timings.",
        "`filter` and `filter-adaptive` expand failed symbolic regions. The other methods retain their usual expansion-disabled behavior.",
        "`sample-random` uses 70% with its 128-case floor. Aggressive sampling falls back when calibration "
        "cannot support it; the CSV records why.",
        "",
        "Colours share a scale across methods within each figure. "
        "Cells show mean ±1 sample SD across completed paired runs; CSV includes ±2 SD endpoints.",
        "Cells are discrete parameter settings; the heatmaps do not interpolate between sampled rates.",
        "T = an incomplete execution; N/A = no erroneous inputs; blank = no measurement. No partial timing is "
        "shown as a completed runtime.",
        "The CSV includes sample SD and observed ranges. These describe seed variation, not confidence intervals. "
        "These synthetic assertions do not "
        "establish recall for arbitrary charts.",
        "",
        "[Individual measurements](results.csv) · [Means and ranges](summary.csv) · [Oracle populations and provenance](results.json)",
        "",
        "| Plot label | Filtering settings |",
        "| --- | --- |",
        "| default | All configurations, without trimming |",
        "| exact-equivalence | `--prune-equivalent`; reuse renders and check every input's assertion |",
        f"| random | `--trim-random {metadata['trim_level']}` |",
        f"| topology | `--trim-topology {metadata['trim_level']}` |",
        f"| combined | Both trim methods at {metadata['trim_level']} |",
        "| filter | `--filter` |",
        "| filter-adaptive | `--filter-adaptive`, including its calibration fallback |",
        "| sample-random | `--sample-random 70`, with the default minimum |",
        "",
    ]
    summary: list[dict[str, object]] = []
    environment = output / "environment.json"
    if environment.is_file():
        lines.extend(["**Timing context:** " + str(mapping(json.loads(environment.read_text()))["timing_context"]), ""])
    for axis, raw_values in mapping(metadata["axes"]).items():
        values = [float(str(value)) for value in sequence(raw_values)]
        selected = [row for row in rows if row["axis"] == axis]
        for metric in METRICS:
            numeric = [float(str(row[metric])) for row in selected if row[metric] is not None and row["status"] == "passed"]
            maximum = 1.0 if metric == "error_recall" else max(numeric, default=1.0) or 1.0
            columns = min(4, len(methods))
            figure, axes = plt.subplots(
                math.ceil(len(methods) / columns),
                columns,
                figsize=(max(5, len(rates) * 0.65) * columns, max(3.8, len(values) * 0.5) * math.ceil(len(methods) / columns)),
                squeeze=False,
            )
            for panel, method in zip(axes.flat, methods, strict=False):
                matrix = np.full((len(values), len(rates)), np.nan)
                annotations: dict[tuple[int, int], str] = {}
                for y, value in enumerate(values):
                    for x, rate in enumerate(rates):
                        batch = [
                            row
                            for row in selected
                            if row["strategy"] == method and row["axis_value"] == value and row["error_percent"] == rate
                        ]
                        if not batch:
                            continue
                        complete = len(batch) == int(str(metadata["repeats"])) and all(row["status"] == "passed" for row in batch)
                        observations = [float(str(row[metric])) for row in batch if row[metric] is not None]
                        deviation = statistics.stdev(observations) if complete and len(observations) > 1 else None
                        center = statistics.mean(observations) if complete and observations else None
                        if not complete:
                            annotations[y, x] = "T" if any(row["status"] != "passed" for row in batch) else "partial"
                        elif observations:
                            matrix[y, x] = statistics.mean(observations)
                            annotations[y, x] = f"{100 * matrix[y, x]:.0f}%" if metric == "error_recall" else f"{matrix[y, x]:.2g}"
                            if deviation is not None:
                                spread = f"{100 * deviation:.1f} pp" if metric == "error_recall" else f"{deviation:.2g}"
                                annotations[y, x] += f"\n±{spread}"
                        else:
                            annotations[y, x] = "N/A"
                        summary.append(
                            {
                                "axis": axis,
                                "axis_value": value,
                                "error_percent": rate,
                                "strategy": method,
                                "metric": metric,
                                "paired_runs": len(batch),
                                "complete": complete,
                                "mean": center,
                                "sample_stddev": deviation,
                                "mean_minus_2sd": center - 2 * deviation if center is not None and deviation is not None else None,
                                "mean_plus_2sd": center + 2 * deviation if center is not None and deviation is not None else None,
                                "minimum": min(observations) if complete and observations else None,
                                "maximum": max(observations) if complete and observations else None,
                            }
                        )
                panel.imshow(matrix, aspect="auto", origin="lower", vmin=0, vmax=maximum, cmap="viridis")
                panel.set_facecolor("#e2e8f0")
                for (y, x), annotation in annotations.items():
                    color = "white" if not np.isnan(matrix[y, x]) and matrix[y, x] < maximum * 0.55 else "#0f172a"
                    panel.text(x, y, annotation, ha="center", va="center", fontsize=8, color=color)
                panel.set_xticks(range(len(rates)), [f"{rate:g}" for rate in rates])
                panel.set_yticks(range(len(values)), [f"{value:g}" for value in values])
                panel.set(title=method, xlabel="Requested erroneous inputs (%)", ylabel=labels[axis])
            for panel in list(axes.flat)[len(methods) :]:
                panel.set_visible(False)
            figure.suptitle(f"{metric_labels[metric]} vs error rate and {axis}")
            name = f"{axis}-{metric.replace('_', '-')}"
            finish(
                figure,
                output,
                name,
                f"Cells: mean ±1 sample SD where n≥2; {metadata['repeats']} paired seeds. pp = percentage points. "
                "T = incomplete; N/A = zero errors. CSV: ±2 SD, not confidence intervals.",
            )
            lines.extend([f"![{metric_labels[metric]} by {axis}]({name}.png)", ""])
    clustering_rows = [row for row in rows if row["axis"] == "clustering"]
    if clustering_rows:
        findings = [
            "# Failure clustering: measured counts",
            "",
            "[Graphs and methodology](README.md)",
            "",
            "Compare rows with the same rate: the erroneous-input count and chart stay fixed while placement changes.",
            "Detected counts below are paired means followed by the observed range; they count inputs, not distinct bugs.",
            "Neighbour fraction measures actual clustering: neighbours differ in one Boolean switch.",
            "Expansion follows symbolic output/branch regions, which need not match these input neighbourhoods.",
            "",
            "| Rate | Clustering | Failing neighbours | Method | Found / errors (range) | Mean added checks |",
            "| ---: | ---: | ---: | --- | --- | ---: |",
        ]
        for rate in rates:
            for value in sorted({float(str(row["axis_value"])) for row in clustering_rows}):
                for method in methods:
                    batch = [
                        row
                        for row in clustering_rows
                        if row["strategy"] == method and row["axis_value"] == value and row["error_percent"] == rate
                    ]
                    if len(batch) != int(str(metadata["repeats"])) or any(row["status"] != "passed" for row in batch):
                        continue
                    counts = [int(str(row["errors_detected"])) for row in batch]
                    neighbors = [float(str(row["neighbor_error_fraction"])) for row in batch if row["neighbor_error_fraction"] is not None]
                    fraction = f"{statistics.mean(neighbors):.1%}" if neighbors else "N/A"
                    added = statistics.mean(int(str(row["additional_executed"])) for row in batch)
                    findings.append(
                        f"| {rate:g}% | {value:g} | {fraction} | {method} | "
                        f"{statistics.mean(counts):g} / {batch[0]['error_count']} ({min(counts)}-{max(counts)}) | {added:g} |"
                    )
        (output / "clustering-counts.md").write_text("\n".join(findings) + "\n")
        lines.extend(["[Compare clustering at a fixed error count](clustering-counts.md)", ""])
        figure, panel = plt.subplots(figsize=(9, 5))
        for index, value in enumerate(sorted({float(str(row["axis_value"])) for row in clustering_rows})):
            observations_by_rate = []
            for rate in rates:
                seed_observations = {
                    int(str(row["repeat"])): float(str(row["neighbor_error_fraction"]))
                    for row in clustering_rows
                    if row["axis_value"] == value and row["error_percent"] == rate and row["neighbor_error_fraction"] is not None
                }
                observations_by_rate.append(list(seed_observations.values()))
            repeated_line(panel, rates, observations_by_rate, f"Clustering {value:g}", f"C{index % 10}", upper=1)
        panel.set(xlabel="Requested erroneous inputs (%)", ylabel="Failing neighbours / all neighbours of failing inputs", ylim=(0, 1))
        panel.legend()
        panel.grid(alpha=0.2)
        figure.suptitle("Measured failure clustering")
        finish(
            figure,
            output,
            "clustering-observed",
            "Neighbours differ in one Boolean switch. Variation is across seeds; zero errors have no ratio.",
        )
        lines.extend(["![Measured clustering, independent of filter selection](clustering-observed.png)", ""])
    with (output / "summary.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summary[0]) if summary else ["axis"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(summary)
    from hypothesis_helm.benchmarking.reporting.response_surface import plot as plot_quadratic

    plot_quadratic(output, document)
    lines.extend(["[Fitted response surfaces: measurements, quadratic predictions and residuals](quadratic-fits.md)", ""])
    if (output / "symbolic" / "README.md").is_file():
        lines.extend(["[Symbolic equations versus quadratics on held-out data](symbolic/README.md)", ""])
    (output / "README.md").write_text("\n".join(lines))

"""
Compare measured response surfaces with fitted quadratics and visible residuals.
"""

import json
import statistics
from pathlib import Path

from attrs import asdict

from hypothesis_helm.benchmarking.analysis.quadratic import fit
from hypothesis_helm.benchmarking.reporting.descriptions import describe
from hypothesis_helm.reporting.contents import with_contents
from hypothesis_helm.schemas.contracts import mapping, sequence


def plot(output: Path, document: dict[str, object]) -> None:
    """
    Publish paired observations and predictions for each method and response.

    Args:
        output (Path): Directory containing the source measurements.
        document (dict[str, object]): Error-surface or response-surface ledger.

    Returns:
        None: Writes figures, fitted coefficients, diagnostics and explanatory Markdown.
    """
    from hypothesis_helm.benchmarking.reporting.labels import current_labels

    document = mapping(current_labels(document))

    import numpy as np
    from matplotlib import pyplot as plt

    metadata = mapping(document["metadata"])
    rows = [mapping(row) for row in sequence(document["rows"])]
    planes = sorted({str(row.get("plane", row.get("axis"))) for row in rows})
    methods = [str(method) for method in sequence(metadata["methods"])]
    repeats = int(str(metadata["repeats"]))
    records: list[dict[str, object]] = []
    lines = [
        "# Fitted response surfaces",
        "",
        "[Measurements](README.md) · [Model definition](../../docs/benchmarking/response-surface.md)",
        "",
        "Quadratics fitted to collected cell means, separately for each method and response. Coefficients are not theoretical predictions.",
        "Only cells with every requested repeat completed enter the fit. Missing or timed-out cells remain blank.",
        "A fit requires a complete rectangular grid and more than six identifiable cells; otherwise its reason is recorded below.",
        "Mean ±1 sample SD labels describe seed variation, not confidence intervals. Residuals are observed minus fitted cell means.",
        "Continuous predictions between discrete settings describe the model, not additional Helm measurements.",
        "Negative predictions remain visible; neither nonnegative runtime nor bounded error counts are enforced by this polynomial.",
        "RMSE and R² measure agreement with the training cells, not performance on unseen charts. No global worst-case claim is made.",
        "",
        "[Coefficients, bounds and diagnostics](quadratic-fits.json)",
        "",
    ]
    for plane in planes:
        selected = [row for row in rows if str(row.get("plane", row.get("axis"))) == plane]
        modern = "plane" in selected[0]
        x_key, y_key = ("x", "y") if modern else ("axis_value", "error_percent")
        x_label = {
            "structure": "Fields ignored by primary output",
            "failures": "Failure clustering",
            "clustering": "Failure clustering",
            "depth": "Nested conditions",
            "redundancy": "Unused fields",
        }.get(plane, plane)
        y_label = "Nested conditions" if plane == "structure" else "Requested erroneous inputs (%)"
        xs = sorted({float(str(row[x_key])) for row in selected})
        ys = sorted({float(str(row[y_key])) for row in selected})
        for method in methods:
            for metric, label in (("total_seconds", "Total runtime (seconds)"), ("errors_missed", "Erroneous inputs missed")):
                points: list[tuple[float, float, float]] = []
                deviations: list[float | None] = []
                for y in ys:
                    for x in xs:
                        batch = [
                            row
                            for row in selected
                            if row["strategy"] == method and float(str(row[x_key])) == x and float(str(row[y_key])) == y
                        ]
                        if len(batch) != repeats or any(row["status"] != "passed" for row in batch):
                            continue
                        values = [float(str(row[metric])) for row in batch]
                        points.append((x, y, statistics.mean(values)))
                        deviations.append(statistics.stdev(values) if len(values) > 1 else None)
                record: dict[str, object] = {"plane": plane, "method": method, "metric": metric, "x": x_label, "y": y_label}
                name = f"quadratic-{plane}-{method}-{metric.replace('_', '-')}"
                records.append(record)
                try:
                    if len(points) != len(xs) * len(ys):
                        raise ValueError("incomplete grid: no fit to avoid censoring bias or unsupported interpolation")
                    model = fit(points)
                except ValueError as error:
                    for extension in ("png", "svg"):
                        (output / f"{name}.{extension}").unlink(missing_ok=True)
                    record.update(status="unavailable", reason=str(error))
                    lines.extend([f"{plane} / {method} / {label}: fit unavailable ({error}).", ""])
                    continue
                record.update(status="fitted", **asdict(model))
                grid_x, grid_y = np.meshgrid(np.linspace(xs[0], xs[-1], 81), np.linspace(ys[0], ys[-1], 81))
                predicted = np.array([model.predict(float(x), float(y)) for x, y in zip(grid_x.flat, grid_y.flat, strict=True)]).reshape(
                    grid_x.shape
                )
                observed = np.array([z for _, _, z in points]).reshape(len(ys), len(xs))
                residuals = np.array([z - model.predict(x, y) for x, y, z in points]).reshape(observed.shape)
                low, high = min(float(predicted.min()), float(observed.min())), max(float(predicted.max()), float(observed.max()))
                if low == high:
                    high = low + 1
                figure, panels = plt.subplots(1, 3, figsize=(max(17, len(xs) * 2.1), max(5.8, len(ys) * 0.55 + 2)))
                colours = panels[0].imshow(observed, origin="lower", aspect="auto", vmin=low, vmax=high)
                panels[1].pcolormesh(grid_x, grid_y, predicted, shading="auto", vmin=low, vmax=high)
                spread = max(float(np.abs(residuals).max()), 1e-12)
                errors = panels[2].imshow(residuals, origin="lower", aspect="auto", cmap="coolwarm", vmin=-spread, vmax=spread)
                for panel, title in zip(panels, ("Collected means ±1 SD", "Fitted quadratic", "Observed - fitted"), strict=True):
                    panel.set(title=title, xlabel=x_label, ylabel=y_label)
                for panel in (panels[0], panels[2]):
                    panel.set_xticks(range(len(xs)), [f"{value:g}" for value in xs])
                    panel.set_yticks(range(len(ys)), [f"{value:g}" for value in ys])
                    panel.set_xlabel(x_label + "\nSampled settings, equally spaced")
                for (x, y, value), deviation in zip(points, deviations, strict=True):
                    annotation = f"{value:.2g}" + (f"\n±{deviation:.1g}" if deviation is not None else "")
                    panels[0].text(
                        xs.index(x),
                        ys.index(y),
                        annotation,
                        ha="center",
                        va="center",
                        fontsize=7,
                        bbox={"facecolor": "white", "alpha": 0.75, "edgecolor": "none", "pad": 1},
                    )
                figure.colorbar(colours, ax=panels[0], label=label)
                figure.colorbar(colours, ax=panels[1], label=label)
                figure.colorbar(errors, ax=panels[2], label="Residual (same units)")
                figure.suptitle(f"{plane.capitalize()} response surface: {method} / {label}")
                top = describe(
                    figure,
                    name,
                    question="Does a quadratic explain the measured surface? Compare observations, predictions and their disagreement.",
                )
                figure.tight_layout(rect=(0, 0, 1, top))
                for extension in ("png", "svg"):
                    figure.savefig(output / f"{name}.{extension}", dpi=170, facecolor="white")
                plt.close(figure)
                r_squared = f"{model.r_squared:.3f}" if model.r_squared is not None else "N/A (constant observations)"
                lines.extend(
                    [
                        f"## {plane}: {method}, {label}",
                        "",
                        f"RMSE: {model.rmse:.4g}; R²: {r_squared}; cells: {model.cells}.",
                        "",
                        f"![Collected and fitted surfaces with residuals]({name}.png)",
                        "",
                    ]
                )
    (output / "quadratic-fits.json").write_text(
        json.dumps(
            {"source": "results.json", "coefficient_order": ["intercept", "u", "v", "uv", "u2", "v2"], "fits": records},
            indent=2,
            allow_nan=False,
        )
        + "\n"
    )
    (output / "quadratic-fits.md").write_text(with_contents("\n".join(lines) + "\n"))

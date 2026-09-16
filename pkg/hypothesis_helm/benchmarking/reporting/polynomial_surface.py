"""
Show held-out measurements beside quadratic and quartic predictions.
"""

from pathlib import Path

from hypothesis_helm.benchmarking.reporting.descriptions import describe
from hypothesis_helm.reporting.contents import with_contents
from hypothesis_helm.schemas.contracts import mapping, sequence


def plot(output: Path, ledger: dict[str, object]) -> None:
    """
    Publish comparable panels and holdout errors, preserving unavailable fits visibly.

    Args:
        output (Path): Separate comparison directory.
        ledger (dict[str, object]): Models, reserved observations and scores.

    Returns:
        None: Writes PNG, SVG and Markdown reports.
    """
    import numpy as np
    from matplotlib import pyplot as plt
    from matplotlib.patches import Rectangle

    lines = [
        "# Quadratic versus quartic",
        "",
        "Both models train on the same cells, excluding 25% of settings and the last repeat. Corners remain in training.",
        "Outlined cells are held out in both setting and repeat. All observed panels show the reserved repeat.",
        "Scores compare unmodified predictions: lower RMSE is better. A quartic is not assumed to improve prediction.",
        "Timing reflects the host's load during collection; this small comparison does not establish a general model ranking.",
        "A full quartic needs 15 identifiable coefficients and more than 15 training cells, including at least five settings per axis.",
        "Unavailable fits remain blank. No extra measurements are inferred, and existing quadratic and symbolic results are unchanged.",
        "",
        "[Splits, coefficients and scores](results.json)",
        "",
        "| Surface / method / response | Model | Held-out cells RMSE | Held-out repeat RMSE | Both held out RMSE |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for index, value in enumerate(sequence(ledger["fits"])):
        record = mapping(value)
        label = f"{record['plane']} / {record['method']} / {record['metric']}"
        if "split" not in record:
            lines.append(f"| {label} | Unavailable: {record['reason']} | - | - | - |")
            continue
        split = mapping(record["split"])
        observed = [[float(str(v)) for v in sequence(point)] for point in sequence(split["observed"])]
        xs, ys = sorted({p[0] for p in observed}), sorted({p[1] for p in observed})
        models = mapping(record["models"])
        x_label = {
            "clustering": "Failure clustering",
            "failures": "Failure clustering",
            "depth": "Nested conditions",
            "redundancy": "Unused fields",
            "structure": "Fields ignored by primary output",
        }.get(str(record["plane"]), "First factor")
        y_label = "Nested conditions" if record["plane"] == "structure" else "Requested erroneous inputs (%)"
        arrays = [np.array([p[2] for p in observed]).reshape(len(xs), len(ys)).T]
        for name in ("quadratic", "quartic"):
            model = mapping(models[name])
            if model["status"] != "fitted":
                lines.append(f"| {label} | {name}: {model['reason']} | - | - | - |")
                continue
            scores = mapping(model["scores"])
            cells, seeds, joint = (float(str(mapping(scores[group])["rmse"])) for group in ("cells", "seeds", "joint"))
            lines.append(f"| {label} | {name} | {cells:.4g} | {seeds:.4g} | {joint:.4g} |")
            arrays.append(np.array([float(str(sequence(p)[2])) for p in sequence(model["predictions"])]).reshape(len(xs), len(ys)).T)
        low, high = min(float(a.min()) for a in arrays), max(float(a.max()) for a in arrays)
        if low == high:
            high = low + 1
        figure, axes = plt.subplots(1, 3, figsize=(17, 6))
        cursor = 0
        for panel, name in zip(axes, ("observed", "quadratic", "quartic"), strict=True):
            panel.set_title("Held-out repeat" if name == "observed" else name.capitalize())
            model = mapping(models[name]) if name != "observed" else {}
            if name != "observed" and model["status"] != "fitted":
                panel.text(0.5, 0.5, f"Unavailable\n{model['reason']}", ha="center", va="center", wrap=True)
                panel.set_axis_off()
                continue
            colours = panel.imshow(arrays[cursor], origin="lower", aspect="auto", vmin=low, vmax=high)
            cursor += 1
            panel.set_xticks(range(len(xs)), [f"{x:g}" for x in xs], rotation=45)
            panel.set_yticks(range(len(ys)), [f"{y:g}" for y in ys])
            panel.set_xlabel(x_label + " (sampled settings)")
            panel.set_ylabel(y_label)
            for point in sequence(split["joint"]):
                x, y, _ = (float(str(v)) for v in sequence(point))
                panel.add_patch(Rectangle((xs.index(x) - 0.5, ys.index(y) - 0.5), 1, 1, fill=False, edgecolor="black", linewidth=1))
            figure.colorbar(colours, ax=panel, label="Seconds" if record["metric"] == "total_seconds" else "Erroneous inputs missed")
        response_label = "Runtime" if record["metric"] == "total_seconds" else "Erroneous inputs missed"
        figure.suptitle(f"{record['plane']} / {record['method']}: {response_label}")
        top = describe(figure, "polynomial-comparison", question="Does a quartic predict reserved measurements better than a quadratic?")
        figure.tight_layout(rect=(0, 0, 1, top))
        filename = f"comparison-{index + 1}"
        for extension in ("png", "svg"):
            figure.savefig(output / f"{filename}.{extension}", dpi=170, facecolor="white")
        plt.close(figure)
    lines.extend(["", "## Comparisons", ""])
    for index, value in enumerate(sequence(ledger["fits"])):
        if "split" in mapping(value):
            lines.extend([f"![Held-out observations and model predictions](comparison-{index + 1}.png)", ""])
    (output / "README.md").write_text(with_contents("\n".join(lines) + "\n"))

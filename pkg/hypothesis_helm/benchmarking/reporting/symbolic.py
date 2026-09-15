"""
Publish held-out symbolic-regression comparisons alongside measured surfaces.
"""

from pathlib import Path

from hypothesis_helm.benchmarking.reporting.descriptions import describe
from hypothesis_helm.schemas.contracts import mapping, sequence


def plot(output: Path, ledger: dict[str, object]) -> None:
    """
    Draw observed, quadratic and symbolic predictions on identical discrete grids.

    Args:
        output (Path): Analysis artifact destination.
        ledger (dict[str, object]): Fitted expressions, reserved predictions and scoring evidence.

    Returns:
        None: PNG/SVG comparisons and an equation/holdout score report.
    """
    import numpy as np
    from matplotlib import pyplot as plt
    from matplotlib.patches import Rectangle

    lines = [
        "# Symbolic response surfaces",
        "",
        "Each model was trained without the last repeat and without 25% of factor cells. The four corners remain in training.",
        "Predictions below were frozen before scoring. These are empirical equations, not pruning proofs or recall guarantees.",
        "The observed panel uses the reserved repeat; both models use identical training data and held-out groups.",
        "Cells: unseen settings on training seeds. Seeds: unseen repeat at training settings. Joint: unseen settings and repeat.",
        "Repeated seeds refer to chart traversal/error placement; only one equation-search seed was used in this experiment.",
        "Only the last source repeat is reserved, so these results do not establish generalization across many unseen seeds.",
        "Colours share a scale within each figure; predictions are not clipped to physical bounds. Cells are equally spaced.",
        "Outlined cells were withheld from training; all observed values come from the reserved repeat.",
        "",
        "[Raw equations, training splits, predictions and provenance](results.json)",
        f"Search limits: {ledger['iterations']} iterations, {ledger['fit_timeout']} seconds per search, "
        f"expression complexity {ledger['max_size']}; seed {ledger['seed']}, serial execution.",
        "Search timeout excludes initialization and can affect reproducibility. Operators: +, -, *, /, square, exp.",
        "[PySR](https://github.com/astroautomata/PySR) supplies the equation search; holdouts are not used to tune it.",
        "",
        "| Surface | Model | Unseen cells RMSE | Unseen seed RMSE | Joint holdout RMSE |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    figures: list[str] = []
    for raw in sequence(ledger["fits"]):
        record = mapping(raw)
        label = f"{record['plane']} / {record['method']} / {record['metric']}"
        if record["status"] != "complete":
            figures.extend([f"{label}: unavailable ({record.get('reason')}).", ""])
            continue
        scores = mapping(record["scores"])
        for model in ("quadratic", "symbolic"):
            values = [float(str(mapping(mapping(scores[group])[model])["rmse"])) for group in ("cells", "seeds", "joint")]
            lines.append(f"| {label} | {model} | {values[0]:.4g} | {values[1]:.4g} | {values[2]:.4g} |")
        points = [mapping(point) for point in sequence(record["predictions"])]
        xs, ys = sorted({float(str(p["x"])) for p in points}), sorted({float(str(p["y"])) for p in points})
        ordered = sorted(points, key=lambda p: (float(str(p["y"])), float(str(p["x"]))))
        matrices = [
            np.array([float(str(p[key])) for p in ordered]).reshape(len(ys), len(xs)) for key in ("observed", "quadratic", "symbolic")
        ]
        low, high = min(float(m.min()) for m in matrices), max(float(m.max()) for m in matrices)
        if high == low:
            high = low + 1
        figure, axes = plt.subplots(1, 3, figsize=(max(17, len(xs) * 2.1), max(6, len(ys) * 0.55 + 2)))
        for panel, matrix, title in zip(
            axes, matrices, ("Observed reserved repeat", "Quadratic prediction", "PySR prediction"), strict=True
        ):
            image = panel.imshow(matrix, origin="lower", aspect="auto", vmin=low, vmax=high)
            panel.set_xticks(range(len(xs)), [f"{v:g}" for v in xs])
            panel.set_yticks(range(len(ys)), [f"{v:g}" for v in ys])
            panel.set(
                title=title,
                xlabel="Clustering" if record["plane"] in ("clustering", "failures") else str(record["plane"]),
                ylabel="Nested conditions" if record["plane"] == "structure" else "Requested erroneous inputs (%)",
            )
            figure.colorbar(image, ax=panel, label="Seconds" if record["metric"] == "total_seconds" else "Erroneous inputs missed")
            for point in sequence(mapping(record["split"])["joint"]):
                x, y, _ = sequence(point)
                panel.add_patch(
                    Rectangle(
                        (xs.index(float(str(x))) - 0.5, ys.index(float(str(y))) - 0.5), 1, 1, fill=False, edgecolor="black", linewidth=1.5
                    )
                )
        name = f"{record['plane']}-{record['method']}-{record['metric']}"
        figure.suptitle(label.replace("_", " "))
        top = describe(
            figure,
            name,
            question="Which fitted equation predicts reserved measurements better: a quadratic or a searched symbolic expression?",
        )
        figure.text(
            0.5, 0.015, "Outlined cells were withheld from training; every observation uses the reserved repeat.", ha="center", fontsize=9
        )
        figure.tight_layout(rect=(0, 0.05, 1, top))
        for extension in ("png", "svg"):
            figure.savefig(output / f"{name}.{extension}", dpi=170, facecolor="white")
        plt.close(figure)
        figures.extend(
            [
                f"## {label}",
                "",
                "Selected PySR equation (response in original units):",
                "",
                "```text",
                str(record["equation"]),
                "```",
                "",
                f"Input bounds (xmin, xmax, ymin, ymax): `{record['bounds']}`.",
                "`u = 2*(x-xmin)/(xmax-xmin)-1`; `v = 2*(y-ymin)/(ymax-ymin)-1`.",
                "",
                f"![Reserved measurements and model predictions]({name}.png)",
                "",
            ]
        )
    (output / "README.md").write_text("\n".join([*lines, "", *figures]) + "\n")

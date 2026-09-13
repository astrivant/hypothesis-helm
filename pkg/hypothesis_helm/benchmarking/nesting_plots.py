"""
Publish nesting-depth matrices and PCA frames shared across depth profiles.
"""

import csv
import json
import os
import tempfile
from collections import Counter
from pathlib import Path
from textwrap import dedent

import numpy as np

from hypothesis_helm.schemas.contracts import mapping, number, sequence

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "hypothesis-helm-matplotlib"))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

LABELS = {
    "before": "Strength 8",
    "random": "Random",
    "topology": "Topology",
    "combined": "Both trims",
}


def plot(output: Path, document: dict[str, object]) -> None:
    """
    Draw exact policy statistics and shared-frame projections of complete manifest populations.

    Args:
        output (Path): Artifact destination.
        document (dict[str, object]): Completed references, measured policies and pooled PCA bases.

    Returns:
        None: Matrix, PCA figures, CSV and reproducible documentation are written.
    """
    references = [mapping(value) for value in sequence(document["references"])]
    rows = [mapping(value) for value in sequence(document["rows"])]
    metadata = mapping(document["metadata"])
    if any(row["status"] != "complete" for row in [*references, *rows]):
        raise ValueError("complete references and policies are required")
    labels = {**LABELS, "before": f"Strength {metadata['permutations']}"}
    indexed = {(r["structure"], r["strategy"], r["expand_failures"]): r for r in rows}
    columns = [(strategy, expanded) for strategy in labels for expanded in (False, True)]
    figure, axes = plt.subplots(2, 1, figsize=(17, 10))
    for axis, metric, title in zip(
        axes,
        ("erroneous_input_recall", "checked_inputs"),
        ("Erroneous inputs exercised", "Inputs checked by policy"),
        strict=True,
    ):
        values = [[number(indexed[(ref["structure"], strategy, expanded)][metric]) for strategy, expanded in columns] for ref in references]
        axis.imshow(
            values,
            cmap="YlGn" if metric == "erroneous_input_recall" else "YlOrRd",
            vmin=0,
            vmax=1 if metric == "erroneous_input_recall" else None,
            aspect="auto",
        )
        axis.set_title(title)
        axis.set_yticks(range(len(references)), [str(ref["structure"]) for ref in references])
        axis.set_xticks(range(len(columns)), [labels[s] + (" + expansion" if e else "") for s, e in columns])
        for i, ref in enumerate(references):
            for j, (strategy, expanded) in enumerate(columns):
                row = indexed[(ref["structure"], strategy, expanded)]
                label = str(row["checked_inputs"])
                if metric == "erroneous_input_recall":
                    label = (
                        f"{row['erroneous_inputs_found']}/{row['erroneous_inputs_total']}\n{100 * (1 - number(row[metric])):.1f}% missed"
                    )
                axis.text(
                    j,
                    i,
                    label,
                    ha="center",
                    va="center",
                    fontsize=9,
                    bbox={"facecolor": "white", "alpha": 0.75, "edgecolor": "none"},
                )
    figure.suptitle(f"Chart nesting × permutation strength {metadata['permutations']} · fixed trim level 2")
    figure.tight_layout(rect=(0, 0, 1, 0.96))
    for extension in ("png", "svg"):
        figure.savefig(output / f"matrix.{extension}", dpi=160, facecolor="white")
    plt.close(figure)
    for raw_frame in sequence(document["frames"]):
        frame = mapping(raw_frame)
        refs = [ref for ref in references if ref["family"] == frame["family"]]
        coordinates = mapping(frame["coordinates"])
        pooled = np.concatenate([np.asarray(coordinates[str(ref["structure"])], dtype=float) for ref in refs])
        low, high = pooled.min(axis=0), pooled.max(axis=0)
        pad = np.maximum((high - low) * 0.12, 0.5)
        variance = sequence(mapping(frame["basis"])["explained_variance_ratio"])
        largest = max(max(Counter(sequence(ref["outcome_indices"])).values()) for ref in refs)
        for expanded in (False, True):
            figure, axes = plt.subplots(len(refs), 5, figsize=(21, 11), squeeze=False)
            for i, ref in enumerate(refs):
                points = np.asarray(coordinates[str(ref["structure"])], dtype=float)
                identities = [int(number(value)) for value in sequence(ref["outcome_indices"])]
                faults = {int(number(value)) for value in sequence(ref["faulty_indices"])}
                faulty_outputs = {identities[index] for index in faults}
                locations = {identity: points[index] for index, identity in enumerate(identities)}
                for j, strategy in enumerate(("full", *labels)):
                    indices = (
                        list(range(len(points)))
                        if strategy == "full"
                        else [int(number(value)) for value in sequence(indexed[(ref["structure"], strategy, expanded)]["checked_indices"])]
                    )
                    counts = Counter(identities[index] for index in indices)
                    axis = axes[i, j]
                    background = np.array(list(locations.values()))
                    axis.scatter(background[:, 0], background[:, 1], c="#cbd5e1", s=18, alpha=0.6)
                    for erroneous, color, marker in (
                        (False, "#2563eb", "o"),
                        (True, "#dc2626", "X"),
                    ):
                        kept = [identity for identity in counts if (identity in faulty_outputs) == erroneous]
                        if kept:
                            kept_points = np.array([locations[identity] for identity in kept])
                            axis.scatter(
                                kept_points[:, 0],
                                kept_points[:, 1],
                                color=color,
                                marker=marker,
                                s=[24 + 400 * counts[identity] / largest for identity in kept],
                                alpha=0.8,
                                edgecolors="white",
                                linewidths=0.5,
                            )
                    missed = faulty_outputs - counts.keys()
                    if missed:
                        missing = np.array([locations[identity] for identity in missed])
                        axis.scatter(
                            missing[:, 0],
                            missing[:, 1],
                            s=100,
                            facecolors="none",
                            edgecolors="#d97706",
                        )
                    found = len(set(indices) & faults)
                    title = "Full population" if strategy == "full" else labels[strategy]
                    axis.set_title(
                        f"{title}: {len(indices)} checks\nErrors {found}/{len(faults)} "
                        f"({100 * (1 - found / len(faults)):.1f}% missed)\n"
                        f"Outputs {len(counts)}/{len(locations)} "
                        f"({100 * len(counts) / len(locations):.1f}%)",
                        fontsize=9,
                    )
                    axis.set_xlim(low[0] - pad[0], high[0] + pad[0])
                    axis.set_ylim(low[1] - pad[1], high[1] + pad[1])
                    axis.set_xlabel(f"PC1 ({100 * number(variance[0]):.1f}%)")
                    axis.set_ylabel(f"PC2 ({100 * number(variance[1]):.1f}%)")
                    axis.grid(alpha=0.2)
                axes[i, 0].annotate(
                    str(ref["profile"]),
                    xy=(-0.3, 0.5),
                    xycoords="axes fraction",
                    rotation=90,
                    va="center",
                    fontsize=12,
                    weight="bold",
                )
            mode = "expanded" if expanded else "unexpanded"
            figure.suptitle(
                f"{frame['family']} topology mixture · shared PCA across depths · {mode}",
                fontsize=16,
            )
            figure.text(
                0.5,
                0.02,
                "Blue: correct · red X: erroneous · orange ring: missed erroneous output · "
                "gray: full space\nArea tracks input mass on one family-wide scale; "
                "axes fixed across profiles and policies.",
                ha="center",
            )
            figure.tight_layout(rect=(0.02, 0.065, 1, 0.96))
            for extension in ("png", "svg"):
                figure.savefig(output / f"pca-{frame['family']}-{mode}.{extension}", dpi=160, facecolor="white")
            plt.close(figure)
    for svg in output.glob("*.svg"):
        svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")
    with (output / "results.csv").open("w") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[key for key in rows[0] if key not in {"checked_indices", "additional_indices"}],
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    text = dedent(f"""
        # Chart nesting and output-space PCA

        [Benchmarking](../README.md)

        **8 is permutation interaction strength, not component count.** This study holds
        `--permutations {metadata["permutations"]}` fixed and varies additional Boolean gate depth:
        shallow (1), deep (5), and a seeded uniform mix of depths 1–5.
        Each chart has 12 topology components and 10 inputs. Component types, original wiring,
        gate ordering, valid input domain and fault placements stay fixed within each family.
        Gate paths use a separate seeded stream; deeper profiles take longer prefixes
        of the same ordering. Structural bodies may already contain branches:
        the reported depth counts the **added outer gates**.
        Input constraints remain global even when a component's resources are gated off.

        Trimming stays at level 2; the matrix compares random trimming, topology trimming,
        both together, and each with failure expansion off/on. Errors occupy 5% of valid
        assignments (rounded down), fault seed 1729; topology and selection seed 2026.
        Automatic exhaustive promotion and inferred groups are disabled so strength eight
        is actually exercised. Complete populations are rendered separately for ground truth.
        Expansion only revisits omitted members of that strength-eight plan.
        Strength eight describes the unfiltered plan; trimming can remove that coverage.

        ![Policy matrix](matrix.png)

        ## Shared PCA frames

        Each family has **one PCA fit pooled across all three complete depth profiles**.
        Its coordinates, axis limits and marker-size scale stay fixed before/after filtering
        and across shallow/deep/random rows. Axes are comparable within a family,
        not between families.
        Full-population panels show the chart's output geometry; strength-eight panels show
        what the planner samples before filtering. The added error ConfigMap is
        included in the features.
        PCA can overlap distinct outputs and discards variance; labels report retained variance.

        ![Supported mixtures before expansion](pca-supported-unexpanded.png)

        ![Supported mixtures after expansion](pca-supported-expanded.png)

        ![Uniform mixtures before expansion](pca-uniform-unexpanded.png)

        ![Uniform mixtures after expansion](pca-uniform-expanded.png)

        ## Recorded fixture depths

        | Fixture | Component gate depths | Planned inputs / full population |
        |---|---|---|
        """).lstrip("\n")
    for ref in references:
        spec = mapping(json.loads((output / "charts" / str(ref["structure"]) / "benchmark.json").read_text()))
        components = sequence(mapping(spec["structure"])["components"])
        depths = ", ".join(str(mapping(component)["gate_depth"]) for component in components)
        text += f"| {ref['structure']} | {depths} | {mapping(ref['planning'])['planned_inputs']}/{ref['valid_inputs']} |\n"
    text += dedent(f"""

        Helm `{metadata["helm"]}`. Every reference render is checked against an independent
        manifest and fault oracle. Policies replay their selected reference observations;
        added expansion inputs are physically rendered again. Reference plus all added
        renders share a {metadata["time_limit_seconds"]:g}s ceiling per fixture,
        excluding planning/PCA.
        These are matched coverage comparisons, not independent end-to-end timings.
        Exact output coverage, input recall, additional renders and remaining work are in the CSV.
        One fixed seed does not establish a universal best topology or filtering setting.

        [Raw observations and pooled PCA bases](results.json) · [CSV](results.csv)

        ```sh
        hypothesis-helm-benchmark nesting --permutations 8 \\
          --time-limit 9m --output reports/nesting
        ```
        """)
    (output / "README.md").write_text(text)

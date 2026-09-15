"""
Publish complete compiler graph figures and mathematical invariants for each chart.
"""

import csv
import gzip
import json
import sys
from collections import Counter
from pathlib import Path
from textwrap import dedent

import matplotlib
from hypothesis_helm.benchmarking.reporting.descriptions import describe

matplotlib.use("Agg")
from matplotlib import pyplot as plt

root = Path(sys.argv[1])
output = root / "outputs/chart-topologies"
inventory = json.loads((root / "topology-inventory.json").read_text())
rows = []
for item in inventory:
    directory = Path(item["output"])
    metrics_path = directory / "metrics.json"
    base = {
        "repository": item["repository"],
        "chart": item["chart"],
        "source": item["source"],
        "directory": str(directory.relative_to(output)),
    }
    if metrics_path.exists():
        metrics = json.loads(metrics_path.read_text())
        kinds = metrics["node_kinds"]
        base.update(
            status="rendered" if metrics["baseline"]["status"] == "rendered" else "static-only",
            vertices=metrics["vertices"],
            edges=metrics["edges"],
            weak_components=metrics["weak_components"],
            undirected_cycle_rank=metrics["edges"] - metrics["vertices"] + metrics["weak_components"],
            values=kinds.get("value", 0),
            templates=kinds.get("template", 0),
            manifests=kinds.get("manifest", 0),
            manifest_fields=kinds.get("manifest-field", 0),
            longest_dependency_chain=metrics["longest_dependency_chain_edges"],
            unresolved=metrics["unresolved_accesses"],
        )
        assert base["undirected_cycle_rank"] >= 0
        metrics["underlying_undirected_multigraph_cycle_rank"] = base["undirected_cycle_rank"]
        metrics["cycle_rank_contract"] = (
            "E - V + C for the one-dimensional underlying undirected multigraph; parallel references count separately. "
            "This is not template branch count or evidence of a bug."
        )
        metrics_path.write_text(json.dumps(metrics, indent=2) + "\n")
        diagram = (
            "![Full directed dependency multigraph](topology.png)\n\n[Vector graph](topology.svg) · [Graph "
            "JSON](graph.json.gz) · [DOT](graph.dot.gz) · [Coordinates](positions.csv.gz) · [Invariants](metrics.json)"
        )
    else:
        status_path = directory / "status.json"
        status = (
            json.loads(status_path.read_text())
            if status_path.exists()
            else {"status": "incomplete", "reason": "Graph job did not finish; inspect the retained job log and diagnostics."}
        )
        base.update(status=status["status"])
        directory.mkdir(parents=True, exist_ok=True)
        diagram = status.get("reason", "Graph unavailable; inspect retained diagnostics.")
    (directory / "README.md").write_text(
        dedent(f"""
        # {directory.relative_to(output).as_posix()}

        [All chart topologies]({"../" * len(directory.relative_to(output).parts)}README.md)

        Status: **{base["status"]}**. Source: `{item["source"]}`.
        Potential references are not proof of exact input-to-output causality.
        Baseline-unavailable graphs contain static evidence only.

        """).lstrip()
        + diagram
        + "\n"
    )
    rows.append(base)
    for name in ["graph.json", "graph.dot", "positions.csv", "audit.json"]:
        path = directory / name
        if path.exists():
            data = path.read_bytes()
            compressed = gzip.compress(data, mtime=0)
            assert gzip.decompress(compressed) == data
            path.with_suffix(path.suffix + ".gz").write_bytes(compressed)
            path.unlink()
fields = [
    "repository",
    "chart",
    "status",
    "vertices",
    "edges",
    "weak_components",
    "undirected_cycle_rank",
    "values",
    "templates",
    "manifests",
    "manifest_fields",
    "longest_dependency_chain",
    "unresolved",
    "directory",
    "source",
]
with (output / "results.csv").open("w", newline="") as stream:
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
(output / "results.json").write_text(
    json.dumps(
        {
            "source_revisions": json.loads((root / "provenance.json").read_text())["source_revisions"],
            "charts": rows,
            "contract": "Exact invariants of the exported graph, not a claim that all runtime dependencies are statically known.",
        },
        indent=2,
    )
    + "\n"
)
figure, axes = plt.subplots(1, 2, figsize=(13, 5.5))
for repo, color in [("bitnami", "#0072B2"), ("prometheus", "#D55E00"), ("synthetic", "#009E73")]:
    values = [row for row in rows if row["repository"] == repo and row.get("vertices", 0) > 0]
    if not values:
        continue
    axes[0].scatter([row["vertices"] for row in values], [max(1, row["edges"]) for row in values], label=repo, color=color, alpha=0.65)
    axes[1].scatter(
        [row["vertices"] for row in values], [row["undirected_cycle_rank"] for row in values], label=repo, color=color, alpha=0.65
    )
axes[0].set(xscale="log", yscale="log", xlabel="Vertices", ylabel="Edges (zero shown at 1)", title="Complete exported graph size")
axes[1].set(
    xscale="log",
    yscale="symlog",
    xlabel="Vertices",
    ylabel="Undirected multigraph cycle rank (E − V + C)",
    title="Independent cycles in the underlying graph",
)
axes[1].set_ylim(bottom=0)
for axis in axes:
    axis.legend()
    axis.grid(alpha=0.2)
figure.suptitle("Compiler graph invariants - every exported vertex and edge retained")
figure.tight_layout(rect=(0, 0, 1, describe(figure, "graph-invariants")))
figure.savefig(output / "graph-invariants.png", dpi=170)
figure.savefig(output / "graph-invariants.svg")
plt.close(figure)
counts = Counter(row["status"] for row in rows)
lines = [
    "# Chart topology graphs",
    "",
    "[Benchmarking](../../benchmarks/README.md)",
    "",
    f"{len(rows)} charts: "
    f"{counts['rendered']} graphs with rendered baselines, "
    f"{counts['static-only']} static-only graphs, and "
    f"{counts['missing-values']} chart without a values file. Verification checks account for "
    f"every exported vertex and edge.",
    "",
    "These are directed multigraphs G = (V, E) from the compiler, rendered with Matplotlib. Every exported vertex and "
    "edge is retained, including parallel references; overlapping marks are not removed.",
    "",
    "Vertices represent values, control flow, templates, manifests, and manifest fields. Edges retain the compiler’s "
    "potential-reference, condition, control-flow, observed-render, and containment relations. PNG/SVG drawings and "
    "per-vertex coordinate tables accompany the full JSON/DOT graphs.",
    "",
    "The horizontal rank is the longest directed dependency path from a source; vertical placement orders parents "
    "deterministically. Geometry is a drawing layout, not output distance or PCA. Dependency-chain length is not template nesting depth.",
    "",
    "C is the number of weak components. The cycle rank E − V + C is the first Betti number of the one-dimensional "
    "underlying undirected multigraph. Parallel reference edges count separately. These invariants do not measure bug "
    "count or prove runtime influence. Opaque template access remains unresolved.",
    "",
    "A rendered baseline is one observation. Static-only graphs could not obtain that baseline; missing-values and "
    "incomplete jobs are explicit. No unknown edges are invented.",
    "",
    "![Graph size and cycle rank](graph-invariants.png)",
    "",
    "[CSV table](results.csv) · [JSON inventory](results.json) · [Vector overview](graph-invariants.svg)",
    "",
    "| Repository | Chart | Baseline / export | V | E | C | Cycle rank |",
    "| --- | --- | --- | ---: | ---: | ---: | ---: |",
]
for row in rows:
    lines.append(
        f"| "
        f"{row['repository']} | "
        f"[{row['chart']}]({row['directory']}/README.md) | "
        f"{row['status']} | "
        f"{row.get('vertices', 'N/A')} | "
        f"{row.get('edges', 'N/A')} | {row.get('weak_components', 'N/A')} | {row.get('undirected_cycle_rank', 'N/A')} |"
    )
lines.extend(["", "Source revisions:", ""])
for repo, commit in json.loads((root / "provenance.json").read_text())["source_revisions"].items():
    lines.append(f"- {repo}: `{commit}`")
lines.extend(
    [
        "",
        "Graph JSON, DOT and coordinate tables are losslessly gzip-compressed. Decode with `gzip -dc FILE.gz`; the "
        "plotting CLI accepts the decoded JSON. Dependency preparation uses isolated chart copies. Baseline rendering "
        "is not Kubernetes API schema validation.",
        "",
    ]
)
(output / "README.md").write_text("\n".join(lines))
print(dict(Counter(row["status"] for row in rows)))

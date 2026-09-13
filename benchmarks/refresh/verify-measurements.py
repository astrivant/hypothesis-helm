"""
Validate completed study ledgers before publication.
"""

import json
import sys
from collections import Counter
from pathlib import Path

from attrs import asdict
from hypothesis_helm.benchmarking.benchmark_matrix import STRATEGIES
from hypothesis_helm.benchmarking.stress import Stress, progression
from hypothesis_helm.charts import yamlio

root = Path(sys.argv[1])
expected = json.loads((root / "provenance.json").read_text())["code_sha256"]
summary = {}
for study in [
    "performance",
    "discovery",
    "bug-density",
    "sparsity",
    "topology-sparsity",
    "matrix",
    "pca",
    "expansion",
    "topology-depth",
    "nesting",
    "stress",
    "sampling",
]:
    directory = root / "outputs" / study
    result = json.loads((directory / "results.json").read_text())
    metadata = result["metadata"]
    if "code_sha256" in metadata:
        assert metadata["code_sha256"] == expected, study
    assert "v4." in metadata.get("helm", metadata.get("helm_version", "")), (study, list(metadata))
    rows = result.get("points", result.get("rows", result.get("runs", [])))
    assert rows, study
    statuses = Counter(row.get("status", "unreported") for row in rows)
    assert set(statuses) <= ({"passed", "time-limit"} if study in {"performance", "stress"} else {"passed", "complete"}), (study, statuses)
    if study == "sampling":
        reference = result["reference"]
        assert result["status"] == "complete" and reference["remaining"] == 0, "Sampling requires a complete reference"
        assert reference["completed"] == metadata["valid_inputs"] == len(reference["fault_masks"]), "Incomplete fault inventory"
        assert all(0 < row["sample_size"] < reference["completed"] for row in rows), "Invalid sample size"
        for filename in ("results.csv", "README.md", "chart-parameters.yaml", "sampling-recall.png", "sampling-recall.svg"):
            assert (directory / filename).is_file(), filename
    if study == "stress":
        steps = progression(Stress())
        expected_rows = {(step, strategy) for step in range(len(steps)) for strategy in STRATEGIES}
        assert len(rows) == len(expected_rows), "Stress refresh must contain every step and strategy"
        assert {(row["step"], row["strategy"]) for row in rows} == expected_rows, "Missing or duplicate stress measurements"
        assert metadata["time_limit_seconds"] == 540 and metadata["time_limit_scope"] == "per strategy per step"
        for row in rows:
            name, settings = steps[row["step"]]
            assert row["case"] == name and row["parameters"] == asdict(settings), row["case"]
            assert row["error"] is None, row["case"]
            assert 0 <= row["completed"] <= row["selected"], row["case"]
            assert row["remaining"] == row["selected"] - row["completed"], row["case"]
            assert row["status"] != "passed" or row["remaining"] == 0, row["case"]
            recipe = yamlio.load((directory / "cases" / f"{name}.yaml").read_text())
            assert recipe["parameters"]["stress"] == asdict(settings), name
        for filename in ("results.csv", "README.md", "topology-stress.png", "topology-stress.svg"):
            assert (directory / filename).is_file(), filename
        assert not list(directory.rglob("Chart.yaml")), "Stress results must retain recipes, not duplicate charts"
    references = result.get("references", [])
    assert all(row["status"] == "complete" for row in references), study
    figures = list(directory.glob("*.png"))
    assert figures, study
    for figure in figures:
        assert figure.stat().st_size > 1000
    vectors = list(directory.glob("*.svg"))
    assert vectors and all(figure.stat().st_size > 1000 for figure in vectors), study
    summary[study] = {
        "rows": len(rows),
        "statuses": dict(statuses),
        "references": len(references),
        "figures": len(figures),
        "vector_figures": len(vectors),
    }
(root / "measurement-verification.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))

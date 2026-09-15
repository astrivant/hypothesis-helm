"""
Validate completed study ledgers before publication.
"""

import json
import sys
from collections import Counter
from pathlib import Path

from attrs import asdict
from hypothesis_helm.benchmarking.charts.stress import Stress, progression
from hypothesis_helm.benchmarking.charts.structures import STRUCTURES
from hypothesis_helm.benchmarking.refresh.plan import STUDIES
from hypothesis_helm.benchmarking.studies.error_surface import METHODS, METRICS, RATES, verify
from hypothesis_helm.benchmarking.studies.matrix import STRATEGIES
from hypothesis_helm.benchmarking.studies.structural_sparsity import verify as verify_structural_sparsity
from hypothesis_helm.charts import yamlio

root = Path(sys.argv[1])
expected = json.loads((root / "provenance.json").read_text())["code_sha256"]
summary = {}
for study in STUDIES:
    directory = root / "outputs" / study
    result = json.loads((directory / "results.json").read_text())
    metadata = result["metadata"]
    if "code_sha256" in metadata:
        assert metadata["code_sha256"] == expected, study
    assert "v4." in metadata.get("helm", metadata.get("helm_version", "")), (study, list(metadata))
    rows = result.get("points", result.get("rows", result.get("runs", [])))
    assert rows, study
    statuses = Counter(row.get("status", "unreported") for row in rows)
    assert set(statuses) <= (
        {"passed", "time-limit"}
        if study in {"performance", "stress", "filtering", "error-surface", "structural-sparsity"}
        else {"passed", "complete"}
    ), (
        study,
        statuses,
    )
    if study == "matrix":
        expected_rows = {(structure, strategy) for structure in STRUCTURES for strategy in STRATEGIES}
        assert len(rows) == len(expected_rows) and {(row["structure"], row["strategy"]) for row in rows} == expected_rows
    if study == "structural-sparsity":
        verify_structural_sparsity(result)
        for suffix in ("runtime", "discovery", "analysis", "errors"):
            for extension in ("png", "svg"):
                assert (directory / f"structural-sparsity-{suffix}.{extension}").is_file()
    if study == "pca":
        expected_strategies = {"before", "random", "topology", "combined", "filter", "filter-adaptive"}
        assert {row["structure"] for row in rows} == set(STRUCTURES) and len(rows) == len(STRUCTURES)
        assert all(set(row["strategies"]) == expected_strategies for row in rows)
        assert all(set(row["selected_indices"]) == expected_strategies for row in rows)
    if study in {"expansion", "nesting"}:
        structures = (
            set(STRUCTURES)
            if study == "expansion"
            else {f"{family}-{profile}" for family in ("uniform", "supported") for profile in ("shallow", "deep", "random")}
        )
        expected_rows = {
            (structure, strategy, expanded)
            for structure in structures
            for strategy in ("before", "random", "topology", "combined", "filter", "filter-adaptive")
            for expanded in (False, True)
        }
        assert len(rows) == len(expected_rows)
        assert {(row["structure"], row["strategy"], row["expand_failures"]) for row in rows} == expected_rows
    if study == "filtering":
        assert metadata["status"] == "complete" and metadata["repeats"] == 2
        expected_rows = {
            (fields, depth, repeat, method)
            for fields in (6, 7, 8, 9)
            for depth in (1, 3, 5)
            for repeat in range(2)
            for method in ("baseline", "sample-random", "filter", "filter-adaptive")
        }
        assert len(rows) == len(expected_rows)
        assert {(row["input_fields"], row["gate_depth"], row["repeat"], row["strategy"]) for row in rows} == expected_rows
        for row in rows:
            assert row["valid_inputs"] == 2 ** row["input_fields"]
            assert 0 <= row["completed"] <= row["planned"] <= row["valid_inputs"]
            assert row["remaining"] == row["planned"] - row["completed"]
            assert row["status"] != "passed" or row["remaining"] == 0
            assert row["wall_seconds"] >= row["planning_seconds"] + row["execution_seconds"]
            assert row["planning_seconds"] >= row["complexity_seconds"] >= 0
        for name in ("filtering-runtime", "filtering-planning", "filtering-completed", "filtering-phases"):
            assert (directory / f"{name}.png").is_file() and (directory / f"{name}.svg").is_file()
    if study == "error-surface":
        verify(result)
        assert metadata["methods"] == list(METHODS) and metadata["error_rates"] == list(RATES)
        assert metadata["input_fields"] == 8 and metadata["repeats"] == 3
        assert metadata["axes"] == {"depth": list(range(6)), "redundancy": list(range(8)), "clustering": [0, 0.5, 1]}
        for axis in metadata["axes"]:
            for metric in METRICS:
                for extension in ("png", "svg"):
                    assert (directory / f"{axis}-{metric.replace('_', '-')}.{extension}").is_file()
        assert (directory / "summary.csv").is_file()
    if study == "calibration-variation":
        calibration = json.loads((directory / "calibration.json").read_text())
        assert calibration["status"] == "complete" and len(calibration["profiles"]) == 30
        assert len(rows) == 180 and all(row["trials"] == 100 for row in rows)
        cases = {cell["case"] for cell in calibration["profiles"]}
        strategies = {"filter", "exact", "nearby-0.1", "nearby-0.2", "nearby-0.35", "nearby-0.5"}
        assert len(cases) == 30
        assert {(row["case"], row["strategy"]) for row in rows} == {(case, strategy) for case in cases for strategy in strategies}
        for cell in calibration["profiles"]:
            assert len(cell["reference"]["cases"]) + 1 == cell["evidence"]["reference_renders"]
        for filename in ("matrix.csv", "matrix.json", "MATRIX.md", "matching-matrix.png", "profile-variation.png"):
            assert (directory / filename).is_file(), filename
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

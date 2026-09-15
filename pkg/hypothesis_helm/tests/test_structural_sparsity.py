"""
Verify structural distances, fixed defect populations and shared-chart replay.
"""

import copy
import json
import shutil
from pathlib import Path

import pytest
from jsonschema import validate

from hypothesis_helm.benchmarking.charts.fixture import FixtureWorkspace, case_path, chart_path
from hypothesis_helm.benchmarking.charts.generator import generate, reproduce
from hypothesis_helm.benchmarking.charts.structural_sparsity import PLACEMENTS, configure, expected
from hypothesis_helm.benchmarking.studies.matrix import bundle_key, measure
from hypothesis_helm.benchmarking.studies.structural_sparsity import reference, verify
from hypothesis_helm.charts.model import Chart
from hypothesis_helm.schemas.contracts import mapping


@pytest.mark.parametrize("placement", PLACEMENTS)
def test_fixed_domain_and_graph_distances(tmp_path: Path, placement: str) -> None:
    """
    Change placement without changing tree size, valid inputs or the seven bad assignments.

    Args:
        tmp_path (Path): Isolated case recipes.
        placement (str): Active-field placement and projection connectivity.

    Returns:
        None: Schema, oracle and replay agree for every assignment.
    """
    logical = tmp_path / "charts" / placement
    with FixtureWorkspace() as workspace:
        generate(logical, input_complexity=4, output_bins=2, workspace=workspace)
        configure(logical, 4, 2, placement, 2026, workspace=workspace)
        chart = Chart.load(chart_path(logical, workspace=workspace))
        spec = mapping(json.loads((chart.path / "benchmark.json").read_text()))
        settings = mapping(spec["structural_sparsity"])
        assert settings["value_nodes"] == 29
        assert settings["max_path_distance"] == (2 if placement == "near" else 8)
        assert settings["projection_components"] == (2 if placement == "disconnected" else 1)
        identities, outcomes = reference(chart, spec)
        assert len(identities) == sum(outcomes.values()) == len(outcomes) == 16
        errors = 0
        for key in identities:
            values = json.loads(key)
            validate(values, chart.schema)
            resources = expected(values, spec)
            assert bundle_key(resources) in outcomes
            errors += any(mapping(resource["data"])["status"] == "incorrect" for resource in resources)
        assert errors == 7
        before = (chart.path / "templates/sparsity.yaml").read_bytes()
        exported = tmp_path / "exported"
        reproduced = reproduce(case_path(logical), exported)
        assert reproduced["structural_sparsity"] == settings
        assert (exported / "templates/sparsity.yaml").read_bytes() == before


def test_native_engine_and_publication_guard(tmp_path: Path) -> None:
    """
    Check every real Helm output and reject damaged measurement matrices.

    Args:
        tmp_path (Path): Isolated generated chart and results.

    Returns:
        None: Native execution finds both defects in exactly seven configurations.
    """
    helm = shutil.which("helm")
    if helm is None:
        pytest.skip("Helm is required for render verification")
    logical = tmp_path / "charts" / "far"
    with FixtureWorkspace() as workspace:
        generate(logical, input_complexity=4, output_bins=2, workspace=workspace)
        configure(logical, 4, 1, "far", 2026, workspace=workspace)
        chart = Chart.load(chart_path(logical, workspace=workspace))
        spec = mapping(json.loads((chart.path / "benchmark.json").read_text()))
        row = measure(
            chart,
            spec,
            "default",
            level=2,
            seed=2026,
            limit=10000,
            seconds=30,
            helm=helm,
            reference=reference(chart, spec),
            strength=4,
            manifest_oracle=expected,
        )
        assert row["status"] == "passed", row["error"]
        assert row["erroneous_inputs_evaluated"] == 7
        assert row["defects_found"] == ["defect-0", "defect-1"]
        row.update(breadth=4, depth=1, placement="far", repeat=0, errors_missed=0, value_nodes=25)
        document: dict[str, object] = {
            "metadata": {"status": "complete", "breadths": [4], "depths": [1], "placements": ["far"], "methods": ["default"], "repeats": 1},
            "rows": [row],
        }
        verify(document)
        broken = copy.deepcopy(document)
        broken["rows"] = []
        with pytest.raises(AssertionError):
            verify(broken)
        row["errors_missed"] = 1
        with pytest.raises(AssertionError):
            verify(document)

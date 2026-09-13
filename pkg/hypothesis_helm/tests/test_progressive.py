"""
Verify bounded progressive planning, union counts and machine-readable CLI output.
"""

import json
from pathlib import Path

import pytest

from hypothesis_helm.charts.runner import Chart, check_chart, merge_values
from hypothesis_helm.cli import main
from hypothesis_helm.reporting.progressive import duration_estimate
from hypothesis_helm.schemas.combinations import plan_interactions
from hypothesis_helm.schemas.contracts import configuration_key, mapping, sequence


def test_cli_plot_preserves_configured_enumeration(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    """
    Preview increasing strengths while preserving the configured exhaustive policy.

    Args:
        capsys (pytest.CaptureFixture[str]): Separates plot stderr from JSON stdout.
        tmp_path (Path): Unused artifact destination to check dry-run side effects.

    Returns:
        None: The complete configured plan and progressive distinct counts agree.
    """
    assert (
        main(
            [
                "test",
                "examples/workload",
                "--dry-run",
                "--artifact-dir",
                str(tmp_path),
            ]
        )
        == 0
    )
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    progression = report["progressive_estimate"]
    assert [stage["candidate_inputs"] for stage in progression["stages"]] == [9, 19, 24]
    assert progression["configured_run"]["candidate_inputs"] == 24
    assert report["coverage_strategy"] == "exhaustive"
    assert "Progressive dry-run forecast" in captured.err
    assert "10 additional inputs" in captured.err
    assert "unknown (no compatible" in captured.err
    assert list(tmp_path.iterdir()) == []


def test_large_full_run_remains_bounded() -> None:
    """
    Retain successful previews when higher-strength planning exceeds the case limit.

    Returns:
        None: Unavailable stages and heuristic totals do not claim exhaustive coverage.
    """
    report = check_chart(
        "examples/workload",
        permutations=1,
        dry_run=True,
        exhaustive_threshold=0,
        max_cases=20,
        infer_exhaustive_groups=False,
    )
    progression = mapping(report["progressive_estimate"])
    stages = [mapping(stage) for stage in sequence(progression["stages"])]
    assert stages[2]["status"] == "unavailable"
    full = mapping(progression["full_run"])
    assert full["status"] == "bounded"
    assert full["candidate_inputs_upper_bound"] == 25
    assert full["filter_forecast_renders_lower_bound"] == 1
    assert "heuristic_filter_forecast_renders" in full
    assert full["heuristic_estimated_seconds"] is None
    chart = Chart.load("examples/workload")
    cumulative: set[str] = set()
    for strength, stage in enumerate(stages[:2], 1):
        plan = plan_interactions(chart.schema, strength, exhaustive_threshold=0)
        inputs = {configuration_key(merge_values(chart.defaults, values)) for values in [{}, *plan.values]}
        assert stage["new_inputs"] == len(inputs - cumulative)
        cumulative.update(inputs)
        assert stage["cumulative_inputs"] == len(cumulative)


@pytest.mark.parametrize("cost", [None, -1, True, float("nan"), float("inf"), "1", 10**400])
def test_invalid_cost_profiles_remain_unknown(cost: object) -> None:
    """
    Reject incomplete or corrupt measurements instead of inventing a wall time.

    Args:
        cost (object): Unusable persisted renderer measurement.

    Returns:
        None: Only finite nonnegative numeric profiles can produce estimates.
    """
    assert (
        duration_estimate(
            8,
            3,
            {"cost_profile": {"seconds_per_render": cost, "seconds_per_check": 1}},
        )
        is None
    )
    assert (
        duration_estimate(
            8,
            3,
            {"cost_profile": {"seconds_per_render": 2, "seconds_per_check": 0.5}},
        )
        == 10
    )
    assert (
        duration_estimate(
            10**400,
            10**400,
            {"cost_profile": {"seconds_per_render": 2.0, "seconds_per_check": 0.5}},
        )
        is None
    )


def test_progression_advances_beyond_triples(tmp_path: Path) -> None:
    """
    Evaluate higher strengths instead of capping recommendations at three factors.

    Args:
        tmp_path (Path): Four-factor finite chart location.

    Returns:
        None: Strength four completes and matches the affordable full domain.
    """
    (tmp_path / "templates").mkdir()
    (tmp_path / "Chart.yaml").write_text("apiVersion: v2\nname: four\nversion: 0.1.0\n")
    defaults = dict.fromkeys(("a", "b", "c", "d"), False)
    (tmp_path / "values.yaml").write_text(json.dumps(defaults))
    (tmp_path / "values.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "additionalProperties": False,
                "required": list(defaults),
                "properties": {name: {"type": "boolean"} for name in defaults},
            }
        )
    )
    (tmp_path / "templates" / "config.yaml").write_text("apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: four\n")
    report = check_chart(tmp_path, permutations=2, dry_run=True, exhaustive_threshold=0)
    forecast = mapping(report["progressive_estimate"])
    stages = [mapping(stage) for stage in sequence(forecast["stages"])]
    assert [stage["strength"] for stage in stages] == [1, 2, 3, 4]
    assert stages[-1]["candidate_inputs"] == 16
    assert mapping(forecast["full_run"])["candidate_inputs"] == 16

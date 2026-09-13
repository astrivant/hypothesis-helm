"""
Verify interaction coverage against independent finite-domain oracles.
"""

import itertools
import json
from pathlib import Path

import pytest
from jsonschema import validators

from hypothesis_helm.charts.runner import Chart, check_chart
from hypothesis_helm.cli import main
from hypothesis_helm.schemas.combinations import plan_interactions
from hypothesis_helm.schemas.contracts import json_value
from hypothesis_helm.schemas.finite import NonFiniteSchema


def boolean_schema(count: int) -> dict[str, object]:
    """
    Build a closed schema with independent required boolean factors.

    Args:
        count (int): Number of factors.

    Returns:
        dict[str, object]: Finite object schema.
    """
    names = [f"flag_{index}" for index in range(count)]
    return {
        "type": "object",
        "additionalProperties": False,
        "required": names,
        "properties": dict.fromkeys(names, {"type": "boolean"}),
    }


@pytest.mark.parametrize("strength", [1, 2, 3, 4, 8])
def test_covers_every_feasible_interaction(strength: int) -> None:
    """
    Compare constrained coverage with a separately enumerated full domain.

    Args:
        strength (int): Requested interaction strength.

    Returns:
        None: Assertions verify coverage and constraint handling.
    """
    schema = boolean_schema(4)
    schema["if"] = {"properties": {"flag_0": {"const": True}}}
    schema["then"] = {"properties": {"flag_1": {"const": True}}}
    validator = validators.validator_for(schema)(schema)
    names = [f"flag_{index}" for index in range(4)]
    universe = [dict(zip(names, row, strict=True)) for row in itertools.product([False, True], repeat=4)]
    valid = [row for row in universe if validator.is_valid(json_value(row))]
    plan = plan_interactions(schema, strength, exhaustive_threshold=0)
    assert all(validator.is_valid(json_value(row)) for row in plan.values)
    interactions = 0
    for group in itertools.combinations(names, min(strength, 4)):
        expected = {tuple(row[name] for name in group) for row in valid}
        actual = {tuple(row[name] for name in group) for row in plan.values}
        assert actual == expected
        interactions += len(expected)
    assert plan.interactions == interactions
    assert plan.values == plan_interactions(schema, strength, exhaustive_threshold=0).values


def test_large_product_stays_bounded() -> None:
    """
    Cover thirty boolean factors without allocating their billion-row product.

    Returns:
        None: Assertions verify every pair and bounded planning work.
    """
    plan = plan_interactions(boolean_schema(30), 2)
    assert len(plan.values) < 1000
    assert plan.candidates < 1000
    for left, right in itertools.combinations(range(30), 2):
        assert {(row[f"flag_{left}"], row[f"flag_{right}"]) for row in plan.values} == {
            (False, False),
            (False, True),
            (True, False),
            (True, True),
        }


def test_nested_and_optional_factors() -> None:
    """
    Retain nested leaf combinations and distinguish omission from explicit values.

    Returns:
        None: Assertions verify the declared factor domains.
    """
    plan = plan_interactions(Chart.load("examples/workload").schema, 3)
    assert len(plan.values) == 24
    assert plan.factors == [("replicas",), ("image", "repository"), ("image", "tag")]
    optional = boolean_schema(2)
    optional["required"] = ["flag_0"]
    assert len(plan_interactions(optional, 2).values) == 6
    empty = {"type": "object", "additionalProperties": False}
    assert plan_interactions(empty, 2).values == [{}]


@pytest.mark.parametrize(
    ("strength", "max_cases", "max_candidates"),
    [(0, 1000, 100000), (2, 1, 100000), (2, 2, 100000), (2, 1000, 1), (2, 1000, 0)],
)
def test_limits_refuse_partial_coverage(strength: int, max_cases: int, max_candidates: int) -> None:
    """
    Reject invalid or insufficient budgets instead of returning partial coverage.

    Args:
        strength (int): Requested interaction strength.
        max_cases (int): Suite and factor size limit.
        max_candidates (int): Planning work limit.

    Returns:
        None: The planner raises for every insufficient budget.
    """
    with pytest.raises(ValueError):
        plan_interactions(boolean_schema(4), strength, max_cases=max_cases, max_candidates=max_candidates)


def test_unbounded_domain_requires_explicit_bounds() -> None:
    """
    Refuse arbitrary strings rather than claim coverage of sampled representatives.

    Returns:
        None: The diagnostic identifies the unsupported factor.
    """
    schema = boolean_schema(1)
    schema["properties"] = {"flag_0": {"type": "string"}}
    with pytest.raises(NonFiniteSchema, match="flag_0"):
        plan_interactions(schema, 2)


def test_completion_limits_and_infeasible_schema() -> None:
    """
    Refuse incomplete searches and schemas with no feasible complete inputs.

    Returns:
        None: Assertions distinguish search exhaustion from proven infeasibility.
    """
    schema = boolean_schema(8)
    schema["not"] = {}
    with pytest.raises(NonFiniteSchema, match="completion search"):
        plan_interactions(schema, 2, max_candidates=112, exhaustive_threshold=0)
    with pytest.raises(NonFiniteSchema, match="no feasible"):
        plan_interactions(schema, 2)


@pytest.mark.parametrize("option", ["--collect-only", "--match", "--jobs"])
def test_cli_rejects_per_path_options(option: str, capsys: pytest.CaptureFixture[str]) -> None:
    """
    Prevent per-path controls from silently bypassing interaction execution.

    Args:
        option (str): Incompatible per-path option.
        capsys (pytest.CaptureFixture[str]): Captures structured errors.

    Returns:
        None: The command rejects unsupported combinations.
    """
    arguments = ["test", "examples/workload", "--permutations", "2", "--shard", "none", option]
    if option in ("--match", "--jobs"):
        arguments.append("2")
    assert main(arguments) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "error"


def test_cli_interactions_and_failure_report(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    """
    Render the interaction suite through the CLI and preserve failed coverage scope.

    Args:
        monkeypatch (pytest.MonkeyPatch): Restores the renderer after the test.
        capsys (pytest.CaptureFixture[str]): Captures CLI reports.
        tmp_path (Path): Destination for failure artifacts.

    Returns:
        None: Assertions verify dispatch, case accounting and failure reporting.
    """
    monkeypatch.setattr("hypothesis_helm.charts.runner.render", lambda *args, **kwargs: [{}])
    assert main(["test", "examples/workload", "--permutations", "2", "--shard", "none"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["mode"] == "permutations"
    assert report["coverage_complete"] is True
    assert report["attempts"] == report["planned_cases"] + 1
    assert "domain_size" not in report
    monkeypatch.setattr("hypothesis_helm.charts.runner.render", lambda *args, **kwargs: [])
    failed = check_chart("examples/workload", permutations=2, artifact_dir=tmp_path)
    assert failed["status"] == "failed"
    assert failed["coverage_complete"] is False
    assert json.loads((tmp_path / "report.json").read_text())["requested_strength"] == 2

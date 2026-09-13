"""
Verify automatic enumeration and evidence-based local exhaustive coverage.
"""

import itertools
import json
from pathlib import Path

import pytest
from jsonschema import validators

from hypothesis_helm.cli import main
from hypothesis_helm.schemas.combinations import plan_interactions
from hypothesis_helm.schemas.contracts import json_value
from hypothesis_helm.schemas.finite import NonFiniteSchema
from hypothesis_helm.schemas.groups import ExhaustiveGroup, infer_groups, parse_group
from hypothesis_helm.tests.test_combinations import boolean_schema


@pytest.mark.parametrize("sizes", [(9, 11, 101), (10, 10, 10, 10)])
def test_default_enumeration_threshold(sizes: tuple[int, ...]) -> None:
    """
    Enumerate 9,999 combinations and use interaction coverage at exactly 10,000.

    Args:
        sizes (tuple[int, ...]): Independent finite integer domain sizes.

    Returns:
        None: The strict threshold is respected without constructing the larger full suite.
    """
    schema = boolean_schema(len(sizes))
    schema["properties"] = {f"flag_{index}": {"type": "integer", "minimum": 0, "maximum": size - 1} for index, size in enumerate(sizes)}
    plan = plan_interactions(schema, 2)
    if len(sizes) == 3:
        assert plan.strategy == "exhaustive"
        assert len(plan.values) == 9999
    else:
        assert plan.strategy == "interactions"
        assert len(plan.values) < 10000


def test_targeted_group_covers_a_missing_triple() -> None:
    """
    Cover all triples in a selected group while retaining global pairwise coverage.

    Returns:
        None: The targeted group adds combinations that the pairwise suite misses.
    """
    schema = boolean_schema(8)
    baseline = plan_interactions(schema, 2, exhaustive_threshold=0)
    names = ["flag_0", "flag_1", "flag_2"]
    assert not any(all(row[name] for name in names) for row in baseline.values)
    grouped = plan_interactions(
        schema,
        2,
        exhaustive_threshold=0,
        exhaustive_groups=(parse_group(",".join(names)),),
    )
    assert {tuple(row[name] for name in names) for row in grouped.values} == set(itertools.product([False, True], repeat=3))
    for left, right in itertools.combinations(range(8), 2):
        assert {(row[f"flag_{left}"], row[f"flag_{right}"]) for row in grouped.values} == set(itertools.product([False, True], repeat=2))
    assert grouped.group_reports[0]["status"] == "exhaustive"


def test_group_constraints_have_valid_completions() -> None:
    """
    Compare a constrained targeted group with all feasible full configurations.

    Returns:
        None: Invalid group assignments are excluded without losing valid assignments.
    """
    schema = boolean_schema(5)
    schema["if"] = {"properties": {"flag_0": {"const": True}}}
    schema["then"] = {"properties": {"flag_3": {"const": True}, "flag_1": {"const": False}}}
    plan = plan_interactions(
        schema,
        2,
        exhaustive_threshold=0,
        exhaustive_groups=(parse_group("flag_0,flag_1,flag_2"),),
    )
    validator = validators.validator_for(schema)(schema)
    universe = [{f"flag_{index}": value for index, value in enumerate(row)} for row in itertools.product([False, True], repeat=5)]
    expected = {tuple(row[f"flag_{index}"] for index in range(3)) for row in universe if validator.is_valid(json_value(row))}
    assert {tuple(row[f"flag_{index}"] for index in range(3)) for row in plan.values} == expected
    assert all(validator.is_valid(json_value(row)) for row in plan.values)


def test_inference_uses_guards_dependencies_and_reports_unknowns(tmp_path: Path) -> None:
    """
    Infer scoped template groups and keep separate dependencies from merging transitively.

    Args:
        tmp_path (Path): Chart directory containing template evidence.

    Returns:
        None: Candidate groups retain source locations and unresolved context diagnostics.
    """
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "resource.yaml").write_text(
        "{{ $svc := .Values.service }}\n"
        "{{ if .Values.ingress.enabled }}\n"
        "{{ if .Values.tls.enabled }}\n"
        "{{ $svc.type }}\n{{ end }}\n{{ end }}\n"
        '{{ include "dynamic.helper" . }}\n'
    )
    schema = boolean_schema(3)
    schema["dependentRequired"] = {"flag_0": ["flag_1"], "flag_1": ["flag_2"]}
    groups, diagnostics = infer_groups(tmp_path, schema)
    template = [group for group in groups if group.source.startswith("template:")]
    assert any(set(group.paths) == {("ingress", "enabled"), ("tls", "enabled"), ("service", "type")} for group in template)
    dependencies = [group for group in groups if "dependentRequired" in group.source]
    assert {group.paths for group in dependencies} == {
        (("flag_0",), ("flag_1",)),
        (("flag_1",), ("flag_2",)),
    }
    assert diagnostics
    assert any("include" in str(item["message"]) for item in diagnostics)


def test_group_limits_are_explicit_and_required_groups_cannot_be_skipped() -> None:
    """
    Bound inferred groups while refusing unsatisfied explicit coverage requests.

    Returns:
        None: Skipped inference is reported and user-required groups fail closed.
    """
    schema = boolean_schema(8)
    paths = tuple((f"flag_{index}",) for index in range(7))
    inferred = ExhaustiveGroup(paths, "template:large:1")
    plan = plan_interactions(
        schema,
        2,
        exhaustive_threshold=0,
        exhaustive_groups=(inferred,),
        max_group_cases=8,
    )
    assert plan.group_reports[0]["status"] == "skipped"
    assert "limit" in str(plan.group_reports[0]["reason"])
    with pytest.raises(NonFiniteSchema, match="suite exceeds"):
        plan_interactions(
            schema,
            2,
            exhaustive_threshold=0,
            max_cases=10,
            exhaustive_groups=(ExhaustiveGroup(paths, "user", True),),
        )
    with pytest.raises(NonFiniteSchema, match="no finite factors"):
        plan_interactions(
            schema,
            2,
            exhaustive_groups=(parse_group("flag_0,unknown"),),
        )


def test_automatic_dry_run_is_read_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """
    Select exhaustive coverage by default and expose counts without rendering or persistence.

    Args:
        tmp_path (Path): Parent of the prospective artifact directory.
        monkeypatch (pytest.MonkeyPatch): Prevents renderer execution.
        capsys (pytest.CaptureFixture[str]): Captures JSON and diagnostic output.

    Returns:
        None: Automatic dry runs report the correct mode and leave the filesystem unchanged.
    """

    def render(*args: object, **kwargs: object) -> None:
        """
        Fail if a supposedly read-only plan invokes Helm.

        Args:
            *args (object): Renderer positional arguments.
            **kwargs (object): Renderer options.

        Returns:
            None: This boundary must not be reached.
        """
        raise AssertionError("dry run invoked Helm")

    monkeypatch.setattr("hypothesis_helm.charts.runner.render", render)
    target = tmp_path / "reports"
    assert main(["test", "examples/workload", "--dry-run", "--artifact-dir", str(target)]) == 0
    output = capsys.readouterr()
    report = json.loads(output.out)
    assert report["status"] == "dry-run"
    assert report["coverage_strategy"] == "exhaustive"
    assert report["planned_cases"] == 23
    assert report["planned_iterations"] == report["remaining_iterations"] == 24
    assert report["completed_iterations"] == 0
    assert "planning candidates" in output.err
    assert not target.exists()


def test_atomic_group_descendants_must_exist() -> None:
    """
    Reject misspelled descendants instead of accepting their optional parent factor.

    Returns:
        None: Only existing descendants resolve to the atomic optional object.
    """
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["enabled"],
        "properties": {
            "enabled": {"type": "boolean"},
            "service": {
                "type": "object",
                "additionalProperties": False,
                "required": ["port"],
                "properties": {"port": {"enum": [80, 443]}},
            },
        },
    }
    plan = plan_interactions(schema, 2, exhaustive_groups=(parse_group("enabled,service.port"),))
    assert plan.group_reports[0]["status"] == "exhaustive"
    with pytest.raises(NonFiniteSchema, match="no finite factors"):
        plan_interactions(schema, 2, exhaustive_groups=(parse_group("enabled,service.typo"),))


def test_unbounded_default_keeps_per_path_testing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """
    Fall back transparently when an unbounded schema cannot support finite coverage.

    Args:
        monkeypatch (pytest.MonkeyPatch): Replaces generated-suite execution.
        capsys (pytest.CaptureFixture[str]): Captures the fallback reason.
        tmp_path (Path): Prospective artifact directory.

    Returns:
        None: The default command remains usable for unbounded chart schemas.
    """
    monkeypatch.setattr("hypothesis_helm.cli.generate_tests", lambda *a, **kw: {"tests": 1, "diagnostics": []})
    monkeypatch.setattr("hypothesis_helm.cli.run_suite", lambda *a, **kw: 0)
    assert main(["test", "examples/configmap", "--artifact-dir", str(tmp_path)]) == 0
    assert "finite automatic coverage unavailable" in capsys.readouterr().err

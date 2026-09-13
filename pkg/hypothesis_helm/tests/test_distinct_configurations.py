"""
Verify that finite coverage renders each normalized configuration only once.
"""

from pathlib import Path

import pytest

from hypothesis_helm.charts.runner import Chart, check_chart, merge_values
from hypothesis_helm.schemas.contracts import configuration_key
from hypothesis_helm.schemas.factors import factor_space


@pytest.mark.parametrize("exhaustive", [False, True])
def test_defaults_and_omitted_values_are_not_rendered_twice(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, exhaustive: bool) -> None:
    """
    Collapse omitted and explicit defaults while preserving genuinely distinct values.

    Args:
        monkeypatch (pytest.MonkeyPatch): Captures the effective values sent to the renderer.
        tmp_path (Path): Chart identity and result directory.
        exhaustive (bool): Select legacy enumeration or permutation coverage.

    Returns:
        None: Two distinct configurations produce exactly two renderer invocations.
    """
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"enabled": {"type": "boolean"}},
    }
    chart = Chart(tmp_path, schema, {"enabled": False})
    rendered: list[str] = []

    def render(chart: Chart, values: dict[str, object], **kwargs: object) -> list[dict[str, object]]:
        """
        Record normalized values without invoking Helm.

        Args:
            chart (Chart): Original schema and defaults.
            values (dict[str, object]): Selected values override.
            **kwargs (object): Renderer execution settings.

        Returns:
            list[dict[str, object]]: A resource accepted by the mocked boundary.
        """
        rendered.append(configuration_key(merge_values(chart.defaults, values)))
        return [{}]

    monkeypatch.setattr("hypothesis_helm.charts.runner.render", render)
    report = check_chart(
        chart,
        exhaustive=exhaustive,
        permutations=None if exhaustive else 2,
        infer_exhaustive_groups=False,
        artifact_dir=tmp_path / "reports",
    )
    assert report["status"] == "passed"
    assert len(rendered) == len(set(rendered)) == report["attempts"] == 2
    assert report["unique_configurations"] == 2
    assert report["duplicate_cases_removed"] == 2
    assert set(rendered) == {
        configuration_key({"enabled": False}),
        configuration_key({"enabled": True}),
    }
    if not exhaustive:
        assert report["candidate_cases"] == 4
        assert report["planned_iterations"] == report["completed_iterations"] == 2
        assert report["remaining_iterations"] == 0
        assert report["valid_interactions"] == 3


def test_configuration_identity_preserves_array_order_and_scalar_types() -> None:
    """
    Ignore mapping order without collapsing ordered arrays or different scalar representations.

    Returns:
        None: Only equivalent typed configuration maps share an identity.
    """
    assert configuration_key({"a": 1, "b": 2}) == configuration_key({"b": 2, "a": 1})
    assert configuration_key({"ports": [80, 443]}) != configuration_key({"ports": [443, 80]})
    assert configuration_key({"flag": True}) != configuration_key({"flag": 1})
    assert configuration_key({"value": 1}) != configuration_key({"value": 1.0})


def test_repeated_factor_values_do_not_create_duplicate_domains() -> None:
    """
    Deduplicate equivalent enum objects independently of their key order.

    Returns:
        None: Repeated factor values are represented by one candidate assignment.
    """
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["config"],
        "properties": {"config": {"enum": [{"a": 1, "b": 2}, {"b": 2, "a": 1}]}},
    }
    assert len(factor_space(schema).domains[0]) == 1

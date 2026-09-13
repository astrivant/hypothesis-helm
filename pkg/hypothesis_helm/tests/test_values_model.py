"""
Verify typed values fidelity and shared declarations across coverage analysis passes.
"""

from pathlib import Path
from typing import cast

import attrs
import pytest
from attrs import AttrsInstance
from jsonschema.exceptions import ValidationError

from hypothesis_helm.schemas.combinations import plan_interactions
from hypothesis_helm.schemas.factors import factor_space
from hypothesis_helm.schemas.groups import infer_groups, parse_group
from hypothesis_helm.schemas.model import Missing, ValuesModel


def test_nested_roundtrip_preserves_absence_null_and_original_keys() -> None:
    """
    Model nested values, arrays and keys that cannot be Python field identifiers.

    Returns:
        None: Typed values preserve exact keys and never synthesize missing defaults.
    """
    schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "service": {"type": "object", "properties": {"port": {"type": "integer"}}},
            "items": {
                "type": "array",
                "items": {"type": "object", "properties": {"enabled": {"type": "boolean"}}},
            },
            "nullish": {"type": ["string", "null"]},
            "omitted": {"type": "boolean", "default": True},
            "bad-key": {"type": "string"},
            "class": {"type": "integer"},
            "value_4": {"type": "string"},
            "values_extra": {"type": "boolean"},
        },
    }
    values: dict[str, object] = {
        "service": {"port": 443},
        "items": [{"enabled": False}],
        "nullish": None,
        "bad-key": "literal",
        "class": 2,
        "value_4": "collision",
        "values_extra": True,
        "undeclared": {"keep": [1, None]},
    }
    model = ValuesModel.from_schema(schema)
    typed = model.structure(values)
    assert attrs.has(type(typed))
    assert attrs.has(type(getattr(typed, "service", None)))
    assert isinstance(getattr(typed, "omitted", None), Missing)
    assert getattr(typed, "nullish", "wrong") is None
    assert model.unstructure(typed) == values
    service = model.reference(("service",)).target
    assert service is not None
    assert attrs.fields(cast(type[AttrsInstance], type(typed))).service.metadata["value_node"] is service
    assert model.reference(("items", "0", "enabled")).target is model.reference(("items", "*", "enabled")).target


def test_validation_remains_strict_and_schema_snapshot_is_owned() -> None:
    """
    Retain full-schema checks rather than allowing cattrs to coerce mismatched scalars.

    Returns:
        None: Invalid inputs fail, and edits to the source schema cannot mutate the model.
    """
    schema: dict[str, object] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["count"],
        "properties": {"count": {"type": "integer", "minimum": 2}},
    }
    model = ValuesModel.from_schema(schema)
    invalid: list[dict[str, object]] = [
        {"count": "2"},
        {"count": True},
        {"count": 1},
        {},
        {"count": 2, "extra": 1},
    ]
    for values in invalid:
        with pytest.raises(ValidationError):
            model.structure(values)
    assert model.unstructure(model.structure({}, validate=False)) == {}
    schema.clear()
    assert model.unstructure(model.structure({"count": 2})) == {"count": 2}


def test_analysis_passes_share_declared_field_identity(tmp_path: Path) -> None:
    """
    Bind schema and template relationships to the same fields used for finite factors.

    Args:
        tmp_path (Path): Chart template directory.

    Returns:
        None: Shared identities survive inference and typed candidate generation.
    """
    schema: dict[str, object] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["enabled", "service"],
        "properties": {
            "enabled": {"type": "boolean"},
            "service": {
                "type": "object",
                "additionalProperties": False,
                "required": ["port"],
                "properties": {"port": {"enum": [80, 443]}},
            },
        },
        "dependentRequired": {"enabled": ["service"]},
    }
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "service.yaml").write_text("{{ if .Values.enabled }}\n{{ .Values.service.port }}\n{{ end }}")
    model = ValuesModel.from_schema(schema)
    space = factor_space(model)
    groups, _ = infer_groups(tmp_path, model)
    port = model.reference(("service", "port")).target
    assert port is not None and port.python_type is int
    assert space.nodes[1] is port
    assert any(ref.target is port for group in groups for ref in group.references)
    assert model.relationships[0].references[0].target is space.nodes[0]
    plan = plan_interactions(model, 2, exhaustive_groups=tuple(groups))
    assert len(plan.values) == 4
    assert {row["enabled"] for row in plan.values} == {False, True}


def test_atomic_enum_and_array_selectors_resolve_against_model() -> None:
    """
    Resolve enum object descendants and array indices without inspecting generated plans.

    Returns:
        None: Known selectors resolve and invalid array indices remain unresolved.
    """
    schema: dict[str, object] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["enabled"],
        "properties": {
            "enabled": {"type": "boolean"},
            "service": {"enum": [{"port": 80}, {"port": 443}]},
            "items": {"type": "array", "maxItems": 1, "items": {"type": "boolean"}},
        },
    }
    model = ValuesModel.from_schema(schema)
    assert model.reference(("service", "port")).target is not None
    assert model.reference(("service", "typo")).target is None
    assert model.reference(("items", "0")).target is not None
    assert model.reference(("items", "1")).target is None
    plan = plan_interactions(model, 2, exhaustive_groups=(parse_group("enabled,service.port"),))
    assert plan.group_reports[0]["status"] == "exhaustive"


def test_enum_arrays_and_literal_keys_keep_planning_behavior() -> None:
    """
    Preserve finite planning for enum arrays and fields requiring Python aliases.

    Returns:
        None: Typed construction retains original keys and atomic descendant selectors.
    """
    schema: dict[str, object] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["bad-key", "class"],
        "properties": {
            "bad-key": {"type": "boolean"},
            "class": {"type": "boolean"},
            "array": {"enum": [[], [{"port": 80}], [{"port": 443}]]},
        },
    }
    model = ValuesModel.from_schema(schema)
    assert model.reference(("array", "0", "port")).target is not None
    assert model.reference(("array", "1", "port")).target is None
    plan = plan_interactions(model, 2, exhaustive_groups=(parse_group("bad-key,array.0.port"),))
    assert len(plan.values) == 16
    assert all("bad-key" in row and "class" in row for row in plan.values)

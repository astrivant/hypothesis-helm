"""
Verify that context generation only resolves guards implied by the schema.
"""

import copy

import pytest
from jsonschema import validators

from hypothesis_helm.schemas.contracts import json_value
from hypothesis_helm.schemas.dialects import DRAFT4, DRAFT7, DRAFT2020
from hypothesis_helm.schemas.generation.conditionals import fixed_branches


@pytest.mark.parametrize("version", [DRAFT4, DRAFT7, DRAFT2020])
@pytest.mark.parametrize("required", [False, True])
@pytest.mark.parametrize("fixed", [False, True])
def test_fixed_guard_preserves_acceptance(version: str, required: bool, fixed: bool) -> None:
    """
    Compare validators before and after simplifying guards over literal properties.

    Args:
        version (str): Dialect controlling whether const and conditional keywords apply.
        required (bool): Whether the discriminator is guaranteed to exist.
        fixed (bool): Whether its value is fixed or may change between candidates.

    Returns:
        None: The transformation preserves acceptance and never mutates the input schema.
    """
    schema: dict[str, object] = {
        "$schema": version,
        "type": "object",
        "properties": {"enabled": {"const": False} if fixed else {"type": "boolean"}},
        "required": ["enabled"] if required else [],
        "allOf": [
            {
                "if": {"properties": {"enabled": {"const": True}}},
                "then": {"properties": {"entries": {"type": "array"}}},
                "else": {"properties": {"entries": {"type": "object"}}},
            }
        ],
    }
    original = copy.deepcopy(schema)
    simplified = fixed_branches(schema)
    before = validators.validator_for(schema)(schema)
    after = validators.validator_for(simplified)(simplified)
    entries_options: tuple[object, ...] = ([], {}, None, "x")
    for enabled in (None, True, False, 0, "x"):
        for entries in entries_options:
            candidate = {"entries": entries} if enabled is None else {"enabled": enabled, "entries": entries}
            assert before.is_valid(json_value(candidate)) == after.is_valid(json_value(candidate))
    if not required or not fixed or version == DRAFT4:
        assert simplified == schema
    assert schema == original


def test_parent_literals_do_not_resolve_nested_property_guards() -> None:
    """
    Keep child-object conditions independent from identically named parent fields.

    Returns:
        None: Root facts never escape into another object or into non-object instances.
    """
    schema: dict[str, object] = {
        "type": "object",
        "required": ["enabled"],
        "properties": {
            "enabled": {"const": False},
            "child": {"if": {"properties": {"enabled": {"const": True}}}, "then": False},
        },
    }
    assert fixed_branches(schema) == schema
    schema.pop("type")
    schema["if"] = {"properties": {"enabled": {"const": True}}}
    schema["then"] = False
    assert fixed_branches(schema) == schema

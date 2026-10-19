"""
Preserve shared schema references while freezing excluded dependency instances.
"""

from __future__ import annotations

import copy

import pytest
from hypothesis_helm.compiler.passes.dependencies import Dependencies
from hypothesis_helm.schemas.contracts import mapping, sequence
from jsonschema import Draft7Validator


@pytest.mark.parametrize("nested", [False, True])
@pytest.mark.parametrize("exclude_second", [False, True])
def test_dependency_freeze_does_not_change_referenced_schema(nested: bool, exclude_second: bool) -> None:
    """
    Keep one dependency's baseline from becoming another instance's input contract.

    Args:
        nested (bool): Place both dependency instances beneath an ordinary parent.
        exclude_second (bool): Freeze both instances, each with its own baseline.

    Returns:
        None: Baselines remain valid, excluded values stay frozen and source data is untouched.
    """
    prefix = ("parent",) if nested else ()
    pointer = "#/properties/parent/properties/first" if nested else "#/properties/first"
    properties: dict[str, object] = {
        "first": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
        "second": {"$ref": pointer},
    }
    schema: dict[str, object] = {"type": "object", "properties": properties, "required": ["first", "second"]}
    baseline: dict[str, object] = {"first": {"name": "first"}, "second": {"name": "second"}}
    if nested:
        schema = {"type": "object", "properties": {"parent": schema}, "required": ["parent"]}
        baseline = {"parent": baseline}
    schema["allOf"] = [{"type": "object"}]
    original_schema = copy.deepcopy(schema)
    original_baseline = copy.deepcopy(baseline)
    excluded = {(*prefix, "first")}
    if exclude_second:
        excluded.add((*prefix, "second"))
    dependencies = Dependencies(baseline=baseline, excluded=excluded)
    scoped = dependencies.scope_schema(schema)
    validator = Draft7Validator(scoped)

    assert validator.is_valid(baseline)
    assert schema == original_schema and baseline == original_baseline
    assert scoped["properties"] == schema["properties"]
    assert sequence(scoped["allOf"])[0] == sequence(schema["allOf"])[0]
    assert dependencies.scope_schema(schema) == scoped
    for name in ("first", "second"):
        changed = copy.deepcopy(baseline)
        parent = mapping(changed["parent"]) if nested else changed
        parent[name] = {"name": "changed"}
        assert validator.is_valid(changed) is (name == "second" and not exclude_second)


def test_absent_dependency_stays_absent_without_restricting_its_referrer() -> None:
    """
    Forbid an omitted dependency without replacing a schema referenced by present data.

    Returns:
        None: Omission is frozen, while the present sibling retains its original type check.
    """
    schema: dict[str, object] = {
        "type": "object",
        "properties": {"first": {"type": "string"}, "second": {"$ref": "#/properties/first"}},
    }
    dependencies = Dependencies(baseline={"second": "present"}, excluded={("first",)})
    validator = Draft7Validator(dependencies.scope_schema(schema))
    assert validator.is_valid({"second": "present"})
    assert not validator.is_valid({"first": "new", "second": "present"})
    assert not validator.is_valid({"second": 1})

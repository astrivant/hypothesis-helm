"""
Check that early binding rejection never excludes a validated complete input.
"""

from collections.abc import Iterator
from itertools import product

import pytest
from jsonschema import Draft202012Validator

from hypothesis_helm.schemas.contracts import json_value
from hypothesis_helm.schemas.generation.feasibility import compatible_binding

_Path = tuple[str | int, ...]


def _leaves(value: object, prefix: _Path = ()) -> Iterator[tuple[_Path, object]]:
    """
    Visit every concrete leaf in a finite reference document.

    Args:
        value (object): Reference value to traverse.
        prefix (_Path): Current object keys and array indices.

    Yields:
        tuple[_Path, object]: Concrete leaf and its complete value.
    """
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _leaves(child, (*prefix, key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _leaves(child, (*prefix, index))
    else:
        yield prefix, value


@pytest.mark.parametrize("operator", ["anyOf", "oneOf", "conditional"])
def test_valid_completions_are_never_rejected(operator: str) -> None:
    """
    Exhaust a finite nested domain and retain every leaf of every valid completion.

    Args:
        operator (str): Branching construct joining incompatible array and map regions.

    Returns:
        None: Every schema-valid reference leaf survives the conservative compatibility check.
    """
    array: dict[str, object] = {"properties": {"enabled": {"const": True}, "entries": {"type": "array", "items": {"$ref": "#/$defs/leaf"}}}}
    objects: dict[str, object] = {
        "properties": {
            "enabled": {"const": False},
            "entries": {"type": "object", "patternProperties": {"^a$": {"type": "integer"}}, "additionalProperties": {"type": "string"}},
        }
    }
    schema: dict[str, object] = {
        "type": "object",
        "properties": {"enabled": {"type": "boolean"}},
        "required": ["enabled", "entries"],
        "$defs": {"leaf": {"type": ["string", "integer"]}},
    }
    if operator == "conditional":
        schema.update({"if": {"properties": {"enabled": {"const": True}}}, "then": array, "else": objects})
    else:
        schema[operator] = [array, objects]
    validator = Draft202012Validator(schema)
    accepted = 0
    for enabled, first, second in product((False, True), (None, True, 0, "x"), (None, True, 0, "x")):
        for entries in ([first, second], {"a": first, "b": second}):
            document = {"enabled": enabled, "entries": entries}
            if validator.is_valid(json_value(document)):
                accepted += 1
                for path, value in _leaves(document):
                    assert compatible_binding(schema, path, value), (document, path)
    assert accepted > 0


@pytest.mark.parametrize(
    ("schema", "path", "value", "compatible"),
    [
        ({"type": "object", "additionalProperties": False}, ("x",), 1, False),
        ({"type": "array", "maxItems": 1}, (1,), 0, False),
        ({"type": "array", "prefixItems": [{"const": 0}], "items": False}, (1,), 1, False),
        ({"type": "object", "propertyNames": {"enum": ["x"]}}, ("y",), 1, False),
        ({"type": "object", "patternProperties": {"^x": {"type": "integer"}, "x$": {"minimum": 2}}}, ("x",), 1, False),
        ({"type": "object", "if": {"required": ["guard"]}, "then": {"properties": {"x": False}}}, ("x",), 1, True),
        ({"type": "object", "not": {"required": ["guard", "x"]}}, ("x",), 1, True),
        ({"type": "object", "dependentRequired": {"x": ["guard"]}}, ("x",), 1, True),
    ],
)
def test_definite_conflicts_and_unknown_siblings(schema: dict[str, object], path: _Path, value: object, compatible: bool) -> None:
    """
    Reject known conflicts while deferring undecided conditions to complete validation.

    Args:
        schema (dict[str, object]): Partial or complete schema constraints.
        path (_Path): Binding under inspection.
        value (object): Requested leaf.
        compatible (bool): Expected conservative outcome.

    Returns:
        None: Structural contradictions are rejected without guessing unknown sibling values.
    """
    assert compatible_binding(schema, path, value) is compatible

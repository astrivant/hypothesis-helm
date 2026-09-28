"""
Exercise alternative container shapes and map key/value constraints together.
"""

import copy
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from jsonschema import validators

from hypothesis_helm.charts.model import Chart, _schema_nodes
from hypothesis_helm.charts.suites.runtime import path_values
from hypothesis_helm.schemas.contracts import json_value
from hypothesis_helm.schemas.dialects import DRAFT7, DRAFT2019, DRAFT2020
from hypothesis_helm.schemas.generation.domains import InputDomains


@pytest.mark.parametrize("version", [DRAFT7, DRAFT2019, DRAFT2020])
@pytest.mark.parametrize("array_branch", [False, True])
def test_conditional_container_binding(tmp_path: Path, version: str, array_branch: bool) -> None:
    """
    Resolve the same wildcard as an array index or map key in the appropriate branch.

    Args:
        tmp_path (Path): Isolated chart location.
        version (str): Schema dialect to validate and generate.
        array_branch (bool): Required guard value selecting the container shape.

    Returns:
        None: Every example preserves the supplied leaf and satisfies the selected branch.
    """
    schema: dict[str, object] = {
        "$schema": version,
        "type": "object",
        "properties": {"enabled": {"const": array_branch}},
        "required": ["enabled"],
        "if": {"properties": {"enabled": {"const": True}}},
        "then": {"properties": {"entries": {"type": "array", "items": {"type": "boolean"}, "maxItems": 1}}},
        "else": {
            "properties": {
                "entries": {"type": "object", "patternProperties": {"^entry$": {"type": "boolean"}}, "additionalProperties": False}
            }
        },
    }
    defaults: dict[str, object] = {"enabled": array_branch, "entries": [] if array_branch else {}}
    expected: tuple[str | int, ...] = ("entries", 0 if array_branch else "entry")
    check_binding(tmp_path, schema, defaults, ("entries", "*"), True, expected)


@pytest.mark.parametrize("version", [DRAFT7, DRAFT2019, DRAFT2020])
@pytest.mark.parametrize("long_branch", [False, True])
def test_conditional_tuple_tail_binding(tmp_path: Path, version: str, long_branch: bool) -> None:
    """
    Keep each branch's tuple-tail index instead of taking the maximum prefix length.

    Args:
        tmp_path (Path): Isolated chart location.
        version (str): Schema dialect controlling tuple keywords.
        long_branch (bool): Whether the active tuple has one or two positional entries.

    Returns:
        None: A Boolean leaf is generated in the active branch's tail.
    """
    prefix_keyword, tail_keyword = ("prefixItems", "items") if version == DRAFT2020 else ("items", "additionalItems")
    short: dict[str, object] = {"type": "array", prefix_keyword: [{"const": 0}], tail_keyword: {"type": "boolean"}, "maxItems": 2}
    long = {**short, prefix_keyword: [{"const": 0}, {"const": 1}], "maxItems": 3}
    schema: dict[str, object] = {
        "$schema": version,
        "type": "object",
        "properties": {"enabled": {"const": long_branch}},
        "required": ["enabled"],
        "if": {"properties": {"enabled": {"const": True}}},
        "then": {"properties": {"rows": long}},
        "else": {"properties": {"rows": short}},
    }
    defaults: dict[str, object] = {"enabled": long_branch, "rows": [0, 1] if long_branch else [0]}
    check_binding(tmp_path, schema, defaults, ("rows", "*"), True, ("rows", 2 if long_branch else 1))


@pytest.mark.parametrize(
    ("entries", "value", "key"),
    [
        ({"propertyNames": {"enum": ["allowed"]}, "additionalProperties": {"type": "boolean"}}, True, "allowed"),
        (
            {"patternProperties": {"^a$": {"type": "integer"}, "^b$": {"type": "string"}}, "additionalProperties": False},
            "text",
            "b",
        ),
        (
            {
                "propertyNames": {"enum": ["b"]},
                "patternProperties": {"^a$": {"type": "integer"}, "^b$": {"type": "string"}},
                "additionalProperties": False,
            },
            "text",
            "b",
        ),
        (
            {"patternProperties": {"^a": {"type": "integer"}, "a$": {"enum": [2]}}, "additionalProperties": False},
            2,
            "a",
        ),
    ],
    ids=["property-names", "second-pattern", "impossible-key-region", "overlapping-patterns"],
)
def test_map_key_and_value_binding(tmp_path: Path, entries: dict[str, object], value: object, key: str) -> None:
    """
    Select permitted keys together with their value domains rather than by pattern order.

    Args:
        tmp_path (Path): Isolated chart location.
        entries (dict[str, object]): Key regions and associated value restrictions.
        value (object): Requested leaf.
        key (str): Key that must be reachable for the requested value.

    Returns:
        None: Generated maps validate without weakening key or value constraints.
    """
    # Fix the overlapping-pattern key to exercise their intersection deterministically.
    if key == "a":
        entries = {**entries, "propertyNames": {"enum": ["a"]}}
    schema: dict[str, object] = {"type": "object", "properties": {"entries": {"type": "object", **entries}}}
    check_binding(tmp_path, schema, {"entries": {}}, ("entries", "*"), value, ("entries", key))


def test_named_array_does_not_inherit_extra_property_type(tmp_path: Path) -> None:
    """
    Generate a named array even when additional map properties must be strings.

    Args:
        tmp_path (Path): Isolated chart location.

    Returns:
        None: Missing containers keep their declared array and object types.
    """
    rows: dict[str, object] = {
        "type": "array",
        "maxItems": 1,
        "items": {"type": "object", "properties": {"name": {"const": "x"}}, "required": ["name"], "additionalProperties": False},
    }
    schema: dict[str, object] = {"type": "object", "properties": {"rows": rows}, "additionalProperties": {"type": "string"}}
    assert _schema_nodes(schema, ("rows",), schema) == [rows]
    assert _schema_nodes(schema, ("other",), schema) == [{"type": "string"}]
    check_binding(tmp_path, schema, {}, ("rows", "*", "name"), "x", ("rows", 0, "name"))


def test_pattern_property_excludes_additional_type() -> None:
    """
    Apply all matching patterns but exclude the extra-key schema at the same node.

    Returns:
        None: Pattern intersections and wildcard extra regions remain distinguishable.
    """
    schema: dict[str, object] = {
        "type": "object",
        "patternProperties": {"^row": {"type": "array"}, "s$": {"maxItems": 2}},
        "additionalProperties": {"type": "string"},
    }
    assert _schema_nodes(schema, ("rows",), schema) == [{"type": "array"}, {"maxItems": 2}]
    assert _schema_nodes(schema, ("*",), schema) == [{"type": "array"}, {"maxItems": 2}, {"type": "string"}]


def check_binding(
    directory: Path,
    schema: dict[str, object],
    defaults: dict[str, object],
    path: tuple[str | int, ...],
    value: object,
    expected: tuple[str | int, ...],
) -> None:
    """
    Validate repeated candidate construction with health checks enabled.

    Args:
        directory (Path): Chart location, with no renderer needed for generation checks.
        schema (dict[str, object]): Complete authored contract.
        defaults (dict[str, object]): Starting values, which must remain unchanged.
        path (tuple[str | int, ...]): Symbolic path to exercise.
        value (object): Requested leaf value.
        expected (tuple[str | int, ...]): Concrete path where the leaf must occur.

    Returns:
        None: All examples validate and retain the requested value without mutating input data.
    """
    original = copy.deepcopy((schema, defaults))
    chart = Chart(directory, schema, defaults)
    chart.domains = InputDomains([], [], "nested-binding-regression")
    validator = validators.validator_for(schema)(schema)

    @settings(max_examples=12, deadline=None, derandomize=True)
    @given(st.data())
    def check(data: st.DataObject) -> None:
        """
        Generate an example through the production path-binding pipeline.

        Args:
            data (st.DataObject): Hypothesis dependent draw context.

        Returns:
            None: Both full-schema validity and target preservation hold.
        """
        result = path_values(chart, path, value, data)
        assert validator.is_valid(json_value(result))
        selected: object = result
        for segment in expected:
            if isinstance(selected, list) and isinstance(segment, int):
                selected = selected[segment]
            else:
                assert isinstance(selected, dict)
                selected = selected[segment]
        assert type(selected) is type(value) and selected == value

    check()
    assert (schema, defaults) == original


@pytest.mark.parametrize("operator", ["conditional", "anyOf", "oneOf"])
def test_candidate_can_change_branch_and_container(tmp_path: Path, operator: str) -> None:
    """
    Reach a valid alternate container when the baseline branch cannot accept the leaf.

    Args:
        tmp_path (Path): Isolated chart location.
        operator (str): Branching construct whose alternatives must remain available.

    Returns:
        None: A string candidate activates the array branch despite the map-valued baseline.
    """
    array: dict[str, object] = {
        "properties": {"enabled": {"const": True}, "entries": {"type": "array", "items": {"type": "string"}, "maxItems": 1}}
    }
    mapping_branch: dict[str, object] = {
        "properties": {
            "enabled": {"const": False},
            "entries": {"type": "object", "patternProperties": {"^entry$": {"type": "integer"}}, "additionalProperties": False},
        }
    }
    schema: dict[str, object] = {"type": "object", "required": ["enabled", "entries"], "properties": {"enabled": {"type": "boolean"}}}
    if operator == "conditional":
        schema.update({"if": {"properties": {"enabled": {"const": True}}}, "then": array, "else": mapping_branch})
    else:
        schema[operator] = [array, mapping_branch]
    check_binding(tmp_path, schema, {"enabled": False, "entries": {}}, ("entries", "*"), "target", ("entries", 0))


def test_referenced_map_names_nested_in_array(tmp_path: Path) -> None:
    """
    Resolve a key-name reference while traversing an array containing constrained maps.

    Args:
        tmp_path (Path): Isolated chart location.

    Returns:
        None: Both array indices and schema-defined map keys survive nested traversal.
    """
    schema: dict[str, object] = {
        "type": "object",
        "$defs": {"name": {"enum": ["allowed"]}},
        "properties": {
            "rows": {
                "type": "array",
                "maxItems": 1,
                "items": {"type": "object", "propertyNames": {"$ref": "#/$defs/name"}, "additionalProperties": {"type": "boolean"}},
            }
        },
    }
    check_binding(tmp_path, schema, {"rows": []}, ("rows", "*", "*"), True, ("rows", 0, "allowed"))

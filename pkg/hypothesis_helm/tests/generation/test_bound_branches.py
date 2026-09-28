"""
Keep dependent-context generation constructive when a binding rules out Boolean branches.
"""

import copy
from itertools import product
from pathlib import Path

import pytest
from hypothesis import given, seed, settings
from hypothesis import strategies as st
from jsonschema import validators

from hypothesis_helm.charts.model import Chart
from hypothesis_helm.charts.suites.runtime import _constraint, path_values
from hypothesis_helm.schemas.contracts import json_value, mapping, sequence
from hypothesis_helm.schemas.dialects import DRAFT7, DRAFT2020
from hypothesis_helm.schemas.generation.conditionals import bound_branches
from hypothesis_helm.schemas.generation.domains import InputDomains


def branch_schema(operator: str) -> dict[str, object]:
    """
    Build the open-object branch switch that exposed excessive rejection in CI.

    Args:
        operator (str): Conditional or Boolean branch operator.

    Returns:
        dict[str, object]: An array branch for enabled inputs and a map branch otherwise.
    """
    array: dict[str, object] = {
        "properties": {"enabled": {"const": True}, "entries": {"type": "array", "items": {"type": "string"}, "maxItems": 1}}
    }
    objects: dict[str, object] = {
        "properties": {
            "enabled": {"const": False},
            "entries": {"type": "object", "patternProperties": {"^entry$": {"type": "integer"}}, "additionalProperties": False},
        }
    }
    schema: dict[str, object] = {"type": "object", "required": ["enabled", "entries"], "properties": {"enabled": {"type": "boolean"}}}
    if operator == "conditional":
        schema.update({"if": {"properties": {"enabled": {"const": True}}}, "then": array, "else": objects})
    else:
        schema[operator] = [array, objects]
    return schema


@pytest.mark.parametrize("version", [DRAFT7, DRAFT2020])
@pytest.mark.parametrize("operator", ["anyOf", "oneOf", "conditional"])
@pytest.mark.parametrize("array", [False, True])
def test_binding_specialization_preserves_accepted_documents(version: str, operator: str, array: bool) -> None:
    """
    Remove impossible alternatives while preserving the original guard and binding.

    Args:
        version (str): Tuple and reference dialect.
        operator (str): Boolean branch form being specialized.
        array (bool): Whether the binding requires the array or map branch.

    Returns:
        None: Both validators agree over the finite reference domain and the input schema is unchanged.
    """
    schema = branch_schema(operator)
    schema["$schema"] = version
    path = ("entries", 0 if array else "entry")
    value: object = "target" if array else 1
    keyword = "prefixItems" if version == DRAFT2020 else "items"
    schema["allOf"] = [_constraint(path, value, positional_keyword=keyword)]
    original = copy.deepcopy(schema)
    specialized = bound_branches(schema, path, value)
    assert all(key not in specialized for key in ("anyOf", "oneOf", "if"))
    before = validators.validator_for(schema)(schema)
    after = validators.validator_for(specialized)(specialized)
    accepted = 0
    for enabled, leaf in product((None, False, True), (None, True, 1, "target")):
        for entries in ([leaf], [leaf, "other"], {"entry": leaf}, {}):
            document = {"entries": entries} if enabled is None else {"enabled": enabled, "entries": entries}
            expected = before.is_valid(json_value(document))
            assert after.is_valid(json_value(document)) == expected, document
            accepted += expected
    assert accepted > 0
    assert schema == original


def test_overlapping_oneof_remains_exclusive() -> None:
    """
    Retain exclusive-choice semantics when more than one branch could accept the binding.

    Returns:
        None: A document matching both surviving branches remains invalid.
    """
    schema: dict[str, object] = {
        "type": "object",
        "oneOf": [
            {"properties": {"entries": {"type": "array", "maxItems": 1}}},
            {"properties": {"entries": {"type": "array", "maxItems": 2}}},
        ],
        "allOf": [_constraint(("entries", 0), "target", positional_keyword="prefixItems")],
    }
    specialized = bound_branches(schema, ("entries", 0), "target")
    assert len(sequence(specialized["oneOf"])) == 2
    validator = validators.validator_for(specialized)(specialized)
    assert not validator.is_valid({"entries": ["target"]})
    assert validator.is_valid({"entries": ["target", "other"]})


@pytest.mark.parametrize("version", [DRAFT7, DRAFT2020])
def test_branch_references_keep_original_root(version: str) -> None:
    """
    Analyze local references without losing definitions or their inherited dialect.

    Args:
        version (str): Schema dialect inherited by referenced alternatives.

    Returns:
        None: The surviving referenced branch and full validation use the original definitions.
    """
    schema = branch_schema("anyOf")
    schema["$schema"] = version
    array, objects = sequence(schema["anyOf"])
    schema["$defs"] = {"array": array, "objects": objects}
    schema["anyOf"] = [{"$ref": "#/$defs/array"}, {"$ref": "#/$defs/objects"}]
    keyword = "prefixItems" if version == DRAFT2020 else "items"
    schema["allOf"] = [_constraint(("entries", 0), "target", positional_keyword=keyword)]
    specialized = bound_branches(schema, ("entries", 0), "target")
    assert "anyOf" not in specialized
    assert specialized["$defs"] == schema["$defs"]
    validator = validators.validator_for(specialized)(specialized)
    assert validator.is_valid({"enabled": True, "entries": ["target"]})
    assert not validator.is_valid({"enabled": False, "entries": ["target"]})


@pytest.mark.parametrize("operator", ["anyOf", "oneOf", "conditional"])
@pytest.mark.parametrize("random_seed", [0, 42])
def test_open_branch_contexts_generate_without_health_check_failures(tmp_path: Path, operator: str, random_seed: int) -> None:
    """
    Exercise many branch-switching draws with normal Hypothesis health checks enabled.

    Args:
        tmp_path (Path): Synthetic chart path; no Helm invocation is needed.
        operator (str): Branching construct from the CI regression.
        random_seed (int): Reproducible generation seed independent of the suite's test order.

    Returns:
        None: Every draw changes the guard and keeps the exact bound array value.
    """
    schema = branch_schema(operator)
    original = copy.deepcopy(schema)
    chart = Chart(tmp_path, schema, {"enabled": False, "entries": {}})
    chart.domains = InputDomains([], [], "branch-context-regression")

    @seed(random_seed)
    @settings(max_examples=100, deadline=None, database=None)
    @given(st.data())
    def check(data: st.DataObject) -> None:
        """
        Generate the selected input with the production context strategy.

        Args:
            data (st.DataObject): Dependent draw context.

        Returns:
            None: Requested leaf and compatible guard survive complete schema validation.
        """
        result = path_values(chart, ("entries", "*"), "target", data)
        assert result["enabled"] is True
        assert result["entries"] == ["target"]
        assert validators.validator_for(schema)(schema).is_valid(json_value(result))

    check()
    assert schema == original
    assert mapping(chart.defaults) == {"enabled": False, "entries": {}}

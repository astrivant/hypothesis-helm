"""
Keep path completion proportional to the missing context and preserve validation.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import TYPE_CHECKING

from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis_helm.charts.model import Chart
from hypothesis_helm.charts.suites import runtime
from hypothesis_helm.schemas.generation.contexts import context_proposal, literal_repairs
from hypothesis_helm.schemas.generation.domains import InputDomains
from jsonschema import Draft202012Validator

if TYPE_CHECKING:
    import pytest


def test_required_siblings_do_not_solve_unrelated_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Complete a new item while leaving a large unrelated schema out of the solver.

    Args:
        tmp_path (Path): Synthetic chart directory.
        monkeypatch (pytest.MonkeyPatch): Guard against the original expensive fallback.

    Returns:
        None: Each generated case preserves the target, defaults and complete schema.
    """
    unrelated = {
        "type": "object",
        "properties": {f"field{index}": {"anyOf": [{"type": "string"}, {"type": "integer"}]} for index in range(1000)},
    }
    schema: dict[str, object] = {
        "type": "object",
        "if": {"properties": {"rules": {"minItems": 1}}},
        "then": {"properties": {"enabled": {"const": True}, "mode": {"const": "managed"}}},
        "properties": {
            "enabled": {"type": "boolean"},
            "mode": {"enum": ["local", "managed"]},
            "unrelated": unrelated,
            "rules": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["weight", "mode"],
                    "properties": {"weight": {"type": "integer"}, "mode": {"enum": ["spread", "pack"]}},
                    "additionalProperties": False,
                },
            },
        },
    }
    defaults: dict[str, object] = {"mode": "local", "enabled": False, "unrelated": {"field7": "kept"}, "rules": []}
    chart = Chart(tmp_path, schema, defaults)
    chart.domains = InputDomains([], [], "required-context")
    original_schema, original_defaults = copy.deepcopy(schema), copy.deepcopy(defaults)

    def prohibit_fallback(*args: object, **kwargs: object) -> dict[str, object]:
        """
        Fail if a missing required sibling causes complete-chart solving.

        Args:
            *args (object): Unused general-solver arguments.
            **kwargs (object): Unused general-solver keyword arguments.

        Returns:
            dict[str, object]: Never returned because fallback is unnecessary here.
        """
        raise AssertionError("required siblings must not invoke the whole-chart fallback")

    monkeypatch.setattr(runtime, "bound_branches", prohibit_fallback)

    @settings(max_examples=12, deadline=None, derandomize=True)
    @given(st.integers(), st.data())
    def check(weight: int, data: st.DataObject) -> None:
        """
        Preserve arbitrary target values in an independently validated completion.

        Args:
            weight (int): Target value, including values beyond small example ranges.
            data (st.DataObject): Dependent strategy draw context.

        Returns:
            None: Complete validation and preservation checks succeed.
        """
        result = runtime.path_values(chart, ("rules", "*", "weight"), weight, data)
        Draft202012Validator(schema).validate(result)
        assert result["enabled"] is True
        assert result["mode"] == "managed"
        assert result["unrelated"] == defaults["unrelated"]
        assert isinstance(result["rules"], list)
        assert result["rules"][0]["weight"] == weight
        assert schema == original_schema
        assert defaults == original_defaults

    check()


def test_proposal_preserves_reference_and_collection_boundaries() -> None:
    """
    Decline recursive and oversized completion without changing caller inputs.

    Returns:
        None: Unsupported proposals leave the general solver available.
    """
    recursive: dict[str, object] = {
        "type": "object",
        "required": ["next"],
        "properties": {"next": {"$ref": "#"}, "target": {"type": "integer"}},
    }
    assert context_proposal(recursive, {"target": 1}, ("target",)) is None
    oversized: dict[str, object] = {
        "type": "object",
        "required": ["items"],
        "properties": {"items": {"type": "array", "minItems": 1_000_000}, "target": {"type": "integer"}},
    }
    assert context_proposal(oversized, {"target": 1}, ("target",)) is None


def test_missing_required_empty_array_has_a_valid_proposal() -> None:
    """
    Avoid an invalid empty prefixItems declaration for a missing required array.

    Returns:
        None: The proposed schema is valid and admits the minimal complete context.
    """
    schema: dict[str, object] = {
        "type": "object",
        "required": ["items"],
        "properties": {"items": {"type": "array"}, "target": {"type": "integer"}},
    }
    proposal = context_proposal(schema, {"target": 1}, ("target",))
    assert proposal is not None
    Draft202012Validator.check_schema(proposal)
    Draft202012Validator(proposal).validate({"target": 1, "items": []})


def test_nonliteral_dependencies_retain_general_context_generation(tmp_path: Path) -> None:
    """
    Keep dependent-context solving when a minimum requires more than a literal repair.

    Args:
        tmp_path (Path): Synthetic chart directory.

    Returns:
        None: Generated capacity meets the dependent minimum without changing the target.
    """
    schema: dict[str, object] = {
        "type": "object",
        "required": ["capacity", "items"],
        "additionalProperties": False,
        "properties": {
            "capacity": {"type": "integer", "minimum": 0, "maximum": 10},
            "items": {"type": "array", "items": {"type": "integer"}, "maxItems": 1},
        },
        "if": {"properties": {"items": {"minItems": 1}}},
        "then": {"properties": {"capacity": {"minimum": 5}}},
    }
    chart = Chart(tmp_path, schema, {"capacity": 0, "items": []})
    chart.domains = InputDomains([], [], "general-context")

    @settings(max_examples=3, deadline=None, derandomize=True)
    @given(st.data())
    def check(data: st.DataObject) -> None:
        """
        Exercise the retained general solver with an independent validator.

        Args:
            data (st.DataObject): Dependent strategy draw context.

        Returns:
            None: Complete schema and selected leaf remain valid.
        """
        result = runtime.path_values(chart, ("items", "*"), 42, data)
        Draft202012Validator(schema).validate(result)
        assert result["items"] == [42]
        assert isinstance(result["capacity"], int) and result["capacity"] >= 5

    check()


def test_literal_repairs_preserve_the_target_and_its_ancestors() -> None:
    """
    Repair independent enum fields without changing target containers or their children.

    Returns:
        None: Literal suggestions contain only independent context fields.
    """
    schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "target": {"const": {"child": 7}, "properties": {"child": {"const": 7}}},
            "mode": {"enum": ["enabled", "disabled"]},
        },
    }
    errors = list(Draft202012Validator(schema).iter_errors({"target": {"child": 1}, "mode": "unknown"}))
    expected = [(("mode",), "enabled"), (("mode",), "disabled")]
    assert list(literal_repairs(errors, ("target",))) == expected
    assert list(literal_repairs(errors, ("target", "child"))) == expected


def test_nested_conditional_context_does_not_expand_the_chart(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Solve conditional required siblings inside one new item without unrelated chart branches.

    Args:
        tmp_path (Path): Synthetic chart directory.
        monkeypatch (pytest.MonkeyPatch): Guard against complete-chart fallback.

    Returns:
        None: Every target survives in a fully valid locally generated context.
    """
    service = {
        "type": "object",
        "required": ["direction", "graphs"],
        "additionalProperties": False,
        "properties": {
            "direction": {"enum": ["in", "out"]},
            "url": {"type": "string", "minLength": 1},
            "endpoints": {"type": "array", "items": {"enum": ["api", "events"]}, "maxItems": 2},
            "graphs": {
                "type": "array",
                "items": {"type": "object", "required": ["uid"], "properties": {"uid": {"type": "string"}}},
            },
        },
        "if": {"properties": {"direction": {"const": "in"}}},
        "then": {"required": ["endpoints"], "properties": {"endpoints": {"minItems": 1}}, "not": {"required": ["url"]}},
        "else": {"required": ["url"], "properties": {"endpoints": {"maxItems": 0}}},
    }
    schema = {
        "type": "object",
        "properties": {
            "services": {"type": "array", "items": service},
            "unrelated": {
                "type": "object",
                "properties": {f"field{index}": {"anyOf": [{"type": "string"}, {"type": "integer"}]} for index in range(1000)},
            },
        },
    }
    defaults = {"services": [], "unrelated": {"field1": "keep"}}
    chart = Chart(tmp_path, schema, defaults)
    chart.domains = InputDomains([], [], "conditional-context")
    original_schema, original_defaults = copy.deepcopy(schema), copy.deepcopy(defaults)

    def no_general_solver(*args: object, **kwargs: object) -> dict[str, object]:
        """
        Reject complete-chart generation for a bounded conditional item.

        Args:
            *args (object): Unused fallback arguments.
            **kwargs (object): Unused fallback options.

        Returns:
            dict[str, object]: Never returned; this case must solve locally.
        """
        raise AssertionError("conditional item must not invoke whole-chart solving")

    monkeypatch.setattr(runtime, "bound_branches", no_general_solver)

    @settings(max_examples=6, deadline=None, derandomize=True)
    @given(st.text(max_size=8), st.data())
    def check(uid: str, data: st.DataObject) -> None:
        """
        Preserve an arbitrary nested target while satisfying its enclosing object's conditions.

        Args:
            uid (str): Target string whose value may not change.
            data (st.DataObject): Context generation draws.

        Returns:
            None: Complete validation, target preservation and input immutability hold.
        """
        result = runtime.path_values(chart, ("services", "*", "graphs", "*", "uid"), uid, data)
        Draft202012Validator(schema).validate(result)
        assert isinstance(result["services"], list)
        assert result["services"][0]["graphs"][0]["uid"] == uid
        assert result["unrelated"] == defaults["unrelated"]
        assert schema == original_schema and defaults == original_defaults

    check()


def test_focused_context_declines_root_reference_and_size_expansion() -> None:
    """
    Keep unrestricted, reference-dependent and oversized scopes on the established fallback.

    Returns:
        None: Focused proposals do not expand unbounded contexts or detach references.
    """
    schema: dict[str, object] = {
        "type": "object",
        "properties": {"item": {"type": "object", "properties": {"target": {"type": "integer"}, "other": {"$ref": "#"}}}},
    }
    candidate = {"item": {"target": 1}}
    assert context_proposal(schema, candidate, ("item", "target"), focus=()) is None
    assert context_proposal(schema, candidate, ("item", "target"), focus=("item", "target")) is None
    assert context_proposal(schema, candidate, ("item", "target"), focus=("item",)) is None
    oversized: dict[str, object] = {
        "type": "object",
        "properties": {"item": {"type": "object", "description": "x" * 65537, "properties": {"target": {"type": "integer"}}}},
    }
    assert context_proposal(oversized, candidate, ("item", "target"), focus=("item",)) is None


def test_focused_target_is_preserved_in_older_schema_dialects() -> None:
    """
    Use a target assertion understood by Draft 4 as well as later schema dialects.

    Returns:
        None: A focused child cannot silently ignore the protected value assertion.
    """
    for version in (
        "http://json-schema.org/draft-04/schema#",
        "http://json-schema.org/draft-07/schema#",
        "https://json-schema.org/draft/2020-12/schema",
    ):
        schema: dict[str, object] = {
            "$schema": version,
            "type": "object",
            "properties": {"item": {"type": "object", "properties": {"target": {"type": "integer"}}}},
        }
        proposal = context_proposal(schema, {"item": {"target": 5}}, ("item", "target"), focus=("item",))
        assert proposal is not None
        Draft202012Validator.check_schema(proposal)
        validator = Draft202012Validator(proposal)
        assert validator.is_valid({"item": {"target": 5}})
        assert not validator.is_valid({"item": {"target": 0}})

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
from hypothesis_helm.schemas.generation.contexts import context_proposal
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
        "properties": {
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
    defaults: dict[str, object] = {"unrelated": {"field7": "kept"}, "rules": []}
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

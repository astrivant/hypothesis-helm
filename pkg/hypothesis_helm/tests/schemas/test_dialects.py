"""
Compare schema dialect lowering, path discovery and finite coverage against native JSON Schema validators.
"""

import copy
import json
from itertools import product
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis_helm_catalog.builder import scalar_domain
from jsonschema import Draft7Validator, validators

from hypothesis_helm.charts.model import Chart, _schema_nodes
from hypothesis_helm.charts.suites.generate import strategy_source
from hypothesis_helm.charts.suites.runtime import _constraint
from hypothesis_helm.schemas.configuration.policy import check_schema, restrict
from hypothesis_helm.schemas.contracts import json_value
from hypothesis_helm.schemas.dialects import DRAFT4, DRAFT6, DRAFT7, DRAFT2019, DRAFT2020, canonical
from hypothesis_helm.schemas.generation.compatibility import generation_view, validation_view
from hypothesis_helm.schemas.generation.domains import InputDomains
from hypothesis_helm.schemas.generation.finite import enumerate_values
from hypothesis_helm.schemas.generation.strategies import schema_strategy
from hypothesis_helm.schemas.model import ValuesModel
from hypothesis_helm.schemas.paths import dereference, enumerate_paths

DRAFTS = (DRAFT4, DRAFT6, DRAFT7, DRAFT2019, DRAFT2020)


@pytest.mark.parametrize("draft", [DRAFT7, DRAFT2019, DRAFT2020])
@pytest.mark.parametrize("branches", [{"then": False}, {"else": False}, {"then": False, "else": False}])
def test_impossible_conditionals_do_not_poison_later_generation(draft: str, branches: dict[str, object]) -> None:
    """
    Generate impossible conditionals before ordinary values to expose shared generator-state corruption.

    Args:
        draft (str): Original conditional-supporting schema dialect.
        branches (dict[str, object]): Contradictory branch or pair of branches.

    Returns:
        None: Empty domains remain empty and later valid object and tuple domains remain usable.
    """
    impossible = {"$schema": draft, "if": "then" in branches, **branches}
    assert schema_strategy(impossible).is_empty
    schema: dict[str, object] = {
        "$schema": DRAFT7,
        "type": "object",
        "required": ["rows"],
        "additionalProperties": False,
        "properties": {
            "rows": {"type": "array", "items": [{"enum": ["a", "b"]}], "additionalItems": {"type": "boolean"}, "maxItems": 2},
        },
    }
    validator = Draft7Validator(schema)

    @settings(max_examples=12, deadline=None, derandomize=True)
    @given(schema_strategy(schema))
    def check(value: object) -> None:
        """
        Exercise object, tuple and Boolean generation after an impossible input domain.

        Args:
            value (object): Generated tuple container.

        Returns:
            None: Later schema generation is unaffected by the preceding empty domain.
        """
        assert validator.is_valid(value)

    check()


@pytest.mark.parametrize("draft", DRAFTS)
def test_exclusive_bounds_keep_their_dialect(draft: str) -> None:
    """
    Preserve open numeric bounds after fragment extraction and generator lowering.

    Args:
        draft (str): Original document dialect.

    Returns:
        None: All routes accept precisely the same bounded integers.
    """
    bounds = {"minimum": 2, "maximum": 5, "exclusiveMinimum": True, "exclusiveMaximum": True}
    if draft != DRAFT4:
        bounds = {"exclusiveMinimum": 2, "exclusiveMaximum": 5}
    schema: dict[str, object] = {"$schema": draft, "type": "object", "properties": {"count": {"type": "integer", **bounds}}}
    entry = next(row for row in enumerate_paths(schema) if row.path == ("count",))
    lowered = generation_view(entry.schema)
    Draft7Validator.check_schema(lowered)
    accepted = [value for value in range(8) if Draft7Validator(lowered).is_valid(value)]
    assert accepted == [3, 4]
    assert "exclusiveMinimum" in strategy_source(entry.schema) or "min_value=3" in strategy_source(entry.schema)


@pytest.mark.parametrize("draft", DRAFTS)
def test_reference_siblings_follow_the_declared_draft(draft: str) -> None:
    """
    Ignore reference siblings before Draft 2019 and enforce them in modern drafts.

    Args:
        draft (str): Original document dialect.

    Returns:
        None: Discovery and generation agree with reference validation.
    """
    schema: dict[str, object] = {
        "$schema": draft,
        "definitions": {"count": {"type": "integer", "minimum": 0, "maximum": 3}},
        "$ref": "#/definitions/count",
        "minimum": 2,
    }
    original = validators.validator_for(schema)(schema)
    resolved = dereference(schema, schema)
    generated = generation_view(schema)
    for value in range(5):
        expected = original.is_valid(value)
        assert validators.validator_for(resolved)(resolved).is_valid(value) == expected
        assert Draft7Validator(generated).is_valid(value) == expected


@pytest.mark.parametrize("draft", [DRAFT7, DRAFT2019, DRAFT2020])
def test_tuple_prefix_and_tail_preserve_generation_and_exhaustion(draft: str) -> None:
    """
    Enumerate positional strings followed by Boolean tail entries without losing prefix cases.

    Args:
        draft (str): Tuple syntax selected by the schema author.

    Returns:
        None: Complete finite enumeration and generation preserve each positional domain.
    """
    array: dict[str, object] = {"type": "array", "maxItems": 2}
    prefix = [{"enum": ["a", "b"]}]
    array.update(
        {"prefixItems": prefix, "items": {"type": "boolean"}}
        if draft == DRAFT2020
        else {"items": prefix, "additionalItems": {"type": "boolean"}}
    )
    schema: dict[str, object] = {
        "$schema": draft,
        "type": "object",
        "required": ["rows"],
        "additionalProperties": False,
        "properties": {"rows": array},
    }
    values = list(enumerate_values(schema))
    assert len(values) == 7
    assert {"rows": ["a", True]} in values
    assert {"rows": []} in values
    lowered = generation_view(schema)
    Draft7Validator.check_schema(lowered)
    for candidate in values:
        assert Draft7Validator(lowered).is_valid(json_value(candidate))

    @settings(max_examples=12, deadline=None, derandomize=True)
    @given(schema_strategy(schema))
    def check(candidate: object) -> None:
        """
        Validate generated tuples using their original dialect.

        Args:
            candidate (object): Generated configuration.

        Returns:
            None: Every generated tuple also belongs to the finite domain.
        """
        assert candidate in values

    check()


def test_new_dependencies_and_zero_contains_lower_without_narrowing() -> None:
    """
    Preserve both forms of dependencies and allow zero matching contains items when requested.

    Returns:
        None: Lowered constraints agree on an independently enumerated input population.
    """
    schema: dict[str, object] = {
        "$schema": DRAFT2020,
        "type": "object",
        "dependentRequired": {"a": ["b"]},
        "dependentSchemas": {"a": {"properties": {"b": {"const": True}}}},
        "properties": {"rows": {"type": "array", "contains": {"const": True}, "minContains": 0}},
    }
    validator = validators.validator_for(schema)(schema)
    lowered = Draft7Validator(generation_view(schema))
    for a, b, rows in product([None, False, True], [None, False, True], [[], [False], [True]]):
        candidate = {key: value for key, value in {"a": a, "b": b, "rows": rows}.items() if value is not None}
        assert lowered.is_valid(candidate) == validator.is_valid(candidate)


@pytest.mark.parametrize("operator", ["not", "oneOf", "if"])
def test_unlowerable_constraints_do_not_narrow_boolean_compositions(operator: str) -> None:
    """
    Keep generation a superset when annotation-dependent constraints occur inside Boolean operators.

    Args:
        operator (str): Negation, exclusive choice or conditional selection.

    Returns:
        None: Every accepted original input remains reachable in the generation view.
    """
    uncertain: dict[str, object] = {"type": "object", "unevaluatedProperties": False}
    schema: dict[str, object] = {"$schema": DRAFT2020}
    if operator == "not":
        schema["not"] = uncertain
    elif operator == "oneOf":
        schema["oneOf"] = [uncertain, {"required": ["flag"]}]
    else:
        schema.update({"if": uncertain, "then": {"required": ["yes"]}, "else": {"required": ["no"]}})
    original = validators.validator_for(schema)(schema)
    generated = Draft7Validator(generation_view(schema))
    for keys in product([False, True], repeat=3):
        candidate = {name: True for name, present in zip(("flag", "yes", "no"), keys, strict=True) if present}
        if original.is_valid(candidate):
            assert generated.is_valid(candidate)


def test_schema_shaped_literal_objects_are_not_rewritten() -> None:
    """
    Keep reserved-looking names inside literal data intact during path expansion and conversion.

    Returns:
        None: Literal refs, definitions, dependencies and tuple-looking data stay byte-for-byte equivalent as JSON.
    """
    literal = {"$ref": "not-a-reference", "$defs": {"example": 1}, "prefixItems": [1], "dependencies": {"a": ["b"]}}
    schema: dict[str, object] = {"type": "object", "properties": {"payload": {"const": literal}}}
    before = copy.deepcopy(schema)
    entry = next(row for row in enumerate_paths(schema) if row.path == ("payload",))
    assert entry.schema["const"] == literal
    assert generation_view(entry.schema)["const"] == literal
    assert schema == before


def test_inactive_const_does_not_become_a_finite_domain_or_compiler_fact() -> None:
    """
    Ignore the Draft 6 const keyword in a Draft 4 chart's Boolean input.

    Returns:
        None: Both values remain in exhaustive coverage and the compiler model.
    """
    schema: dict[str, object] = {
        "$schema": DRAFT4,
        "type": "object",
        "additionalProperties": False,
        "required": ["flag"],
        "properties": {"flag": {"type": "boolean", "const": True}},
    }
    assert list(enumerate_values(schema)) == [{"flag": False}, {"flag": True}]
    assert "const" not in ValuesModel.from_schema(schema).root.children["flag"].schema


def test_references_into_tuple_positions_resolve_before_rewriting() -> None:
    """
    Follow an indexed JSON Pointer before prefixItems is renamed for the generator.

    Returns:
        None: The referenced enum survives positional keyword lowering.
    """
    schema: dict[str, object] = {
        "$schema": DRAFT2020,
        "$defs": {"tuple": {"prefixItems": [{"enum": ["target"]}]}},
        "$ref": "#/$defs/tuple/prefixItems/0",
    }
    assert Draft7Validator(generation_view(schema)).is_valid("target")
    assert not Draft7Validator(generation_view(schema)).is_valid("wrong")


def test_pointer_escapes_share_resolution_without_copying_mutable_targets() -> None:
    """
    Share percent decoding, pointer escapes and array indices between generation and schema inference.

    Returns:
        None: Both consumers resolve the same target, and inference retains the original mutable dictionary.
    """
    target: dict[str, object] = {"enum": ["allowed"]}
    schema: dict[str, object] = {
        "$defs": {"a b/~": {"prefixItems": [target]}},
        "$ref": "#/$defs/a%20b~1~0/prefixItems/0",
    }
    assert _schema_nodes(schema, (), schema)[0] is target
    assert Draft7Validator(generation_view(schema)).is_valid("allowed")
    assert not Draft7Validator(generation_view(schema)).is_valid("wrong")


@pytest.mark.parametrize("draft", [DRAFT4, DRAFT6])
def test_generated_guards_are_active_for_older_authored_schemas(draft: str) -> None:
    """
    Upgrade the generation contract before adding const and conditional compiler guards.

    Args:
        draft (str): Authored dialect lacking some generated condition keywords.

    Returns:
        None: An active guard constrains the field, while its disabled branch remains open.
    """
    schema: dict[str, object] = {
        "$schema": draft,
        "type": "object",
        "properties": {"enabled": {"type": "boolean"}, "name": {"type": "string"}},
    }
    domains = InputDomains(
        [
            {
                "path": ["name"],
                "schema": {"enum": ["allowed"]},
                "guards": [{"properties": {"enabled": {"const": True}}, "required": ["enabled"]}],
            }
        ],
        [],
        "guard-test",
    )
    before = copy.deepcopy(schema)
    constrained = domains.apply(schema)
    validators.validator_for(constrained).check_schema(constrained)
    validator = validators.validator_for(constrained)(constrained)
    assert not validator.is_valid({"enabled": True, "name": "wrong"})
    assert validator.is_valid({"enabled": False, "name": "wrong"})
    assert validator.is_valid({"enabled": True, "name": "allowed"})
    assert schema == before


def test_draft4_path_equality_is_not_an_ignored_const_keyword() -> None:
    """
    Keep exact selected values when constructing dependent contexts under Draft 4.

    Returns:
        None: The positional constraint accepts only the chosen value.
    """
    schema = {"$schema": DRAFT4, **_constraint(("rows", 0, "flag"), False)}
    validator = validators.validator_for(schema)(schema)
    assert validator.is_valid({"rows": [{"flag": False}]})
    assert not validator.is_valid({"rows": [{"flag": True}]})


def test_catalog_bounds_are_portable_and_literals_are_not_schema_references() -> None:
    """
    Preserve scalar source bounds while allowing reference-looking data in inline constraints.

    Returns:
        None: Catalog output has numeric bounds and literal input data does not trigger reference rejection.
    """
    source: dict[str, object] = {"$schema": DRAFT4, "type": "integer", "minimum": 0, "exclusiveMinimum": True}
    extracted = scalar_domain(source)
    assert extracted == {"type": "integer", "exclusiveMinimum": 0}
    validators.validator_for(extracted).check_schema(extracted)
    check_schema({"const": {"$ref": "https://example.com/ordinary-data", "$id": "ordinary"}}, inline=True)


@pytest.mark.parametrize("reference", ["$dynamicRef", "$recursiveRef"])
def test_unresolved_dynamic_references_are_explicit(reference: str) -> None:
    """
    Refuse dynamic reference semantics instead of quietly treating them as ordinary local pointers.

    Args:
        reference (str): Dynamic reference keyword supported by a modern validator.

    Returns:
        None: The generation boundary reports its unsupported reference mode directly.
    """
    with pytest.raises(ValueError, match="dynamic and recursive"):
        generation_view({"$schema": DRAFT2020 if reference == "$dynamicRef" else DRAFT2019, reference: "#"})


@pytest.mark.parametrize("draft", [DRAFT4, DRAFT6, DRAFT7, DRAFT2019])
def test_validation_upgrade_preserves_tuple_and_dependency_semantics(draft: str) -> None:
    """
    Preserve authoritative acceptance when adding modern compiler rules to a legacy contract.

    Args:
        draft (str): Original dialect to upgrade.

    Returns:
        None: Both validators agree on every independently constructed candidate.
    """
    schema: dict[str, object] = {
        "$schema": draft,
        "type": "object",
        "properties": {"rows": {"type": "array", "items": [{"enum": [0, 1]}], "additionalItems": False}},
        "dependentRequired" if draft == DRAFT2019 else "dependencies": {"rows": ["flag"]},
    }
    original = validators.validator_for(schema)(schema)
    modern = validation_view(schema)
    validators.validator_for(modern).check_schema(modern)
    upgraded = validators.validator_for(modern)(modern)
    for rows, flag in product([None, [], [0], [1], [2], [0, 1]], [None, True]):
        value = {key: entry for key, entry in {"rows": rows, "flag": flag}.items() if entry is not None}
        assert upgraded.is_valid(value) == original.is_valid(value)


def test_validation_upgrade_refuses_approximate_lowering() -> None:
    """
    Prevent a broad generation view from replacing an authoritative validation contract.

    Returns:
        None: Unsupported legacy-to-modern upgrades fail explicitly rather than relaxing validation.
    """
    with pytest.raises(ValueError, match="cannot be lowered exactly"):
        validation_view({"$schema": DRAFT2019, "unevaluatedProperties": False})


@pytest.mark.parametrize("draft", DRAFTS)
def test_metaschema_aliases_keep_constraints_and_literals(draft: str) -> None:
    """
    Canonicalize HTTP and HTTPS aliases without changing schema-looking literal values.

    Args:
        draft (str): Target canonical dialect.

    Returns:
        None: Validation remains warning-free and literal schema identifiers remain data.
    """
    alias = draft.replace("http://", "https://") if draft.startswith("http://") else draft.replace("https://", "http://") + "#"
    schema: dict[str, object] = {"$schema": alias, "type": "integer", "enum": [2], "default": {"$schema": "literal-data"}}
    normalized = canonical(schema)
    assert normalized["$schema"] == draft
    assert normalized["default"] == schema["default"]
    assert list(Draft7Validator(generation_view(schema)).iter_errors(2)) == []
    assert canonical({"$schema": "http://json-schema.org/schema#"})["$schema"] == DRAFT2020


@pytest.mark.parametrize("draft", [DRAFT7, DRAFT2020])
def test_wildcard_restrictions_cover_tuple_prefix_and_tail(draft: str) -> None:
    """
    Apply an explicit item constraint to every tuple slot and preserve the original types.

    Args:
        draft (str): Schema tuple dialect.

    Returns:
        None: Constraints neither miss prefix entries nor widen Boolean or positional schemas.
    """
    array: dict[str, object] = {"$schema": draft, "type": "array"}
    prefix = [{"type": "integer"}, True, False]
    array.update({"prefixItems": prefix, "items": True} if draft == DRAFT2020 else {"items": prefix, "additionalItems": True})
    restricted = restrict(array, ("*",), {"enum": [1]})
    validators.validator_for(restricted).check_schema(restricted)
    validator = validators.validator_for(restricted)(restricted)
    assert validator.is_valid([1, 1])
    assert not validator.is_valid([2])
    assert not validator.is_valid([1, 2])
    assert not validator.is_valid([1, 1, 1])


def test_property_and_map_restrictions_preserve_boolean_and_additional_schemas() -> None:
    """
    Keep forbidden properties forbidden and intersect map constraints without bypassing additionalProperties.

    Returns:
        None: Named and wildcard rules tighten every relevant map value without broadening the source contract.
    """
    schema: dict[str, object] = {
        "type": "object",
        "properties": {"free": True, "forbidden": False},
        "additionalProperties": {"type": "integer"},
    }
    constrained = restrict(restrict(schema, ("free",), {"type": "string"}), ("forbidden",), {"enum": [1]})
    validator = validators.validator_for(constrained)(constrained)
    assert validator.is_valid({"free": "yes"})
    assert not validator.is_valid({"free": 1})
    assert not validator.is_valid({"forbidden": 1})
    named = restrict(schema, ("extra",), {"minimum": 1})
    assert not validators.validator_for(named)(named).is_valid({"extra": "not an integer"})
    wildcard = restrict(schema, ("*",), {"enum": [1]})
    validator = validators.validator_for(wildcard)(wildcard)
    assert validator.is_valid({"free": 1, "extra": 1})
    assert not validator.is_valid({"extra": 2})
    assert not validator.is_valid({"free": "text"})


def test_chart_loader_allows_reference_looking_literal_data(tmp_path: Path) -> None:
    """
    Check schema references without interpreting an enum value as a schema document.

    Args:
        tmp_path (Path): Temporary chart containing reserved-looking payload keys.

    Returns:
        None: Literal identifiers survive chart loading and genuine external references are rejected.
    """
    (tmp_path / "Chart.yaml").write_text("apiVersion: v2\nname: literal\nversion: 1.0.0\n")
    (tmp_path / "values.yaml").write_text("{}\n")
    schema: dict[str, object] = {"type": "object", "properties": {"payload": {"enum": [{"$ref": "ordinary-string"}]}}}
    (tmp_path / "values.schema.json").write_text(json.dumps(schema))
    assert Chart.load(tmp_path).schema == schema
    schema["$dynamicRef"] = "https://example.invalid/not-downloaded"
    (tmp_path / "values.schema.json").write_text(json.dumps(schema))
    with pytest.raises(ValueError, match="only local"):
        Chart.load(tmp_path)

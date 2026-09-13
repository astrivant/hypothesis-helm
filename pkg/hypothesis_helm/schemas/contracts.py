"""
Typed boundaries for JSON schemas and round-trip YAML values.
"""

import json
import re
from typing import cast

from hypothesis.strategies import SearchStrategy
from hypothesis_jsonschema import from_schema
from jsonschema import validators

type Json = None | bool | int | float | str | list[Json] | dict[str, Json]

CONTROL_CHARACTERS = re.compile(r"[\x00-\x09\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def supported_generated_text(value: object) -> bool:
    """
    Exclude C0/C1 controls from sampled strings and keys, except LF and CR.

    Printable Unicode and configuration whitespace remain eligible. This is a
    sampling policy, not a change to chart schemas or user-provided values.

    Args:
        value (object): Generated JSON value, including nested objects and arrays.

    Returns:
        bool: Whether every generated string satisfies the text sampling policy.
    """
    if isinstance(value, str):
        return CONTROL_CHARACTERS.search(value) is None
    if isinstance(value, dict):
        return all(supported_generated_text(key) and supported_generated_text(item) for key, item in value.items())
    if isinstance(value, list):
        return all(supported_generated_text(item) for item in value)
    return True


def ordinary_generated_text(value: object) -> object:
    """
    Replace controls in fresh candidate text before validating or testing the candidate.

    Replacements preserve string lengths. Schema validation afterwards rejects
    incompatible patterns, enums, and object constraints.
    This function must not be applied to chart defaults or supplied values.

    Args:
        value (object): Fresh JSON Schema strategy candidate.

    Returns:
        object: Candidate containing ordinary text, still requiring schema validation.
    """
    if isinstance(value, str):
        return CONTROL_CHARACTERS.sub("a", value)
    if isinstance(value, dict):
        return {ordinary_generated_text(key): ordinary_generated_text(item) for key, item in value.items()}
    if isinstance(value, list):
        return [ordinary_generated_text(item) for item in value]
    return value


def configuration_key(values: dict[str, object]) -> str:
    """
    Identify a configuration independently of map order while preserving arrays and types.

    Args:
        values (dict[str, object]): Raw or normalized chart values.

    Returns:
        str: Canonical JSON identity retaining scalar types and ordered array contents.
    """
    return json.dumps(values, sort_keys=True, separators=(",", ":"), allow_nan=False)


def mapping(value: object) -> dict[str, object]:
    """
    Require an object mapping at a schema or YAML boundary.

    Args:
        value (object): Candidate value supplied by the property strategy.

    Returns:
        dict[str, object]: Resulting schema, values mapping, or structured report.
    """
    if not isinstance(value, dict):
        raise ValueError("expected an object mapping")
    return cast(dict[str, object], value)


def sequence(value: object) -> list[object]:
    """
    Require a JSON array at a schema or YAML boundary.

    Args:
        value (object): Candidate value supplied by the property strategy.

    Returns:
        list[object]: Result of the documented operation.
    """
    if not isinstance(value, list):
        raise ValueError("expected an array")
    return cast(list[object], value)


def number(value: object) -> int | float:
    """
    Require a numeric schema bound.

    Args:
        value (object): Candidate value supplied by the property strategy.

    Returns:
        int | float: Result of the documented operation.
    """
    if not isinstance(value, (int, float)):
        raise ValueError("expected a numeric schema bound")
    return value


def text(value: object) -> str:
    """
    Require a string schema reference or key.

    Args:
        value (object): Candidate value supplied by the property strategy.

    Returns:
        str: Serialized output or resolved strategy expression.
    """
    if not isinstance(value, str):
        raise ValueError("expected a string")
    return value


def json_value(value: object) -> Json:
    """
    Adapt parsed JSON and YAML values to the validator's recursive input type.

    Args:
        value (object): Candidate value supplied by the property strategy.

    Returns:
        Json: Result of the documented operation.
    """
    return cast(Json, value)


def schema_strategy(schema: dict[str, object]) -> SearchStrategy[object]:
    """
    Generate schema-valid samples without control-character fuzzing.

    Args:
        schema (dict[str, object]): JSON Schema defining the accepted value domain.

    Returns:
        SearchStrategy[object]: Result of the documented operation.
    """
    validator = validators.validator_for(schema)(schema)
    return (
        from_schema(cast(dict[str, Json], schema))
        .map(ordinary_generated_text)
        .filter(lambda candidate: validator.is_valid(json_value(candidate)))
    )

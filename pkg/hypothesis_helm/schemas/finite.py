"""
Explicit enumeration of small, finite JSON Schema domains.
"""

from __future__ import annotations

import itertools
import math

from jsonschema import validators

from hypothesis_helm.schemas.contracts import json_value, mapping, sequence


class NonFiniteSchema(ValueError):
    """
    The schema cannot be safely enumerated within the requested limit.
    """


def enumerate_values(schema: dict[str, object], limit: int = 1000) -> list[dict[str, object]]:
    """
    Enumerate a supported finite domain, or refuse rather than truncate it.

    Supports const, enum, booleans, null, bounded integers, closed objects and
    bounded arrays. Unsupported constraints fail closed for exhaustive mode.

    Args:
        schema (dict[str, object]): JSON Schema defining the accepted value domain.
        limit (int): Maximum candidate domain size allowed for exhaustive checking.

    Returns:
        list[dict[str, object]]: Result of the documented operation.
    """
    if limit < 1:
        raise ValueError("exhaustive limit must be positive")
    missing = object()

    def bounded(size: int) -> None:
        """
        Refuse candidate domains exceeding the configured enumeration limit.

        Args:
            size (int): Candidate domain size to compare with the configured limit.

        Returns:
            None: None. The operation completes through its documented side effects.
        """
        if size > limit:
            raise NonFiniteSchema(f"domain exceeds exhaustive limit {limit}")

    def domain(node: object) -> list[object]:
        """
        Enumerate the candidate values of a supported finite schema.

        Args:
            node (object): Current schema or template node.

        Returns:
            list[object]: Result of the documented operation.
        """
        if not isinstance(node, dict):
            raise NonFiniteSchema("boolean schemas require an explicit finite domain")
        if "const" in node:
            return [node["const"]]
        if "enum" in node:
            bounded(len(node["enum"]))
            return sequence(node["enum"])
        if any(k in node for k in ("$ref", "allOf", "anyOf", "oneOf", "if", "not")):
            raise NonFiniteSchema("compositions and references are not supported in exhaustive mode")
        kind = node.get("type")
        if kind == "boolean":
            return [False, True]
        if kind == "null":
            return [None]
        if kind == "integer":
            if "minimum" not in node or "maximum" not in node:
                raise NonFiniteSchema("integer domains need minimum and maximum")
            low, high = math.ceil(node["minimum"]), math.floor(node["maximum"])
            bounded(max(0, high - low + 1))
            return list(range(low, high + 1))
        if kind == "object":
            if node.get("additionalProperties") is not False or node.get("patternProperties"):
                raise NonFiniteSchema("objects need additionalProperties: false and no patterns")
            props = node.get("properties", {})
            choices = []
            size = 1
            for name, child in props.items():
                values = domain(child)
                if name not in node.get("required", []):
                    values = [missing, *values]
                choices.append(values)
                size *= len(values)
                bounded(size)
            return [dict((k, v) for k, v in zip(props, row, strict=True) if v is not missing) for row in itertools.product(*choices)]
        if kind == "array":
            if "maxItems" not in node or not isinstance(node.get("items"), dict):
                raise NonFiniteSchema("arrays need maxItems and a single finite items schema")
            item_choices = domain(node["items"])
            rows: list[object] = []
            low, high = node.get("minItems", 0), node["maxItems"]
            # Bound even empty/singleton item domains before looping.
            bounded(max(0, high - low + 1))
            for size in range(low, high + 1):
                bounded(len(rows) + len(item_choices) ** size)
                rows.extend(list(row) for row in itertools.product(item_choices, repeat=size))
            return rows
        raise NonFiniteSchema(f"no enumerable domain for type {kind!r}; use enum or sampling")

    candidates = domain(schema)
    validator = validators.validator_for(schema)(schema)
    values = [mapping(v) for v in candidates if validator.is_valid(json_value(v))]
    if not values:
        raise NonFiniteSchema("schema has no valid inputs in its declared finite domain")
    return values

"""
Explicit enumeration of small, finite JSON Schema domains.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Sequence
from functools import partial

from jsonschema import validators

from hypothesis_helm.schemas.contracts import json_value, mapping, sequence
from hypothesis_helm.schemas.replay import Replay, concatenate, select, transform


class NonFiniteSchema(ValueError):
    """
    The schema cannot be safely enumerated within the requested limit.
    """


def enumerate_values(schema: dict[str, object], limit: int = 1000) -> Sequence[dict[str, object]]:
    """
    Enumerate a supported finite domain, or refuse rather than truncate it.

    Supports const, enum, booleans, null, bounded integers, closed objects and
    bounded arrays. Unsupported constraints fail closed for exhaustive mode.

    Args:
        schema (dict[str, object]): JSON Schema defining the accepted value domain.
        limit (int): Maximum candidate domain size allowed for exhaustive checking.

    Returns:
        Sequence[dict[str, object]]: Valid configurations reconstructed from retained candidate positions.
    """
    if limit < 1:
        raise ValueError("exhaustive limit must be positive")
    schema = copy.deepcopy(schema)
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

    def domain(node: object) -> Sequence[object]:
        """
        Enumerate the candidate values of a supported finite schema.

        Args:
            node (object): Current schema or template node.

        Returns:
            Sequence[object]: Bounded domain reconstructed one position at a time.
        """
        if not isinstance(node, dict):
            raise NonFiniteSchema("boolean schemas require an explicit finite domain")
        if "const" in node:
            return Replay(1, lambda index: copy.deepcopy(node["const"]))
        if "enum" in node:
            bounded(len(node["enum"]))
            return transform(sequence(node["enum"]), copy.deepcopy)
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
            return range(low, high + 1)
        if kind == "object":
            if node.get("additionalProperties") is not False or node.get("patternProperties"):
                raise NonFiniteSchema("objects need additionalProperties: false and no patterns")
            props = node.get("properties", {})
            choices: list[Sequence[object]] = []
            size = 1
            for name, child in props.items():
                values = domain(child)
                if name not in node.get("required", []):
                    values = concatenate([missing], values)
                choices.append(values)
                size *= len(values)
                bounded(size)
            names = tuple(props)
            return Replay(
                size, lambda index: dict((k, v) for k, v in zip(names, product_at(choices, index), strict=True) if v is not missing)
            )
        if kind == "array":
            if "maxItems" not in node or not isinstance(node.get("items"), dict):
                raise NonFiniteSchema("arrays need maxItems and a single finite items schema")
            item_choices = domain(node["items"])
            rows: list[Sequence[object]] = []
            total = 0
            low, high = node.get("minItems", 0), node["maxItems"]
            # Bound even empty/singleton item domains before looping.
            bounded(max(0, high - low + 1))
            for size in range(low, high + 1):
                count = len(item_choices) ** size
                total += count
                bounded(total)
                rows.append(Replay(count, partial(repeated_at, item_choices, size)))
            return concatenate(*rows)
        raise NonFiniteSchema(f"no enumerable domain for type {kind!r}; use enum or sampling")

    candidates = domain(schema)
    validator = validators.validator_for(schema)(schema)
    positions = []
    for index, value in enumerate(candidates):
        if validator.is_valid(json_value(value)):
            mapping(value)
            positions.append(index)
    values = transform(select(candidates, positions), mapping)
    if not values:
        raise NonFiniteSchema("schema has no valid inputs in its declared finite domain")
    return values


def product_at(domains: Sequence[Sequence[object]], index: int) -> list[object]:
    """
    Decode one Cartesian position in the same order as itertools.product.

    Args:
        domains (Sequence[Sequence[object]]): Ordered finite factor domains.
        index (int): Valid mixed-radix position in their product.

    Returns:
        list[object]: Fresh values for one assignment, with the rightmost factor varying fastest.
    """
    row: list[object] = []
    for domain in reversed(domains):
        index, choice = divmod(index, len(domain))
        row.append(domain[choice])
    row.reverse()
    return row


def repeated_at(domain: Sequence[object], width: int, index: int) -> list[object]:
    """
    Reconstruct one array without retaining repeated domain-reference arrays.

    Args:
        domain (Sequence[object]): Finite element domain.
        width (int): Array length.
        index (int): Valid Cartesian position for this array length.

    Returns:
        list[object]: Fresh elements in the original Cartesian order.
    """
    result: list[object] = []
    for _ in range(width):
        index, choice = divmod(index, len(domain))
        result.append(domain[choice])
    result.reverse()
    return result

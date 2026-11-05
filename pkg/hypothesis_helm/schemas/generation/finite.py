"""
Explicit enumeration of small, finite JSON Schema domains.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Sequence
from functools import partial

from jsonschema import validators

from hypothesis_helm.exceptions.schemas import NonFiniteSchema
from hypothesis_helm.schemas.contracts import json_value, mapping, number, sequence
from hypothesis_helm.schemas.dialects import DRAFT2020, active, canonical, dialect
from hypothesis_helm.schemas.generation.replay import Replay, concatenate, select, transform

__all__ = ("enumerate_values", "product_at", "repeated_at")


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
    schema = canonical(schema)
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

    def domain(node: object, inherited: str = DRAFT2020) -> Sequence[object]:
        """
        Enumerate the candidate values of a supported finite schema.

        Args:
            node (object): Current schema or template node.
            inherited (str): Dialect inherited from the parent schema.

        Returns:
            Sequence[object]: Bounded domain reconstructed one position at a time.
        """
        if node is False:
            return []
        if not isinstance(node, dict):
            raise NonFiniteSchema("boolean schemas require an explicit finite domain")
        version = dialect(node, inherited)
        node = active(node, inherited)
        if any(keyword in node for keyword in ("$ref", "$dynamicRef", "$recursiveRef")):
            raise NonFiniteSchema("references are not supported in exhaustive mode")
        if "const" in node:
            return Replay(1, lambda index: copy.deepcopy(node["const"]))
        if "enum" in node:
            bounded(len(sequence(node["enum"])))
            return transform(sequence(node["enum"]), copy.deepcopy)
        if "$ref" in node or (not node.get("type") and any(k in node for k in ("allOf", "anyOf", "oneOf", "if", "not"))):
            raise NonFiniteSchema("compositions and references are not supported in exhaustive mode")
        kind = node.get("type")
        if kind == "boolean":
            return [False, True]
        if kind == "null":
            return [None]
        if kind == "integer":
            if "minimum" not in node or "maximum" not in node:
                raise NonFiniteSchema("integer domains need minimum and maximum")
            low, high = math.ceil(number(node["minimum"])), math.floor(number(node["maximum"]))
            bounded(max(0, high - low + 1))
            return range(low, high + 1)
        if kind == "object":
            if node.get("additionalProperties") is not False or node.get("patternProperties"):
                raise NonFiniteSchema("objects need additionalProperties: false and no patterns")
            props = mapping(node.get("properties", {}))
            choices: list[Sequence[object]] = []
            size = 1
            for name, child in props.items():
                values = domain(child, version)
                if name not in sequence(node.get("required", [])):
                    values = concatenate([missing], values)
                choices.append(values)
                size *= len(values)
                bounded(size)
            names = tuple(props)
            return Replay(
                size, lambda index: dict((k, v) for k, v in zip(names, product_at(choices, index), strict=True) if v is not missing)
            )
        if kind == "array":
            prefix = node.get("prefixItems", []) if version == DRAFT2020 else node.get("items", [])
            prefix = prefix if isinstance(prefix, list) else []
            tail = node.get("items", True) if version == DRAFT2020 or not prefix else node.get("additionalItems", True)
            if "maxItems" not in node and tail is not False:
                raise NonFiniteSchema("arrays need maxItems or a closed tuple")
            rows: list[Sequence[object]] = []
            total = 0
            low, high = int(number(node.get("minItems", 0))), int(number(node.get("maxItems", len(prefix))))
            if tail is False:
                high = min(high, len(prefix))
            # Bound even empty/singleton item domains before looping.
            bounded(max(0, high - low + 1))
            positional = [domain(child, version) for child in prefix[:high]]
            item_choices = domain(tail, version) if high > len(prefix) else []
            for size in range(low, high + 1):
                choices = positional[:size] + [item_choices] * max(0, size - len(prefix))
                count = math.prod(len(choice) for choice in choices)
                total += count
                bounded(total)
                rows.append(Replay(count, partial(product_at, choices)))
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

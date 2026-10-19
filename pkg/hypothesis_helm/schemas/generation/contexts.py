"""
Propose small required-field completions before solving the complete chart schema.
"""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Iterable, Iterator
from typing import TYPE_CHECKING

from hypothesis_helm.schemas.contracts import mapping, sequence
from hypothesis_helm.schemas.dialects import DRAFT2020, dialect, resolve, walk

if TYPE_CHECKING:
    from jsonschema.exceptions import ValidationError

__all__ = ("context_proposal", "context_scopes", "literal_repairs")

_MISSING = object()
_LOCAL_SCHEMA_BYTES = 65536


def context_proposal(
    schema: dict[str, object],
    candidate: dict[str, object],
    path: tuple[str | int, ...],
    *,
    focus: tuple[str | int, ...] | None = None,
) -> dict[str, object] | None:
    """
    Retain supplied siblings and generate only missing required values along a binding.

    This is a proposal distribution, not an equivalent schema transformation.
    Cross-field constraints remain the complete chart validator's responsibility;
    an invalid proposal must fall back to the unrestricted context strategy.

    Args:
        schema (dict[str, object]): Complete generation schema and reference scope.
        candidate (dict[str, object]): Baseline with the concrete target already inserted.
        path (tuple[str | int, ...]): Protected target whose value must remain unchanged.
        focus (tuple[str | int, ...] | None): Invalid ancestor to solve locally while retaining its dependent constraints.

    Returns:
        dict[str, object] | None: Small generation schema, or None for unsupported recursive contexts.
    """
    if focus is not None and (not focus or len(focus) >= len(path) or path[: len(focus)] != focus):
        return None

    def visit(raw: object, current: object, remaining: tuple[str | int, ...] | None, seen: frozenset[int | str]) -> object:
        """
        Fill required siblings without traversing unrelated optional schema branches.

        Args:
            raw (object): Local schema declaration.
            current (object): Existing value, or the private missing sentinel.
            remaining (tuple[str | int, ...] | None): Remaining protected path, or None for a sibling.
            seen (frozenset[int | str]): Ancestors used to reject recursive expansion.

        Returns:
            object: Proposed Boolean or mapping schema, or None when recursion prevents a bounded proposal.
        """
        if current is not _MISSING and not remaining:
            return {"const": copy.deepcopy(current)}
        if raw is False:
            return False
        if not isinstance(raw, dict):
            raw = {}
        marker = str(raw["$ref"]) if "$ref" in raw else id(raw)
        if marker in seen:
            return None
        seen = seen | {marker}
        node = resolve(raw, schema)
        version = dialect(node, dialect(schema))

        # Solve a small invalid ancestor with its own dependent constraints.
        # References retain the general solver because detaching their scope
        # would change meaning. Unrelated chart branches stay frozen below.
        if focus is not None and remaining and len(path) - len(remaining) == len(focus):
            if len(json.dumps(node).encode()) > _LOCAL_SCHEMA_BYTES or any(
                {"$ref", "$dynamicRef", "$recursiveRef"} & child.keys() for child in walk(node)
            ):
                return None
            target = current
            for part in remaining:
                if isinstance(part, int) and isinstance(target, list) and 0 <= part < len(target):
                    target = target[part]
                elif isinstance(part, str) and isinstance(target, dict) and part in target:
                    target = target[part]
                else:
                    return None
            constraint: dict[str, object] = {"enum": [copy.deepcopy(target)]}
            for part in reversed(remaining):
                if isinstance(part, int):
                    if part < 0 or part > len(path):
                        return None
                    keyword = "prefixItems" if version == DRAFT2020 else "items"
                    constraint = {"type": "array", "minItems": part + 1, keyword: [True] * part + [constraint]}
                else:
                    constraint = {"type": "object", "required": [part], "properties": {part: constraint}}
            return {"$schema": version, "allOf": [copy.deepcopy(node), constraint]}

        # Alternatives retain separate shapes. Complete validation checks their
        # original exclusivity, guards and sibling constraints after the draw.
        for keyword in ("anyOf", "oneOf"):
            if keyword in node:
                alternatives = [visit(branch, current, remaining, seen) for branch in sequence(node[keyword])]
                if any(branch is None for branch in alternatives):
                    return None
                return {"anyOf": alternatives}
        types = [node["type"]] if isinstance(node.get("type"), str) else sequence(node.get("type", []))
        kind = "array" if remaining and isinstance(remaining[0], int) else "object" if remaining else None
        if kind is not None and types and kind not in types:
            return False
        if kind == "object" or (kind is None and node.get("type") == "object"):
            existing = mapping(current) if isinstance(current, dict) else {}
            keys = set(existing) | {str(key) for key in sequence(node.get("required", []))}
            if remaining:
                keys.add(str(remaining[0]))
            properties = mapping(node.get("properties", {}))
            patterns = mapping(node.get("patternProperties", {}))
            children: dict[str, object] = {}
            for key in sorted(keys):
                declarations = ([properties[key]] if key in properties else []) + [
                    child for pattern, child in patterns.items() if re.search(pattern, key)
                ]
                # One applicable declaration proposes a value; the original
                # validator still enforces every intersecting pattern and guard.
                child = declarations[0] if declarations else node.get("additionalProperties", True)
                tail = remaining[1:] if remaining and key == remaining[0] else None
                proposed = visit(child, existing.get(key, _MISSING), tail, seen)
                if proposed is None:
                    return None
                children[key] = proposed
            return {"type": "object", "properties": children, "required": sorted(keys), "additionalProperties": False}
        if kind == "array" or (kind is None and node.get("type") == "array"):
            existing_items = current if isinstance(current, list) else []
            size = max(len(existing_items), int(str(node.get("minItems", 0))), int(remaining[0]) + 1 if remaining else 0)
            # A proposal must not allocate a huge minimum-sized collection.
            # The general solver retains responsibility for larger contexts.
            if size > max(1, len(existing_items) + len(path)):
                return None
            prefix = node.get("prefixItems", []) if version == DRAFT2020 else node.get("items", [])
            prefix = prefix if isinstance(prefix, list) else []
            items = []
            for index in range(size):
                child = (
                    prefix[index]
                    if index < len(prefix)
                    else node.get("items" if version == DRAFT2020 or not prefix else "additionalItems", True)
                )
                tail = remaining[1:] if remaining and index == remaining[0] else None
                proposed = visit(child, existing_items[index] if index < len(existing_items) else _MISSING, tail, seen)
                if proposed is None:
                    return None
                items.append(proposed)
            result: dict[str, object] = {"type": "array", "minItems": size, "maxItems": size}
            if items:
                result["prefixItems"] = items
            return result
        return {"$schema": version, **node}

    proposed = visit(schema, candidate, path, frozenset())
    return {"$schema": DRAFT2020, **proposed} if isinstance(proposed, dict) else None


def literal_repairs(errors: Iterable[ValidationError], protected: tuple[str | int, ...]) -> Iterator[tuple[tuple[str | int, ...], object]]:
    """
    Offer declared literal changes without modifying a protected target or its parents.

    These proposals do not establish which Boolean branch applies. The complete
    validator must accept each repaired document before it can be used.

    Args:
        errors (Iterable[ValidationError]): Errors from complete-document validation.
        protected (tuple[str | int, ...]): Concrete target binding to preserve.

    Yields:
        tuple[tuple[str | int, ...], object]: Candidate path and declared literal, in validator order.
    """
    pending = list(reversed(list(errors)))
    while pending:
        error = pending.pop()
        pending.extend(reversed(error.context))
        raw_path = tuple(error.absolute_path)
        if not all(isinstance(part, (str, int)) for part in raw_path):
            continue
        path = tuple(part for part in raw_path if isinstance(part, (str, int)))
        # An ancestor replacement or a nested change would alter the requested
        # value. Literal repairs are exclusively for independent context fields.
        if not path or path[: len(protected)] == protected or protected[: len(path)] == path:
            continue
        if error.validator == "const":
            yield path, error.validator_value
        elif error.validator == "enum" and isinstance(error.validator_value, list):
            for value in error.validator_value:
                yield path, value


def context_scopes(errors: Iterable[ValidationError], protected: tuple[str | int, ...]) -> tuple[tuple[str | int, ...], ...]:
    """
    Select invalid non-root ancestors of a target, deepest first.

    Args:
        errors (Iterable[ValidationError]): Complete-document validation failures.
        protected (tuple[str | int, ...]): Concrete target whose value remains fixed.

    Returns:
        tuple[tuple[str | int, ...], ...]: Distinct ancestor scopes suitable for bounded local proposals.
    """
    scopes: set[tuple[str | int, ...]] = set()
    pending = list(errors)
    while pending:
        error = pending.pop()
        pending.extend(error.context)
        raw = tuple(error.absolute_path)
        if not all(isinstance(part, (str, int)) for part in raw):
            continue
        path = tuple(part for part in raw if isinstance(part, (str, int)))
        if path and len(path) < len(protected) and protected[: len(path)] == path:
            scopes.add(path)
    return tuple(sorted(scopes, key=lambda path: (-len(path), repr(path))))

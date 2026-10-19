"""
Propose small required-field completions before solving the complete chart schema.
"""

from __future__ import annotations

import copy
import re

from hypothesis_helm.schemas.contracts import mapping, sequence
from hypothesis_helm.schemas.dialects import DRAFT2020, dialect, resolve

__all__ = ("context_proposal",)

_MISSING = object()


def context_proposal(schema: dict[str, object], candidate: dict[str, object], path: tuple[str | int, ...]) -> dict[str, object] | None:
    """
    Retain supplied siblings and generate only missing required values along a binding.

    This is a proposal distribution, not an equivalent schema transformation.
    Cross-field constraints remain the complete chart validator's responsibility;
    an invalid proposal must fall back to the unrestricted context strategy.

    Args:
        schema (dict[str, object]): Complete generation schema and reference scope.
        candidate (dict[str, object]): Baseline with the concrete target already inserted.
        path (tuple[str | int, ...]): Protected target whose value must remain unchanged.

    Returns:
        dict[str, object] | None: Small generation schema, or None for unsupported recursive contexts.
    """

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

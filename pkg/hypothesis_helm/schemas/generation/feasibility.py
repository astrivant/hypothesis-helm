"""
Reject definite path/type conflicts before asking Hypothesis for sibling context.
"""

import re

from jsonschema import validators

from hypothesis_helm.schemas.contracts import json_value, mapping, sequence
from hypothesis_helm.schemas.dialects import DRAFT4, DRAFT6, DRAFT7, DRAFT2020, active, dialect, pointer_target

__all__ = ("compatible_binding",)


def compatible_binding(schema: dict[str, object], path: tuple[str | int, ...], value: object) -> bool:
    """
    Determine whether a binding avoids known structural contradictions.

    Args:
        schema (dict[str, object]): Complete schema defining the candidate's input space.
        path (tuple[str | int, ...]): Concrete binding; strings are keys and integers are array indices.
        value (object): Complete leaf value to place at that path.

    Returns:
        bool: False only for a proven conflict; True still requires complete-document validation.
    """
    validator = validators.validator_for(schema)(schema)

    def visit(raw: object, remaining: tuple[str | int, ...], version: str, seen: frozenset[tuple[int, tuple[str | int, ...]]]) -> bool:
        """
        Check only constraints whose outcome is determined by the selected path and leaf.

        Args:
            raw (object): Current Boolean or object schema.
            remaining (tuple[str | int, ...]): Components below this schema's instance location.
            version (str): Inherited schema dialect.
            seen (frozenset[tuple[int, tuple[str | int, ...]]]): Reference states already visited.

        Returns:
            bool: Whether the partial binding may have a valid completion.
        """
        if isinstance(raw, bool):
            return raw
        if not isinstance(raw, dict):
            return True
        marker = (id(raw), remaining)
        if marker in seen:
            return True
        seen = seen | {marker}
        version = dialect(raw, version)
        node = active(raw, version)
        if not remaining:
            # A complete leaf can be validated exactly, including local references.
            return validator.evolve(schema={"$schema": version, **node}).is_valid(json_value(value))
        if "$ref" in node:
            target, target_version = pointer_target(schema, node["$ref"])
            if not visit(target, remaining, target_version, seen):
                return False
            if version in (DRAFT4, DRAFT6, DRAFT7):
                return True
        if any(not visit(branch, remaining, version, seen) for branch in sequence(node.get("allOf", []))):
            return False
        for keyword in ("anyOf", "oneOf"):
            if keyword in node and not any(visit(branch, remaining, version, seen) for branch in sequence(node[keyword])):
                return False
        # The guard may depend on unknown siblings. Keep both possible outcomes.
        if "if" in node and not any(visit(node.get(arm, True), remaining, version, seen) for arm in ("then", "else")):
            return False
        head, *tail = remaining
        kind = "array" if isinstance(head, int) else "object"
        types = [node["type"]] if isinstance(node.get("type"), str) else sequence(node.get("type", []))
        if types and kind not in types:
            return False
        if isinstance(head, int):
            maximum = node.get("maxItems")
            if isinstance(maximum, int) and head >= maximum:
                return False
            prefix = node.get("prefixItems", []) if version == DRAFT2020 else node.get("items", [])
            prefix = prefix if isinstance(prefix, list) else []
            item = (
                prefix[head] if head < len(prefix) else node.get("items" if version == DRAFT2020 or not prefix else "additionalItems", True)
            )
            return visit(item, tuple(tail), version, seen)
        if "propertyNames" in node:
            names = node["propertyNames"]
            if not validator.evolve(schema=names).is_valid(head):
                return False
        properties = mapping(node.get("properties", {}))
        children = [properties[head]] if head in properties else []
        children.extend(child for pattern, child in mapping(node.get("patternProperties", {})).items() if re.search(pattern, head))
        if not children:
            children = [node.get("additionalProperties", True)]
        # Missing siblings, negation and annotation-dependent constraints remain
        # the responsibility of the complete schema, never guessed from this path.
        return all(visit(child, tuple(tail), version, seen) for child in children)

    return visit(schema, path, dialect(schema), frozenset())

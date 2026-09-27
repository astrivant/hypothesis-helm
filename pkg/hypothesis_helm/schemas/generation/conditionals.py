"""
Simplify generation guards whose inputs are fixed by the schema itself.
"""

import copy

from jsonschema import validators

from hypothesis_helm.schemas.contracts import json_value, mapping, sequence
from hypothesis_helm.schemas.dialects import active, dialect

__all__ = ("fixed_branches",)


def fixed_branches(schema: dict[str, object]) -> dict[str, object]:
    """
    Resolve root-level guards only when every inspected property is a required literal.

    Args:
        schema (dict[str, object]): Complete generation contract, retaining references and dialect.

    Returns:
        dict[str, object]: Equivalent contract with decidable guards removed from root applicators.
    """
    node = active(schema)
    if node.get("type") != "object":
        return copy.deepcopy(schema)
    properties = mapping(node.get("properties", {}))
    fixed: dict[str, object] = {}
    for key in sequence(node.get("required", [])):
        value = properties.get(str(key))
        if not isinstance(value, dict):
            continue
        field = active(value, dialect(node))
        if "const" in field:
            fixed[str(key)] = field["const"]
        elif isinstance(field.get("enum"), list) and len(sequence(field["enum"])) == 1:
            fixed[str(key)] = sequence(field["enum"])[0]
    validator = validators.validator_for(schema)(schema)

    def visit(raw: object) -> object:
        """
        Reduce applicators at the same instance location as the established literals.

        Args:
            raw (object): Root schema or same-instance Boolean branch.

        Returns:
            object: Copied branch; nested property scopes are deliberately left alone.
        """
        if not isinstance(raw, dict):
            return raw
        result = copy.deepcopy(raw)
        condition = active(raw, dialect(node)).get("if")
        if isinstance(condition, dict) and set(condition) <= {"properties", "required"}:
            keys = set(mapping(condition.get("properties", {}))) | set(sequence(condition.get("required", [])))
            if keys <= fixed.keys():
                # These are schema guarantees, not values observed in one baseline.
                selected = "then" if validator.evolve(schema=condition).is_valid(json_value(fixed)) else "else"
                branch = result.get(selected, {})
                for keyword in ("if", "then", "else"):
                    result.pop(keyword, None)
                sequence(result.setdefault("allOf", [])).append(branch)
        for keyword in ("allOf", "anyOf", "oneOf"):
            if keyword in result:
                result[keyword] = [visit(branch) for branch in sequence(result[keyword])]
        return result

    return mapping(visit(schema))

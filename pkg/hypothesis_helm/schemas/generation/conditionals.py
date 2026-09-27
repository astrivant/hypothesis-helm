"""
Simplify generation guards whose inputs are fixed by the schema itself.
"""

import copy

from jsonschema import validators

from hypothesis_helm.schemas.contracts import json_value, mapping, sequence
from hypothesis_helm.schemas.dialects import active, dialect
from hypothesis_helm.schemas.generation.feasibility import compatible_binding

__all__ = ("bound_branches", "fixed_branches")


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


def bound_branches(schema: dict[str, object], path: tuple[str | int, ...], value: object) -> dict[str, object]:
    """
    Remove Boolean alternatives contradicted by a required path/value binding.

    The result is a generation view valid only in conjunction with that binding.
    Original-schema validation remains authoritative. Shared item and key-pattern
    schemas are unchanged so specializing one entry cannot restrict other entries.

    Args:
        schema (dict[str, object]): Complete context schema, already requiring the binding.
        path (tuple[str | int, ...]): Concrete target keys and indices.
        value (object): Complete value required at the target.

    Returns:
        dict[str, object]: Context with impossible root alternatives removed and surviving guards retained.
    """

    def possible(raw: object, version: str) -> bool:
        """
        Preserve unresolved alternatives and exclude only established conflicts.

        Args:
            raw (object): Alternative Boolean or object schema.
            version (str): Dialect inherited at this instance location.

        Returns:
            bool: Whether the binding may satisfy this alternative.
        """
        return raw is not False and (not isinstance(raw, dict) or compatible_binding(raw, path, value, root=schema, inherited=version))

    def visit(raw: object, inherited: str) -> object:
        """
        Specialize same-instance applicators without distributing branch products.

        Args:
            raw (object): Current Boolean branch at the root instance location.
            inherited (str): Enclosing schema dialect.

        Returns:
            object: Copied branch, still preserving constraints unrelated to the binding.
        """
        if not isinstance(raw, dict):
            return raw
        version = dialect(raw, inherited)
        node = active(raw, version)
        result = copy.deepcopy(raw)
        for keyword in ("anyOf", "oneOf"):
            if keyword not in node:
                continue
            branches = [branch for branch in sequence(node[keyword]) if possible(branch, version)]
            if not branches:
                return False
            if len(branches) == 1:
                result.pop(keyword)
                sequence(result.setdefault("allOf", [])).append(branches[0])
            else:
                # Keep oneOf exclusive: surviving branches can still overlap.
                result[keyword] = [visit(branch, version) for branch in branches]
        if "if" in node:
            then, otherwise = node.get("then", True), node.get("else", True)
            accepted, rejected = possible(then, version), possible(otherwise, version)
            if not accepted and not rejected:
                return False
            if accepted != rejected:
                guard = node["if"] if accepted else {"not": node["if"]}
                branch = then if accepted else otherwise
                for keyword in ("if", "then", "else"):
                    result.pop(keyword, None)
                # Rejecting an arm also requires its opposite guard. Dropping the
                # guard would admit sibling values that select the rejected arm.
                sequence(result.setdefault("allOf", [])).extend([guard, branch])
        if "allOf" in result:
            result["allOf"] = [visit(branch, version) for branch in sequence(result["allOf"])]
        return result

    result = visit(schema, dialect(schema))
    return mapping(result) if isinstance(result, dict) else {"not": {}}

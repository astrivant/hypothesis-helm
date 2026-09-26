"""
Lower schema dialects for the Draft 7 generator while keeping full validation separate.
"""

import copy

from hypothesis_helm.schemas.contracts import mapping, sequence
from hypothesis_helm.schemas.dialects import (
    DRAFT7,
    DRAFT2019,
    DRAFT2020,
    active,
    dialect,
    fragment,
    map_children,
    numeric_bounds,
    resolve,
    walk,
)

__all__ = ("generation_view", "validation_view")


def _conjoin(node: dict[str, object], clause: dict[str, object]) -> None:
    """
    Add a generated clause without replacing an existing conjunction.

    Args:
        node (dict[str, object]): Mutable generated schema.
        clause (dict[str, object]): Additional condition.

    Returns:
        None: Both original and lowered constraints remain active.
    """
    sequence(node.setdefault("allOf", [])).append(clause)


def generation_view(schema: dict[str, object], *, require_equivalent: bool = False) -> dict[str, object]:
    """
    Translate supported constraints and broaden unsupported annotation-dependent conditions safely.

    References expand before keyword renaming, so pointers into tuple schemas do not move underneath their callers.
    The result is for candidate generation only. Every candidate must still pass the original validator; this view
    must never be used as proof of the original input domain or exhaustive coverage.

    Args:
        schema (dict[str, object]): Authoritative schema or an explicit generation-only view.
        require_equivalent (bool): Refuse approximations when the result will be used for validation.

    Returns:
        dict[str, object]: Draft 7 generation schema with preserved or broader acceptance.

    Raises:
        ValueError: Dynamic, recursive or nested-resource references cannot be resolved by this generator.
    """
    root = schema

    def lower(raw: object, inherited: str, refs: tuple[str, ...] = ()) -> tuple[object, bool]:
        """
        Lower a subtree and report whether its acceptance was preserved exactly.

        Args:
            raw (object): Boolean or object subschema.
            inherited (str): Enclosing schema dialect.
            refs (tuple[str, ...]): Local references already expanded in this branch.

        Returns:
            tuple[object, bool]: Generation subtree and equivalence indicator for Boolean composition.
        """
        if not isinstance(raw, dict):
            return raw, True
        version = dialect(raw, inherited)
        node = active(raw, inherited)
        if "$dynamicRef" in node or "$recursiveRef" in node:
            raise ValueError("dynamic and recursive JSON Schema references are not supported for input generation")
        if raw is not root and ("$id" in raw or "id" in raw) and any("$ref" in child for child in walk(raw)):
            raise ValueError("references in nested JSON Schema resources are not supported for input generation")
        if "$ref" in node:
            reference = str(node["$ref"])
            if reference in refs:
                raise ValueError(f"recursive schema reference cannot be generated: {reference}")
            return lower(resolve(fragment(node, {"$schema": version}), root, refs), version, (*refs, reference))

        exact_by_id: dict[int, bool] = {}

        def child(value: object) -> object:
            """
            Retain the equivalence result for a child before composing its parent.

            Args:
                value (object): Child schema.

            Returns:
                object: Lowered child, with equivalence tracked by its original identity.
            """
            converted, exact = lower(value, version, refs)
            exact_by_id[id(value)] = exact
            return converted

        result = map_children(node, child, definitions=False)
        for key in ("$schema", "$id", "id", "$anchor", "$dynamicAnchor", "$recursiveAnchor", "$defs", "definitions"):
            result.pop(key, None)
        exact = all(exact_by_id.values())
        result = numeric_bounds(result, version)
        if version == DRAFT2020:
            prefix = result.pop("prefixItems", None)
            if isinstance(prefix, list):
                tail = result.pop("items", True)
                result["items"] = prefix
                result["additionalItems"] = tail
        if version in (DRAFT2019, DRAFT2020):
            required = mapping(result.pop("dependentRequired", {}))
            dependent = mapping(result.pop("dependentSchemas", {}))
            for name in required.keys() | dependent.keys():
                requirement: object = {"required": required[name]} if name in required else {}
                if name in dependent:
                    requirement = {"allOf": [requirement, dependent[name]]}
                _conjoin(result, {"dependencies": {name: requirement}})
            if "contains" in result:
                minimum = result.pop("minContains", 1)
                maximum = result.pop("maxContains", None)
                if minimum == 0:
                    result.pop("contains")
                # Draft 7 can express existence, but not arbitrary match counts.
                if minimum not in (0, 1) or maximum is not None:
                    exact = False
            else:
                result.pop("minContains", None)
                result.pop("maxContains", None)
            for keyword in ("unevaluatedItems", "unevaluatedProperties"):
                if keyword in result:
                    if result[keyword] is not True:
                        exact = False
                    result.pop(keyword)

        # Broadening a child is unsafe under negation, exclusive alternatives,
        # or a branch selector. Broaden the enclosing operator instead.
        if "not" in node and not exact_by_id.get(id(node["not"]), True):
            result.pop("not", None)
        if "oneOf" in node and any(not exact_by_id.get(id(value), True) for value in sequence(node["oneOf"])):
            _conjoin(result, {"anyOf": result.pop("oneOf")})
        if "if" in node and not exact_by_id.get(id(node["if"]), True):
            result.pop("if", None)
            _conjoin(result, {"anyOf": [result.pop("then", {}), result.pop("else", {})]})
        if "if" in result:
            condition = result.pop("if")
            present = "then" in result or "else" in result
            accepted = result.pop("then", {})
            rejected = result.pop("else", {})
            if present:
                # (condition AND then) OR (NOT condition AND else) is equivalent.
                # Lower it here: hypothesis-jsonschema 0.23.1 can mutate its shared
                # FALSEY marker when an impossible conditional is canonicalized.
                _conjoin(result, {"anyOf": [{"allOf": [condition, accepted]}, {"allOf": [{"not": condition}, rejected]}]})
        return result, exact

    converted, equivalent = lower(root, dialect(root))
    if require_equivalent and not equivalent:
        raise ValueError("schema dialect conversion requires annotation-dependent constraints that cannot be lowered exactly")
    result = mapping(converted)
    return {"$schema": DRAFT7, **copy.deepcopy(result)}


def validation_view(schema: dict[str, object]) -> dict[str, object]:
    """
    Upgrade legacy input contracts before combining them with modern compiler or configuration rules.

    Args:
        schema (dict[str, object]): Original standalone schema with its own dialect.

    Returns:
        dict[str, object]: Equivalent Draft 2020-12 contract; unsupported conversions fail explicitly.
    """
    from hypothesis_helm.schemas.dialects import canonical

    if dialect(schema) == DRAFT2020:
        return canonical(schema)
    legacy = generation_view(schema, require_equivalent=True)

    def modern(raw: object) -> object:
        """
        Upgrade a resolved Draft 7 node without changing JSON literals.

        Args:
            raw (object): Current Draft 7 schema node.

        Returns:
            object: Equivalent modern schema node.
        """
        if not isinstance(raw, dict):
            return raw
        result = map_children(raw, modern)
        result.pop("$schema", None)
        items = result.get("items")
        if isinstance(items, list):
            result["prefixItems"] = items
            result["items"] = result.pop("additionalItems", True)
        else:
            result.pop("additionalItems", None)
        dependencies = mapping(result.pop("dependencies", {}))
        required = {name: value for name, value in dependencies.items() if isinstance(value, list)}
        dependent = {name: value for name, value in dependencies.items() if not isinstance(value, list)}
        if required:
            result["dependentRequired"] = required
        if dependent:
            result["dependentSchemas"] = dependent
        return result

    return {"$schema": DRAFT2020, **mapping(modern(legacy))}

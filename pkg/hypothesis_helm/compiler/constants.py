"""
Define typed zero candidates as generation preferences, never as validity guarantees.
"""

from __future__ import annotations

import copy
from collections.abc import Callable, Mapping
from types import MappingProxyType

from hypothesis_helm.schemas.model import MISSING, Missing, ValueNode, ValuesModel

# Factories return fresh containers; Boolean false and integer zero remain distinct types.
ZERO_FACTORIES: Mapping[str, Callable[[], object]] = MappingProxyType(
    {"boolean": bool, "integer": int, "number": float, "string": str, "array": list, "object": dict, "null": lambda: None}
)


def zero_candidate(node: ValueNode) -> object | Missing:
    """
    Propose typed zeros through the shared values model without guessing unknown field types.

    Constraints such as minimum, enum, required items, or rendered Kubernetes API
    requirements may reject this proposal. The caller must validate the entire candidate.

    Args:
        node (ValueNode): Declared field or container in the compiler's shared model.

    Returns:
        object | Missing: Preferred concrete candidate, or MISSING for an unknown type.
    """
    declared = node.schema.get("type")
    kinds = declared if isinstance(declared, list) else [declared]
    if declared is None:
        inferred = {bool: "boolean", int: "integer", float: "number", str: "string", list: "array", dict: "object", type(None): "null"}
        kinds = [inferred.get(node.python_type) if isinstance(node.python_type, type) else None]
        if node.children:
            kinds = ["object"]
    # Prefer a non-null member of a union; explicit null is only a typed candidate.
    kind = next((name for name in ZERO_FACTORIES if name in kinds), None)
    if kind is None:
        return MISSING
    return ZERO_FACTORIES[kind]()


def fill_missing(model: ValuesModel, values: dict[str, object], referenced: set[tuple[str, ...]]) -> dict[str, object]:
    """
    Preserve supplied values and deterministically populate required or referenced typed gaps.

    Args:
        model (ValuesModel): Shared input declarations.
        values (dict[str, object]): Original values; false, zero and explicit null remain supplied.
        referenced (set[tuple[str, ...]]): Known template selectors requiring a scaffold entry.

    Returns:
        dict[str, object]: Example values using declared defaults, constants, or typed zeros.
    """

    def visit(node: ValueNode, supplied: object) -> object:
        """
        Fill a subtree without guessing an unknown type or overwriting an existing value.

        Args:
            node (ValueNode): Shared declaration.
            supplied (object): Existing subtree or the missing sentinel.

        Returns:
            object: Concrete subtree or MISSING when no value or type is known.
        """
        value = copy.deepcopy(supplied)
        if isinstance(value, Missing):
            value = (
                copy.deepcopy(node.schema["default"])
                if "default" in node.schema
                else (copy.deepcopy(node.schema["const"]) if "const" in node.schema else zero_candidate(node))
            )
        if isinstance(value, dict):
            for name, child in node.children.items():
                if name in value or child.required or any(path[: len(child.path)] == child.path for path in referenced):
                    replacement = visit(child, value.get(name, MISSING))
                    if not isinstance(replacement, Missing):
                        value[name] = replacement
        elif isinstance(value, list) and node.item is not None:
            value = [visit(node.item, item) for item in value]
        return value

    result = visit(model.root, values)
    assert isinstance(result, dict)
    return result

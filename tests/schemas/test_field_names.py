"""
Preserve schema field names that collide with generated constructor parameters.
"""

from __future__ import annotations

from hypothesis_helm.schemas.model import ValuesModel


def test_constructor_names_roundtrip_in_nested_objects() -> None:
    """
    Keep original keys when attrs needs a different Python attribute name.

    Returns:
        None: Root and nested records round-trip without aliases losing data.
    """
    names = ("self", "self_", "self__", "values_extra", "values_extra_", "class", "value_5")
    properties: dict[str, object] = {name: {"type": "string"} for name in names}
    schema: dict[str, object] = {
        "type": "object",
        "properties": {**properties, "nested": {"type": "object", "properties": properties}},
    }
    values: dict[str, object] = {name: name for name in names}
    document = {**values, "nested": values}
    model = ValuesModel.from_schema(schema)

    assert model.unstructure(model.structure(document)) == document
    assert model.unstructure(model.structure({"nested": {}})) == {"nested": {}}
    assert model.root.children["self"].attribute not in names
    assert len({child.attribute for child in model.root.children.values()}) == len(model.root.children)

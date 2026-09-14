"""
Extract finite independent factors without enumerating their Cartesian product.
"""

from collections.abc import Sequence

from attrs import define, field

from hypothesis_helm.schemas.contracts import configuration_key
from hypothesis_helm.schemas.finite import NonFiniteSchema, enumerate_values
from hypothesis_helm.schemas.model import ValueNode, ValuesModel
from hypothesis_helm.schemas.replay import select


@define
class FactorSpace:
    """
    Store finite factor domains and the required object skeleton.

    Attributes:
        paths (list[tuple[str, ...]]): Independent configurable factor paths.
        domains (list[Sequence[dict[str, object]]]): Assignments, including optional omission.
        skeleton (dict[str, object]): Required nested and empty object containers.
        nodes (list[ValueNode]): Shared declarations for each finite factor.
    """

    paths: list[tuple[str, ...]]
    domains: list[Sequence[dict[str, object]]]
    skeleton: dict[str, object]
    nodes: list[ValueNode] = field(factory=list)


def factor_space(schema: dict[str, object] | ValuesModel, limit: int = 10000) -> FactorSpace:
    """
    Extract finite factors while bounding each individual domain.

    Args:
        schema (dict[str, object] | ValuesModel): Shared model or original closed values schema.
        limit (int): Maximum candidate values per factor.

    Returns:
        FactorSpace: Domains without their cross product.
    """
    if limit < 1:
        raise ValueError("factor domain limit must be positive")
    model = schema if isinstance(schema, ValuesModel) else ValuesModel.from_schema(schema)
    schema = model.root.schema
    nodes: list[ValueNode] = []
    factors: list[tuple[str, ...]] = []
    domains: list[Sequence[dict[str, object]]] = []
    skeleton: dict[str, object] = {}

    def discover(declaration: ValueNode, base: dict[str, object]) -> None:
        """
        Extract finite domains from required closed object properties.

        Args:
            declaration (ValueNode): Shared object declaration.
            base (dict[str, object]): Skeleton retaining required empty objects.

        Returns:
            None: Populates factors, domains and the object skeleton.
        """
        node, path = declaration.schema, declaration.path
        if node.get("additionalProperties") is not False or node.get("patternProperties"):
            raise NonFiniteSchema(f"permutations need closed objects at {path!r}; set additionalProperties: false")
        for name, child in declaration.children.items():
            child_schema = child.schema
            child_path = child.path
            if child.required and child_schema.get("type") == "object" and "enum" not in child_schema and "const" not in child_schema:
                nested: dict[str, object] = {}
                base[name] = nested
                discover(child, nested)
            else:
                wrapper: dict[str, object] = {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {name: child_schema},
                    "required": [name] if child.required else [],
                }
                try:
                    choices = enumerate_values(wrapper, limit)
                except NonFiniteSchema as exc:
                    raise NonFiniteSchema(f"cannot cover permutations at {child_path!r}: {exc}") from exc
                factors.append(child_path)
                nodes.append(child)
                positions = {configuration_key(choice): index for index, choice in enumerate(choices)}
                domains.append(select(choices, tuple(positions.values())))

    if schema.get("type") != "object":
        raise NonFiniteSchema("permutations require an object schema")
    if "enum" in schema or "const" in schema:
        raise NonFiniteSchema("root enum/const schemas should use --exhaustive")
    discover(model.root, skeleton)
    return FactorSpace(factors, domains, skeleton, nodes)

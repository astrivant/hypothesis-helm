"""
Keep alternative wildcard bindings separate until complete-document validation.
"""

from collections.abc import Iterator

from hypothesis import strategies as st
from hypothesis.strategies import DataObject

from hypothesis_helm.charts.model import _schema_nodes
from hypothesis_helm.schemas.contracts import mapping, sequence
from hypothesis_helm.schemas.dialects import DRAFT2020, active, dialect
from hypothesis_helm.schemas.generation.strategies import schema_strategy

__all__ = ("path_bindings",)

_Binding = tuple[str | int, ...]


def _map_keys(
    node: dict[str, object],
    root: dict[str, object],
    data: DataObject,
    generation: dict[str, object] | None,
    path: tuple[str | int, ...],
) -> Iterator[str]:
    """
    Sample each declared key region instead of selecting only the first pattern.

    Args:
        node (dict[str, object]): One possible map declaration, not a conjunction of alternative branches.
        root (dict[str, object]): Original schema retaining local definitions and dialect.
        data (DataObject): Hypothesis draw context.
        generation (dict[str, object] | None): Configured text generation policy.
        path (tuple[str | int, ...]): Parent path for field-specific text settings.

    Yields:
        str: Candidate key whose value constraints are checked by the complete document strategy.
    """
    yield from mapping(node.get("properties", {}))
    patterns = list(mapping(node.get("patternProperties", {})))
    regions: list[dict[str, object]] = [{"pattern": pattern} for pattern in patterns]
    if node.get("additionalProperties") is not False:
        # Extra keys must not accidentally land in a differently typed pattern region.
        excluded: list[dict[str, object]] = [{"pattern": pattern} for pattern in patterns]
        names = list(mapping(node.get("properties", {})))
        if names:
            excluded.append({"enum": names})
        regions.append({"not": {"anyOf": excluded}} if excluded else {})
    for region in regions:
        key_schema: dict[str, object] = {
            "$schema": dialect(node, dialect(root)),
            "type": "string",
            "allOf": [node.get("propertyNames", {}), region],
        }
        for keyword in ("$defs", "definitions"):
            if keyword in root:
                key_schema[keyword] = root[keyword]
        strategy = schema_strategy(key_schema, generation=generation, path=path)
        # An impossible key region must not reject other viable pattern regions.
        if not strategy.is_empty:
            yield str(data.draw(strategy, label="map key"))


def _segments(
    nodes: list[dict[str, object]],
    current: object,
    root: dict[str, object],
    data: DataObject,
    generation: dict[str, object] | None,
    path: tuple[str | int, ...],
) -> Iterator[str | int]:
    """
    Offer array tails and map keys without conflating their alternative shapes.

    Args:
        nodes (list[dict[str, object]]): Possible parent schemas across branches and references.
        current (object): Parent container in the baseline, when present.
        root (dict[str, object]): Complete chart schema.
        data (DataObject): Hypothesis draw context.
        generation (dict[str, object] | None): Text generation policy.
        path (tuple[str | int, ...]): Concrete parent path.

    Yields:
        str | int: Possible selector; the whole schema decides which selectors are valid.
    """
    arrays = []
    maps = []
    for raw in nodes:
        node = active(raw, dialect(root))
        types = [node["type"]] if isinstance(node.get("type"), str) else sequence(node.get("type", []))
        if "array" in types or "items" in node or "prefixItems" in node:
            arrays.append(node)
        if "object" in types or any(key in node for key in ("properties", "patternProperties", "propertyNames", "additionalProperties")):
            maps.append(node)
    if not arrays and isinstance(current, list):
        arrays.append({})
    for node in arrays:
        prefix = node.get("prefixItems", []) if dialect(node, dialect(root)) == DRAFT2020 else node.get("items", [])
        start = len(prefix) if isinstance(prefix, list) else 0
        # Preserve each branch's tail start. Taking their maximum loses shorter tuples.
        yield start
        if isinstance(current, list) and len(current) > start:
            yield data.draw(st.integers(min_value=start, max_value=len(current) - 1))
    if isinstance(current, dict) and current:
        yield data.draw(st.sampled_from(sorted(current)))
    if not maps and not arrays:
        maps.append({})
    for node in maps:
        yield from _map_keys(node, root, data, generation, path)


def path_bindings(
    path: tuple[str | int, ...],
    defaults: dict[str, object],
    schema: dict[str, object],
    data: DataObject,
    generation: dict[str, object] | None = None,
) -> Iterator[_Binding]:
    """
    Produce possible concrete paths while retaining mutually exclusive structures.

    Args:
        path (tuple[str | int, ...]): Symbolic path containing collection wildcards.
        defaults (dict[str, object]): Baseline values used to retain existing collection entries.
        schema (dict[str, object]): Complete schema, including conditional branches.
        data (DataObject): Hypothesis draw context for keys and existing array positions.
        generation (dict[str, object] | None): Field-specific generation settings.

    Yields:
        _Binding: Concrete path to constrain in a disjunction, never an unconditional structural proof.
    """

    def visit(index: int, prefix: tuple[str | int, ...], current: object) -> Iterator[_Binding]:
        """
        Resolve the next component using schemas at this concrete parent.

        Args:
            index (int): Next symbolic component.
            prefix (tuple[str | int, ...]): Resolved components.
            current (object): Baseline value at the current parent.

        Yields:
            _Binding: Complete candidate path.
        """
        if index == len(path):
            yield prefix
            return
        segment = path[index]
        choices: Iterator[str | int] = iter((segment,))
        if segment == "*":
            nodes = _schema_nodes(schema, tuple(str(part) for part in prefix), schema, include_conditionals=True)
            choices = _segments(nodes, current, schema, data, generation, prefix)
        seen: set[str | int] = set()
        for choice in choices:
            if choice in seen:
                continue
            seen.add(choice)
            if isinstance(current, list) and isinstance(choice, int):
                child = current[choice] if choice < len(current) else None
            else:
                child = current.get(str(choice)) if isinstance(current, dict) else None
            yield from visit(index + 1, (*prefix, choice), child)

    yield from visit(0, (), defaults)

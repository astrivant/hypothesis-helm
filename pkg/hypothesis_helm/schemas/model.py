"""
Compile declared values into a shared typed attrs tree with lossless cattrs boundaries.
"""

from __future__ import annotations

import copy
import hashlib
import keyword
from collections.abc import Iterator
from functools import reduce
from operator import or_
from types import GenericAlias
from typing import cast

from attrs import define, field, make_class
from cattrs import Converter
from jsonschema import validators

from hypothesis_helm.schemas.contracts import json_value, mapping, sequence, text


@define(frozen=True)
class Missing:
    """
    Represent omission independently of explicit null and schema defaults.
    """


MISSING = Missing()


@define(eq=False)
class ValueNode:
    """
    Reference one declared field, object or array item across analysis passes.

    Attributes:
        path (tuple[str, ...]): Original values keys, with wildcard array item segments.
        schema (dict[str, object]): Owned schema fragment retaining validation constraints.
        required (bool): Whether the parent requires this property.
        attribute (str): Collision-free Python attribute for the original values key.
        children (dict[str, ValueNode]): Declared object properties indexed by original keys.
        item (ValueNode | None): Homogeneous array item declaration when available.
        max_items (int | None): Declared or enumerated array length bound.
        python_type (object): Runtime annotation derived from declared JSON types.
        record_type (type | None): Dynamically generated attrs class for an object node.
    """

    path: tuple[str, ...]
    schema: dict[str, object]
    required: bool = False
    attribute: str = ""
    children: dict[str, ValueNode] = field(factory=dict)
    item: ValueNode | None = None
    max_items: int | None = None
    python_type: object = object
    record_type: type | None = None

    def walk(self) -> Iterator[ValueNode]:
        """
        Traverse the compiled hierarchy without rediscovering schema properties.

        Yields:
            ValueNode: This node followed by its descendants.
        """
        yield self
        for child in self.children.values():
            yield from child.walk()
        if self.item is not None:
            yield from self.item.walk()


@define(frozen=True)
class ValueReference:
    """
    Bind a source selector to a declared node while retaining unresolved references.

    Attributes:
        path (tuple[str, ...]): Original selector, including any concrete array index.
        target (ValueNode | None): Shared node, or unresolved schema evidence.
    """

    path: tuple[str, ...]
    target: ValueNode | None = None


@define(frozen=True)
class Relationship:
    """
    Retain local schema interaction evidence on the compiled values model.

    Attributes:
        references (tuple[ValueReference, ...]): Fields mentioned by one constraint.
        source (str): Schema location supplying the evidence.
    """

    references: tuple[ValueReference, ...]
    source: str


@define
class ValuesModel:
    """
    Own one reusable schema-derived hierarchy and its conversion hooks.

    Attributes:
        root (ValueNode): Root values object and authoritative schema snapshot.
        converter (Converter): Private hooks for the generated attrs classes.
        relationships (list[Relationship]): Independent schema interaction evidence.
    """

    root: ValueNode
    converter: Converter = field(factory=Converter)
    relationships: list[Relationship] = field(factory=list)

    @classmethod
    def from_schema(cls, schema: dict[str, object]) -> ValuesModel:
        """
        Compile types and field identities once from the supplied values schema.

        Args:
            schema (dict[str, object]): Authoritative schema, copied to isolate model lifetime.

        Returns:
            ValuesModel: Typed hierarchy with registered lossless conversion hooks.
        """
        model = cls(ValueNode((), copy.deepcopy(schema), True))
        model.compile_node(model.root)
        model.collect_relationships(model.root.schema, (), "schema:#")
        return model

    def compile_node(self, node: ValueNode) -> None:
        """
        Build nested attrs classes and bind field metadata to their shared nodes.

        Args:
            node (ValueNode): Declaration to compile in place.

        Returns:
            None: Child nodes, runtime annotations and cattrs hooks are registered.
        """
        declared = node.schema.get("type")
        kinds = sequence(declared) if isinstance(declared, list) else [declared]
        examples = sequence(node.schema["enum"]) if "enum" in node.schema else [node.schema["const"]] if "const" in node.schema else []
        if declared is None and examples:
            names = {
                type(None): "null",
                bool: "boolean",
                int: "integer",
                float: "number",
                str: "string",
                dict: "object",
                list: "array",
            }
            kinds = list(dict.fromkeys(names.get(type(value)) for value in examples))
        required = sequence(node.schema.get("required", []))
        properties = dict(mapping(node.schema.get("properties", {})))
        objects = [mapping(value) for value in examples if isinstance(value, dict)]
        for name in dict.fromkeys(name for value in objects for name in value):
            if name not in properties:
                properties[name] = {"enum": [value[name] for value in objects if name in value]}
        used = {"values_extra"}
        for index, (name, schema) in enumerate(properties.items()):
            attribute = name
            if not name.isascii() or not name.isidentifier() or keyword.iskeyword(name) or name.startswith("_"):
                attribute = f"value_{index}"
            while attribute in used or (attribute != name and attribute in properties):
                attribute += "_"
            used.add(attribute)
            child = ValueNode(
                (*node.path, name),
                mapping(schema) if isinstance(schema, dict) else {},
                name in required,
                attribute,
            )
            node.children[name] = child
            self.compile_node(child)
        arrays = [sequence(value) for value in examples if isinstance(value, list)]
        bound = node.schema.get("maxItems")
        node.max_items = bound if isinstance(bound, int) else max(map(len, arrays)) if arrays else None
        items = node.schema.get("items")
        if items is None and any(arrays):
            items = {"enum": [item for values in arrays for item in values]}
        if isinstance(items, dict):
            node.item = ValueNode((*node.path, "*"), mapping(items), True)
            self.compile_node(node.item)
        if "object" in kinds or properties:
            attributes: dict[str, object] = {
                child.attribute: field(
                    default=MISSING,
                    type=cast(type, child.python_type),
                    metadata={"value_node": child, "key": name},
                )
                for name, child in node.children.items()
            }
            attributes["values_extra"] = field(factory=dict, type=dict[str, object], repr=False)
            node.record_type = make_class(
                "Values_" + hashlib.sha256(repr(node.path).encode()).hexdigest()[:12],
                attributes,
                slots=True,
                kw_only=True,
            )

            def structure(value: object, target: type) -> object:
                """
                Structure a values mapping without scalar coercion or inserted defaults.

                Args:
                    value (object): Mapping for this object declaration.
                    target (type): Generated attrs class requested by cattrs.

                Returns:
                    object: Instance retaining absent fields and undeclared keys separately.
                """
                document = mapping(value)
                fields = {
                    child.attribute: self.structure_node(child, document[name]) for name, child in node.children.items() if name in document
                }
                fields["values_extra"] = {name: copy.deepcopy(value) for name, value in document.items() if name not in node.children}
                return target(**fields)

            def unstructure(value: object) -> dict[str, object]:
                """
                Restore original keys and omit only fields carrying the missing sentinel.

                Args:
                    value (object): Generated attrs instance.

                Returns:
                    dict[str, object]: Original JSON-compatible values mapping.
                """
                document = copy.deepcopy(mapping(getattr(value, "values_extra", {})))
                for name, child in node.children.items():
                    item = getattr(value, child.attribute)
                    if not isinstance(item, Missing):
                        document[name] = self.unstructure_node(child, item)
                return document

            self.converter.register_structure_hook(node.record_type, structure)
            self.converter.register_unstructure_hook(node.record_type, unstructure)
        primitives: dict[object, object] = {
            "string": str,
            "boolean": bool,
            "integer": int,
            "number": int | float,
            "null": type(None),
            "object": node.record_type or dict[str, object],
            "array": GenericAlias(list, node.item.python_type) if node.item is not None else list[object],
        }
        annotations = [primitives.get(kind, object) for kind in kinds]
        node.python_type = reduce(or_, annotations) if len(annotations) > 1 else annotations[0]

    def structure_node(self, node: ValueNode, value: object) -> object:
        """
        Convert nested declared containers while preserving all scalar values exactly.

        Args:
            node (ValueNode): Shared type declaration.
            value (object): Value already checked by the root schema when requested.

        Returns:
            object: Typed container or an unchanged scalar value.
        """
        if node.record_type is not None and isinstance(value, dict):
            return self.converter.structure(value, node.record_type)
        if node.item is not None and isinstance(value, list):
            return [self.structure_node(node.item, item) for item in value]
        return copy.deepcopy(value)

    def unstructure_node(self, node: ValueNode, value: object) -> object:
        """
        Restore nested containers using the same declaration identities.

        Args:
            node (ValueNode): Shared type declaration.
            value (object): Typed instance, array or scalar.

        Returns:
            object: Lossless raw values for Helm and JSON Schema.
        """
        if node.record_type is not None and isinstance(value, node.record_type):
            return self.converter.unstructure(value)
        if node.item is not None and isinstance(value, list):
            return [self.unstructure_node(node.item, item) for item in value]
        return copy.deepcopy(value)

    def structure(self, values: dict[str, object], *, validate: bool = True) -> object:
        """
        Validate then structure complete values, or explicitly retain partial overrides.

        Args:
            values (dict[str, object]): Raw values document.
            validate (bool): Enforce the complete original JSON Schema before conversion.

        Returns:
            object: Root attrs instance with nested typed values.
        """
        if validate:
            validators.validator_for(self.root.schema)(self.root.schema).validate(json_value(values))
        return self.structure_node(self.root, values)

    def unstructure(self, values: object) -> dict[str, object]:
        """
        Convert typed values back to the original mapping shape without inserting defaults.

        Args:
            values (object): Root instance produced by this model.

        Returns:
            dict[str, object]: Values suitable for Helm, preserving omission and explicit null.
        """
        return mapping(self.unstructure_node(self.root, values))

    def assign(self, values: object, node: ValueNode, value: object) -> None:
        """
        Assign a finite factor through compiled field identities on a typed candidate.

        Args:
            values (object): Root attrs candidate with its required object skeleton.
            node (ValueNode): Shared factor declaration owned by this model.
            value (object): Raw finite-domain choice for this factor.

        Returns:
            None: The typed candidate receives the structured factor value.
        """
        parent = values
        declaration = self.root
        for segment in node.path[:-1]:
            declaration = declaration.children[segment]
            parent = getattr(parent, declaration.attribute)
        setattr(parent, node.attribute, self.structure_node(node, value))

    def reference(self, path: tuple[str, ...]) -> ValueReference:
        """
        Resolve literal keys, container selectors and bounded array indices on the model.

        Args:
            path (tuple[str, ...]): Original selector path.

        Returns:
            ValueReference: Stable node identity or an explicitly unresolved reference.
        """
        node = self.root
        for segment in path:
            if segment in node.children:
                node = node.children[segment]
            elif node.item is not None and (segment == "*" or segment.isdigit()):
                maximum = node.max_items
                if isinstance(maximum, int) and (maximum == 0 or (segment != "*" and int(segment) >= maximum)):
                    return ValueReference(path)
                node = node.item
            else:
                return ValueReference(path)
        return ValueReference(path, node)

    def collect_relationships(self, schema: dict[str, object], prefix: tuple[str, ...], location: str) -> None:
        """
        Compile constraint evidence once, keeping overlapping relationships independent.

        Args:
            schema (dict[str, object]): Constraint or object schema fragment.
            prefix (tuple[str, ...]): Values path for this fragment.
            location (str): Original schema source location.

        Returns:
            None: Constraint references are bound to the existing hierarchy.
        """

        def mentioned(node: object, path: tuple[str, ...]) -> set[tuple[str, ...]]:
            """
            Extract selectors from one constraint expression.

            Args:
                node (object): Schema expression or branch collection.
                path (tuple[str, ...]): Current object prefix.

            Returns:
                set[tuple[str, ...]]: Mentioned fields and containers.
            """
            found: set[tuple[str, ...]] = set()
            if isinstance(node, list):
                for branch in node:
                    found.update(mentioned(branch, path))
            elif isinstance(node, dict):
                for name, child in node.get("properties", {}).items():
                    found.add((*path, name))
                    found.update(mentioned(child, (*path, name)))
                found.update((*path, name) for name in node.get("required", []))
                for key in ("if", "then", "else", "allOf", "anyOf", "oneOf", "not"):
                    found.update(mentioned(node.get(key), path))
            return found

        def add(paths: set[tuple[str, ...]], source: str) -> None:
            """
            Bind a local relationship to model nodes with its source evidence.

            Args:
                paths (set[tuple[str, ...]]): Mentioned selectors.
                source (str): Schema source location.

            Returns:
                None: The relationship is retained for subsequent analysis.
            """
            self.relationships.append(Relationship(tuple(self.reference(path) for path in sorted(paths)), source))

        if "if" in schema:
            add(
                mentioned([schema.get(key) for key in ("if", "then", "else")], prefix),
                location + "/if",
            )
        for key in ("dependencies", "dependentRequired", "dependentSchemas"):
            for name, dependency in mapping(schema.get(key, {})).items():
                refs = {(*prefix, name)}
                if isinstance(dependency, list):
                    refs.update((*prefix, text(item)) for item in dependency)
                else:
                    refs.update(mentioned(dependency, prefix))
                add(refs, f"{location}/{key}/{name}")
        for key in ("anyOf", "oneOf", "not"):
            if key in schema:
                add(mentioned(schema[key], prefix), f"{location}/{key}")
        for key in ("allOf", "anyOf", "oneOf"):
            for index, branch in enumerate(sequence(schema.get(key, []))):
                if isinstance(branch, dict):
                    if key == "allOf":
                        add(mentioned(branch, prefix), f"{location}/{key}/{index}")
                    self.collect_relationships(branch, prefix, f"{location}/{key}/{index}")
        for name, child in mapping(schema.get("properties", {})).items():
            if isinstance(child, dict):
                self.collect_relationships(child, (*prefix, name), f"{location}/properties/{name}")

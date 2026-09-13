"""
Build a known-input generation view without changing the chart's accepted contract.
"""

from __future__ import annotations

import copy

from attrs import define
from hypothesis.strategies import SearchStrategy
from jsonschema import validators

from hypothesis_helm.charts.generate import coalesce
from hypothesis_helm.charts.model import Chart, merge_values
from hypothesis_helm.charts.templates import discover
from hypothesis_helm.schemas.contracts import json_value, mapping, schema_strategy
from hypothesis_helm.schemas.model import ValueNode, ValuesModel


@define
class PriorityInputs:
    """
    Keep generation preferences separate from authoritative validation.

    Attributes:
        schema (dict[str, object]): Generation-only schema for known configuration paths.
        deferred_objects (list[list[str]]): Objects whose arbitrary extra keys run later.
        dynamic_objects (list[list[str]]): Maps retaining arbitrary keys in the first phase.
        diagnostics (list[dict[str, object]]): Unresolved template contexts and inference details.
    """

    schema: dict[str, object]
    deferred_objects: list[list[str]]
    dynamic_objects: list[list[str]]
    diagnostics: list[dict[str, object]]

    @classmethod
    def build(cls, chart: Chart) -> PriorityInputs:
        """
        Prioritize declared, defaulted, and referenced paths using the shared values model.

        Empty maps, schema-defined maps, and wildcard template accesses remain open.
        Unsupported compositions retain their original generation constraints.
        Opaque contexts remain diagnostics, never evidence of unused values.

        Args:
            chart (Chart): Original schema, defaults, and template sources.

        Returns:
            PriorityInputs: Generation preferences with explicit conservative exceptions.
        """
        coalesced = coalesce(chart)
        model = ValuesModel.from_schema(coalesced.schema)
        references, _ = discover(chart.path)
        dynamic = {reference.path[: reference.path.index("*")] for reference in references if "*" in reference.path}
        # Whole-map references may feed toYaml, include, tpl, or other opaque helpers.
        containers = {node.path for node in model.root.walk() if node.children}
        dynamic.update(reference.path for reference in references if reference.path and reference.path in containers)
        deferred: list[list[str]] = []
        retained: list[list[str]] = []

        def visit(node: ValueNode) -> dict[str, object]:
            """
            Build a generation view while retaining dynamic maps and complex constraints.

            Args:
                node (ValueNode): Shared typed value declaration.

            Returns:
                dict[str, object]: Copy used only to generate first-phase candidates.
            """
            schema = copy.deepcopy(node.schema)
            if any(key in schema for key in ("$ref", "allOf", "anyOf", "oneOf", "if", "dependentSchemas")):
                return schema
            if node.children:
                schema["properties"] = {name: visit(child) for name, child in node.children.items()}
            if node.item is not None:
                schema["items"] = visit(node.item)
            if schema.get("type") == "object" and schema.get("additionalProperties") is not False:
                if (
                    not node.children
                    or schema.get("patternProperties")
                    or isinstance(schema.get("additionalProperties"), dict)
                    or node.path in dynamic
                ):
                    retained.append(list(node.path))
                else:
                    schema["additionalProperties"] = False
                    deferred.append(list(node.path))
            return schema

        return cls(visit(model.root), deferred, retained, coalesced.diagnostics)

    def strategy(self, chart: Chart) -> SearchStrategy[dict[str, object]]:
        """
        Generate known-input overrides that satisfy the original merged contract.

        Args:
            chart (Chart): Authoritative schema and untouched defaults.

        Returns:
            SearchStrategy[dict[str, object]]: Restricted generation with original validation.
        """
        validator = validators.validator_for(chart.schema)(chart.schema)
        return (
            schema_strategy(self.schema)
            .map(mapping)
            .filter(lambda values: validator.is_valid(json_value(merge_values(chart.defaults, values))))
        )

    def deferred_strategy(self, chart: Chart) -> SearchStrategy[dict[str, object]]:
        """
        Generate the original-contract cases excluded by the known-input preference.

        Args:
            chart (Chart): Authoritative chart contract and defaults.

        Returns:
            SearchStrategy[dict[str, object]]: Deferred cases, without redefining validity.
        """
        original = validators.validator_for(chart.schema)(chart.schema)
        focused = validators.validator_for(self.schema)(self.schema)
        return chart.strategy().filter(
            lambda values: (
                original.is_valid(json_value(merge_values(chart.defaults, values)))
                and not focused.is_valid(json_value(merge_values(chart.defaults, values)))
            )
        )

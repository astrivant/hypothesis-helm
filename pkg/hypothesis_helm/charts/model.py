"""
Load chart contracts and model values merging without execution dependencies.
"""

from __future__ import annotations

import copy
import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

from attrs import define
from hypothesis.strategies import SearchStrategy
from jsonschema import validators

from hypothesis_helm.charts import yamlio

if TYPE_CHECKING:
    from hypothesis_helm.compiler.passes.dependencies import Dependencies
from hypothesis_helm.schemas.contracts import (
    mapping,
    schema_strategy,
)

LOGGER = logging.getLogger(__name__)


@define
class Chart:
    """
    Hold the chart location, documented schema, and round-trip defaults.

    Attributes:
        path (Path): Resolved value path or chart location.
        schema (dict[str, object]): Schema describing accepted values.
        defaults (dict[str, object]): Values loaded from the source chart.
        dependency_model (Dependencies | None): Optional dependency snapshot for an isolated generated suite.
    """

    path: Path
    schema: dict[str, object]
    defaults: dict[str, object]
    dependency_model: Dependencies | None = None

    @classmethod
    def load(cls, path: str | Path) -> Chart:
        """
        Check load.

        Args:
            path (str | Path): Value path or chart location to inspect.

        Returns:
            Chart: Result of the documented operation.
        """
        path = Path(path).resolve()
        metadata = yamlio.load((path / "Chart.yaml").read_text())
        if not isinstance(metadata, dict) or not metadata.get("name"):
            raise ValueError("Chart.yaml must contain a chart name")
        schema = json.loads((path / "values.schema.json").read_text())
        if not isinstance(schema, dict) or schema.get("type") != "object":
            raise ValueError("values.schema.json must declare type: object")

        # Do not allow implicit network resolution or files outside the chart.
        def refs(node: object) -> None:
            """
            Reject external schema references before strategy construction.

            Args:
                node (object): Current schema or template node.

            Returns:
                None: None. The operation completes through its documented side effects.
            """
            if isinstance(node, dict):
                if "$ref" in node and not node["$ref"].startswith("#"):
                    raise ValueError("only local JSON Pointer schema references are supported")
                for value in node.values():
                    refs(value)
            elif isinstance(node, list):
                for value in node:
                    refs(value)

        refs(schema)
        validators.validator_for(schema).check_schema(schema)
        defaults = yamlio.load((path / "values.yaml").read_text()) or {}
        if not isinstance(defaults, dict):
            raise ValueError("values.yaml must contain an object")
        return cls(path, schema, defaults)

    def strategy(self) -> SearchStrategy[dict[str, object]]:
        """
        Generate schema-valid overrides; Helm still merges chart defaults.

        Returns:
            SearchStrategy[dict[str, object]]: Result of the documented operation.
        """
        return schema_strategy(self.schema).map(mapping)


def merge_values(defaults: dict[str, object], overrides: dict[str, object]) -> dict[str, object]:
    """
    Model ordinary Helm map merging and null deletion for schema preflight.

    Helm is authoritative, especially for dependency coalescing and globals.

    Args:
        defaults (dict[str, object]): Existing chart defaults that take precedence during
            coalescing.
        overrides (dict[str, object]): Incoming Helm overrides, including null deletion markers.

    Returns:
        dict[str, object]: Resulting schema, values mapping, or structured report.
    """
    result = copy.deepcopy(defaults)
    for key, value in overrides.items():
        if value is None:
            result.pop(key, None)
        elif isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_values(mapping(result[key]), value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _schema_nodes(
    schema: object,
    path: tuple[str, ...],
    root: dict[str, object],
    seen: frozenset[tuple[int, tuple[str, ...]]] = frozenset(),
) -> list[dict[str, object]]:
    """
    Check  schema nodes.

    Args:
        schema (object): JSON Schema defining the accepted value domain.
        path (tuple[str, ...]): Value path or chart location to inspect.
        root (dict[str, object]): Root schema used to resolve local references.
        seen (frozenset[tuple[int, tuple[str, ...]]]): References already visited while resolving
            this schema.

    Returns:
        list[dict[str, object]]: Result of the documented operation.
    """
    if not isinstance(schema, dict):
        return []
    marker = (id(schema), path)
    if marker in seen:
        return []
    seen = seen | {marker}
    found = []
    if "$ref" in schema:
        target = root
        for part in schema["$ref"].removeprefix("#/").split("/"):
            if schema["$ref"] == "#":
                break
            target = mapping(target[part.replace("~1", "/").replace("~0", "~")])
        found += _schema_nodes(target, path, root, seen)
    for keyword in ("allOf", "anyOf", "oneOf"):
        for branch in schema.get(keyword, []):
            found += _schema_nodes(branch, path, root, seen)
    if not path:
        return found + [schema]
    key, *rest = path
    if key in schema.get("properties", {}):
        found += _schema_nodes(schema["properties"][key], tuple(rest), root, seen)
    if key == "*" and isinstance(schema.get("items"), dict):
        found += _schema_nodes(schema["items"], tuple(rest), root, seen)
    # Explicitly typed map entries count as documentation; open maps do not.
    if isinstance(schema.get("additionalProperties"), dict):
        found += _schema_nodes(schema["additionalProperties"], tuple(rest), root, seen)
    import re

    for pattern, branch in schema.get("patternProperties", {}).items():
        if key == "*" or re.search(pattern, key):
            found += _schema_nodes(branch, tuple(rest), root, seen)
    return found


def _default_paths(value: object, prefix: tuple[str, ...] = ()) -> Iterator[tuple[str, ...]]:
    """
    Check  default paths.

    Args:
        value (object): Candidate value supplied by the property strategy.
        prefix (tuple[str, ...]): Resolved parent path for the current value.

    Yields:
        tuple[str, ...]: Next value path in the document.
    """
    if isinstance(value, dict):
        for key, child in value.items():
            path = prefix + (str(key),)
            yield path
            yield from _default_paths(child, path)
    elif isinstance(value, list):
        for child in value:
            yield from _default_paths(child, prefix + ("*",))

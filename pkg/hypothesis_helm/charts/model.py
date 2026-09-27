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

from attrs import define, field
from hypothesis.strategies import SearchStrategy
from jsonschema import validators

from hypothesis_helm.charts.values import yamlio
from hypothesis_helm.compiler.randomness.certificates import CertificateStore
from hypothesis_helm.exceptions.execution import ChartUnavailable

__all__ = ("Chart", "merge_values")


if TYPE_CHECKING:
    from hypothesis_helm.compiler.passes.dependencies import Dependencies
    from hypothesis_helm.schemas.generation.domains import InputDomains
from hypothesis_helm.schemas.contracts import mapping, sequence
from hypothesis_helm.schemas.dialects import DRAFT4, DRAFT6, DRAFT7, DRAFT2020, active, canonical, dialect, pointer_target, walk
from hypothesis_helm.schemas.generation.strategies import schema_strategy

LOGGER = logging.getLogger(__name__)


@define
class Chart:
    """
    Hold the chart location, documented schema, and round-trip defaults.

    Attributes:
        path (Path): Resolved value path or chart location.
        schema (dict[str, object]): Schema describing accepted values.
        defaults (dict[str, object]): Values loaded from the source chart.
        dependency_model (Dependencies | None): Shared dependency snapshot for discovery, generation and child-default coalescing.
        domains (InputDomains | None): Lazily resolved generation policy, independent of the source schema.
        generated_schema (dict[str, object] | None): Cached default generation contract for this chart instance.
        renderer_effects (bool | None): Cached potential runtime effects in this prepared source snapshot.
        renderer_statistics (dict[str, object]): Observed execution modes and native fallback reasons for this chart job.
        certificate_records (CertificateStore): Native crypto observations retained across retries within this prepared chart.
    """

    path: Path
    schema: dict[str, object]
    defaults: dict[str, object]
    dependency_model: Dependencies | None = None
    domains: InputDomains | None = field(default=None, init=False)
    generated_schema: dict[str, object] | None = field(default=None, init=False)
    renderer_effects: bool | None = field(default=None, init=False)
    renderer_statistics: dict[str, object] = field(factory=dict, init=False)
    certificate_records: CertificateStore = field(factory=CertificateStore, init=False, repr=False, eq=False)

    def require_source(self) -> None:
        """
        Confirm that the prepared chart remains readable before testing another input.

        Raises:
            ChartUnavailable: Chart metadata disappeared or became unreadable during execution.

        Returns:
            None: The source still exists; this does not establish validity of the chart.
        """
        metadata = self.path / "Chart.yaml"
        try:
            with metadata.open("rb") as stream:
                stream.read(1)
        except OSError as exc:
            raise ChartUnavailable(f"Chart source unavailable: {metadata} ({exc.strerror}); testing stopped; not a chart finding") from exc

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
        schema = canonical(schema)

        # Do not allow implicit network resolution or files outside the chart.
        for node in walk(schema):
            for keyword in ("$ref", "$dynamicRef", "$recursiveRef"):
                reference = node.get(keyword)
                if keyword in node and (not isinstance(reference, str) or not reference.startswith("#")):
                    raise ValueError("only local JSON Pointer schema references are supported")
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
        return schema_strategy(self.generation_schema(), generation=self.input_domains().generation).map(mapping)

    def input_domains(self) -> InputDomains:
        """
        Resolve source and destination constraints once for this chart instance.

        Returns:
            InputDomains: Policy shared across planning, generation and reports.
        """
        from hypothesis_helm.schemas.generation.domains import InputDomains

        if self.domains is None:
            self.domains = InputDomains.build(self)
        return self.domains

    def generation_schema(self, schema: dict[str, object] | None = None) -> dict[str, object]:
        """
        Apply the chart's domain policy to an original or inferred schema.

        Args:
            schema (dict[str, object] | None): Generation view, or the original chart schema.

        Returns:
            dict[str, object]: Restricted copy without modifying schema or defaults.
        """
        if schema is not None:
            return self.input_domains().apply(schema)
        if self.generated_schema is None:
            self.generated_schema = self.input_domains().apply(self.schema)
        return self.generated_schema


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
    inherited: str | None = None,
    *,
    include_conditionals: bool = False,
) -> list[dict[str, object]]:
    """
    Collect declarations for a path while retaining conditional shapes only on request.

    Args:
        schema (object): JSON Schema defining the accepted value domain.
        path (tuple[str, ...]): Value path or chart location to inspect.
        root (dict[str, object]): Root schema used to resolve local references.
        seen (frozenset[tuple[int, tuple[str, ...]]]): References already visited while resolving
            this schema.
        inherited (str | None): Dialect inherited through the selected schema path.
        include_conditionals (bool): Include then/else shapes as generation hints, never unconditional constraints.

    Returns:
        list[dict[str, object]]: Applicable declarations or alternative shape hints; alternatives are not a conjunction.
    """
    if not isinstance(schema, dict):
        return []
    marker = (id(schema), path)
    if marker in seen:
        return []
    seen = seen | {marker}
    version = dialect(schema, inherited or dialect(root))
    node = active(schema, version)
    found = []
    if "$ref" in node:
        target, target_version = pointer_target(root, node["$ref"])
        found += _schema_nodes(target, path, root, seen, target_version, include_conditionals=include_conditionals)
        if version in (DRAFT4, DRAFT6, DRAFT7):
            return found
    for keyword in ("allOf", "anyOf", "oneOf"):
        for branch in sequence(node.get(keyword, [])):
            found += _schema_nodes(branch, path, root, seen, version, include_conditionals=include_conditionals)
    if include_conditionals and "if" in node:
        # Discovery visits both arms. Their shapes can guide a candidate, but only
        # full-document validation decides whether that branch actually applies.
        for keyword in ("then", "else"):
            if keyword in node:
                found += _schema_nodes(node[keyword], path, root, seen, version, include_conditionals=True)
    if not path:
        return found + [schema]
    key, *rest = path
    if key in mapping(node.get("properties", {})):
        found += _schema_nodes(
            mapping(node["properties"])[key], tuple(rest), root, seen, version, include_conditionals=include_conditionals
        )
    prefix = node.get("prefixItems", []) if version == DRAFT2020 else node.get("items", [])
    prefix = prefix if isinstance(prefix, list) else []
    tail = node.get("items") if version == DRAFT2020 or not prefix else node.get("additionalItems")
    if key == "*" or key.isdecimal():
        child = prefix[int(key)] if key != "*" and int(key) < len(prefix) else tail
        if isinstance(child, dict):
            found += _schema_nodes(child, tuple(rest), root, seen, version, include_conditionals=include_conditionals)
    import re

    matched = key in mapping(node.get("properties", {}))
    for pattern, branch in mapping(node.get("patternProperties", {})).items():
        if key == "*" or re.search(pattern, key):
            matched = True
            found += _schema_nodes(branch, tuple(rest), root, seen, version, include_conditionals=include_conditionals)
    # Additional properties exclude names matched in this same schema object.
    # A wildcard still represents the unmatched region as well as pattern regions.
    if (key == "*" or not matched) and isinstance(node.get("additionalProperties"), dict):
        found += _schema_nodes(node["additionalProperties"], tuple(rest), root, seen, version, include_conditionals=include_conditionals)
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

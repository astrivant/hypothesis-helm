"""
Select safe manifest readers without changing round-trip values-file editing.
"""

from __future__ import annotations

from contextvars import ContextVar
from importlib.metadata import version
from typing import cast

import yaml as pyyaml
from ruamel.yaml import YAML
from ruamel.yaml.constructor import SafeConstructor
from ruamel.yaml.error import YAMLError
from ruamel.yaml.nodes import MappingNode as RuamelMappingNode
from yaml.nodes import MappingNode

from hypothesis_helm.charts.values.manifest_scalars import HelmFloatResolver
from hypothesis_helm.exceptions.rendering import ManifestParseError

__all__ = ("BACKENDS", "SUITE_YAML_PARSER", "identity", "load_all", "selected", "validate_backend")

BACKENDS = ("ruamel", "ruamel-safe", "pyyaml")
SUITE_YAML_PARSER: ContextVar[str] = ContextVar("suite_yaml_parser", default="ruamel")
_MERGE_KEY = object()


def check_key(key: object, line: int, seen: set[object]) -> None:
    """
    Check explicitly written keys before a safe loader expands YAML merge defaults.

    Args:
        key (object): Constructed key, or a sentinel for a YAML merge directive.
        line (int): Zero-based source line for diagnostics.
        seen (set[object]): Keys already declared in this mapping.

    Returns:
        None: The key is recorded for subsequent duplicate checks.

    Raises:
        ManifestParseError: A key is duplicated or cannot be used in a mapping.
    """
    try:
        if key in seen:
            label = "<<" if key is _MERGE_KEY else repr(key)
            raise ManifestParseError(f"duplicate key {label} at line {line + 1}")
        seen.add(key)
    except TypeError as exc:
        raise ManifestParseError(f"unhashable key at line {line + 1}") from exc


class UniqueSafeLoader(pyyaml.SafeLoader):
    """
    Reject explicit duplicate keys while preserving legal YAML merge overrides.

    Attributes:
        yaml_constructors: Safe constructors with legacy equals scalars treated as strings.
    """

    yaml_constructors = {
        **pyyaml.SafeLoader.yaml_constructors,
        "tag:yaml.org,2002:value": pyyaml.SafeLoader.construct_yaml_str,
    }

    def construct_mapping(self, node: MappingNode, deep: bool = False) -> dict[object, object]:
        """
        Check keys before flattening merges, which may intentionally supply defaults.

        Args:
            node (MappingNode): Parsed mapping with unexpanded merge entries.
            deep (bool): Construct nested values eagerly when requested by the loader.

        Returns:
            dict[object, object]: Mapping with the ordinary SafeLoader scalar semantics.

        """
        seen: set[object] = set()
        for key_node, _ in node.value:
            # Distinguish the merge directive from an ordinary quoted '<<' key.
            key = _MERGE_KEY if key_node.tag == "tag:yaml.org,2002:merge" else self.construct_object(key_node, deep=True)
            check_key(key, key_node.start_mark.line, seen)
        return super().construct_mapping(node, deep=deep)


class ScalarSafeConstructor(SafeConstructor):
    """
    Reject duplicate keys and preserve bare equals signs without changing other readers.

    Attributes:
        yaml_constructors: Safe constructors with legacy equals scalars treated as strings.
    """

    yaml_constructors = {
        **SafeConstructor.yaml_constructors,
        "tag:yaml.org,2002:value": SafeConstructor.construct_yaml_str,
    }

    def construct_mapping(self, node: RuamelMappingNode, deep: bool = False) -> dict[object, object]:
        """
        Check explicit keys before ruamel flattens and bypasses checks for merged mappings.

        Args:
            node (RuamelMappingNode): Parsed mapping with unexpanded merge entries.
            deep (bool): Construct nested values eagerly when requested by the loader.

        Returns:
            dict[object, object]: Mapping with the ordinary safe constructor's scalar semantics.
        """
        seen: set[object] = set()
        for key_node, _ in node.value:
            key = _MERGE_KEY if key_node.tag == "tag:yaml.org,2002:merge" else self.construct_object(key_node, deep=True)
            check_key(key, key_node.start_mark.line, seen)
        return cast(dict[object, object], super().construct_mapping(node, deep=deep))


def validate_backend(value: object) -> str:
    """
    Validate a configured backend without importing user-named modules or executing plugins.

    Args:
        value (object): Backend name from configuration, a suite snapshot or the CLI.

    Returns:
        str: Supported backend name.

    Raises:
        ValueError: The supplied parser name is unsupported.
    """
    if not isinstance(value, str) or value not in BACKENDS:
        raise ValueError(f"yaml_parser must be one of: {', '.join(BACKENDS)}")
    return value


def selected() -> str:
    """
    Prefer explicit run configuration, then a saved suite's parser, then ruamel.

    Returns:
        str: Validated backend inherited by this execution context.
    """
    from hypothesis_helm.schemas.configuration.policy import inherited_policy

    return validate_backend(inherited_policy().get("yaml_parser", SUITE_YAML_PARSER.get()))


def identity() -> dict[str, str]:
    """
    Identify parser selection and installed implementation for reports and cache separation.

    Returns:
        dict[str, str]: Backend, package version and selected loader implementation.
    """
    backend = selected()
    implementation = (
        "SafeLoader+duplicate-check" if backend == "pyyaml" else str(YAML(typ="safe" if backend == "ruamel-safe" else "rt").Parser.__name__)
    )
    if backend != "pyyaml":
        implementation += "+helm-float-v1"
    return {"backend": backend, "version": version("PyYAML" if backend == "pyyaml" else "ruamel.yaml"), "implementation": implementation}


def load_all(text: str, *, backend: str | None = None) -> list[object]:
    """
    Parse a complete manifest stream using one explicit backend without silent fallback.

    Args:
        text (str): Rendered YAML stream.
        backend (str | None): Explicit backend, or the active run/suite selection.

    Returns:
        list[object]: Parsed documents, including empty documents and native scalar types.

    Raises:
        ManifestParseError: The selected parser rejected the stream.
        ValueError: The requested backend is unsupported.
    """
    choice = selected() if backend is None else validate_backend(backend)
    try:
        if choice == "pyyaml":
            return list(pyyaml.load_all(text, Loader=UniqueSafeLoader))
        if choice == "ruamel-safe":
            reader = YAML(typ="safe")
            reader.allow_duplicate_keys = False
            reader.Constructor = ScalarSafeConstructor
            reader.Resolver = HelmFloatResolver
        else:
            from hypothesis_helm.charts.values.yamlio import yaml

            reader = yaml(manifest=True)
        return list(reader.load_all(text))
    except (YAMLError, pyyaml.YAMLError, ManifestParseError) as exc:
        raise ManifestParseError(f"{choice}: {exc}") from exc

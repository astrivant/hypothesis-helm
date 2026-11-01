"""
Round-trip YAML I/O shared by chart loading, coalescing and generation.
"""

from __future__ import annotations

import json
import re
from io import StringIO

from ruamel.yaml import YAML
from ruamel.yaml.constructor import RoundTripConstructor
from ruamel.yaml.nodes import ScalarNode
from ruamel.yaml.representer import BaseRepresenter

from hypothesis_helm.charts.values.manifest_scalars import HelmFloatResolver

__all__ = ("dump", "json_for_helm", "load", "load_all", "yaml")


def yaml(*, manifest: bool = False) -> YAML:
    """
    Create a round-trip reader with Helm-compatible handling of bare equals signs.

    Args:
        manifest (bool): Resolve implicit overflowing manifest floats as strings, preserving values-file behavior.

    Returns:
        YAML: Independent reader/writer preserving quotes and rejecting duplicate keys.
    """
    # Reader state and custom representers must not leak between charts or concurrent render jobs.
    instance = YAML(typ="rt")
    instance.preserve_quotes = True
    instance.allow_duplicate_keys = False
    if manifest:
        instance.Resolver = HelmFloatResolver
    # ruamel tags a bare '=' with YAML's legacy value tag. Helm reads it as
    # a string. Copy the constructor table so other YAML instances are untouched.
    instance.constructor.yaml_constructors = {
        **instance.constructor.yaml_constructors,
        "tag:yaml.org,2002:value": RoundTripConstructor.construct_yaml_str,
    }
    return instance


def load(text: str) -> object:
    """
    Parse one values document while retaining YAML anchors and round-trip scalar information.

    Args:
        text (str): YAML or template text to process.

    Returns:
        object: Parsed YAML tree, or None for an empty document.
    """
    return yaml().load(text)


def dump(value: object, *, explicit_null: bool = False) -> str:
    """
    Serialize values without losing round-trip YAML information.

    Args:
        value (object): Candidate value supplied by the property strategy.
        explicit_null (bool): Write legitimate null values explicitly instead of bare keys.

    Returns:
        str: YAML document suitable for a values file or saved reproduction.
    """

    def null_scalar(representer: BaseRepresenter, unused: None) -> ScalarNode:
        """
        Represent null explicitly without changing another YAML writer's behavior.

        Args:
            representer (BaseRepresenter): Current writer.
            unused (None): Null value being serialized.

        Returns:
            ScalarNode: Explicit YAML null scalar.
        """
        return representer.represent_scalar("tag:yaml.org,2002:null", "null")

    stream = StringIO()
    writer = yaml()
    if explicit_null:
        writer.representer.yaml_representers = {
            **writer.representer.yaml_representers,
            type(None): null_scalar,
        }
    writer.dump(value, stream)
    return stream.getvalue()


def load_all(text: str) -> list[object]:
    """
    Parse a manifest stream with the configured backend while keeping values I/O round-trip.

    Args:
        text (str): YAML or template text to process.

    Returns:
        list[object]: Parsed documents in their original order, including empty documents.
    """
    from hypothesis_helm.charts.values.parsers import load_all as parse_manifests

    return parse_manifests(text)


def json_for_helm(value: object, *, indent: int | None = None) -> str:
    """
    Preserve JSON strings when Helm reads the document through its YAML parser.

    Escape controls and line separators to avoid YAML rejection and normalization.
    Keep ordinary Unicode literal so escaping does not inflate map keys beyond
    YAML's simple-key limit. Supplementary characters stay UTF-8 because Helm's
    YAML parser rejects JSON surrogate-pair escapes.

    Args:
        value (object): JSON-compatible chart overrides.
        indent (int | None): Optional indentation for saved reproducing values.

    Returns:
        str: JSON text accepted without changing Unicode scalar values.
    """
    return re.sub(
        r"[\x7f-\x9f\u2028\u2029\ud800-\udfff\ufffe\uffff]",
        lambda match: f"\\u{ord(match[0]):04x}",
        json.dumps(value, ensure_ascii=False, indent=indent),
    )

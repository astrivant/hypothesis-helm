"""
Round-trip YAML I/O shared by chart loading, coalescing and generation.
"""

import json
import re
from io import StringIO

from ruamel.yaml import YAML
from ruamel.yaml.constructor import RoundTripConstructor
from ruamel.yaml.nodes import ScalarNode
from ruamel.yaml.representer import BaseRepresenter


def yaml() -> YAML:
    """
    Create a round-trip reader with Helm-compatible handling of bare equals signs.

    Returns:
        YAML: Result of the documented operation.
    """
    instance = YAML(typ="rt")
    instance.preserve_quotes = True
    instance.allow_duplicate_keys = False
    # ruamel tags a bare '=' with YAML's legacy value tag. Helm reads it as
    # a string. Copy the constructor table so other YAML instances are untouched.
    instance.constructor.yaml_constructors = {
        **instance.constructor.yaml_constructors,
        "tag:yaml.org,2002:value": RoundTripConstructor.construct_yaml_str,
    }
    return instance


def load(text: str) -> object:
    """
    Check load.

    Args:
        text (str): YAML or template text to process.

    Returns:
        object: Parsed or generated value at the requested boundary.
    """
    return yaml().load(text)


def dump(value: object, *, explicit_null: bool = False) -> str:
    """
    Check dump.

    Args:
        value (object): Candidate value supplied by the property strategy.
        explicit_null (bool): Write legitimate null values explicitly instead of bare keys.

    Returns:
        str: Serialized output or resolved strategy expression.
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
    Check load all.

    Args:
        text (str): YAML or template text to process.

    Returns:
        list[object]: Result of the documented operation.
    """
    return list(yaml().load_all(text))


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

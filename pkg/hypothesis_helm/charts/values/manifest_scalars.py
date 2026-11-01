"""
Keep implicit overflowing manifest floats consistent with Helm's finite float resolution.
"""

from __future__ import annotations

import math
from typing import cast

from ruamel.yaml.nodes import Node, ScalarNode
from ruamel.yaml.resolver import VersionedResolver
from ruamel.yaml.tag import Tag

__all__ = ("HelmFloatResolver",)


class HelmFloatResolver(VersionedResolver):
    """
    Preserve implicit overflow as text while retaining explicit YAML scalar contracts.
    """

    def resolve(self, kind: type[Node], value: object, implicit: object) -> Tag:
        """
        Refine ruamel's implicit float tag without changing finite values or other tags.

        Args:
            kind (type[Node]): Node type supplied by the YAML composer.
            value (object): Scalar text or the composer's non-scalar placeholder.
            implicit (object): Composer flags controlling implicit tag resolution.

        Returns:
            Tag: Original resolved tag, or the string tag for implicit numeric overflow.
        """
        tag = cast(Tag, super().resolve(kind, value, implicit))
        if kind is not ScalarNode or tag.value != "tag:yaml.org,2002:float" or not isinstance(value, str):
            return tag

        # Explicit tags bypass this resolver. Keep YAML's named nonfinite literals unchanged;
        # ordinary numeric overflow must stay text, as in go-yaml's successful-ParseFloat rule.
        normalized = value.replace("_", "")
        if normalized.lower().lstrip("+-") in {".inf", ".nan"}:
            return tag
        try:
            numeric = float(normalized)
        except ValueError:
            # Preserve formats owned by the underlying YAML version, including legacy base-60 scalars.
            return tag
        return tag if math.isfinite(numeric) else Tag(suffix="tag:yaml.org,2002:str")

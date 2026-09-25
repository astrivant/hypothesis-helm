"""
Merge Action configuration without editing the checkout or relocating schema references.
"""

import copy
from pathlib import Path

from ruamel.yaml.error import YAMLError

from hypothesis_helm.charts.values import yamlio
from hypothesis_helm.schemas.configuration.policy import configuration, load_policy
from hypothesis_helm.schemas.configuration.selectors import selectors
from hypothesis_helm.schemas.contracts import mapping, sequence

__all__ = ("merge_config", "prepare_config")


def merge_config(base: dict[str, object], override: dict[str, object]) -> dict[str, object]:
    """
    Merge mappings recursively; replace scalars and entire lists, including empty lists.

    Args:
        base (dict[str, object]): Configuration from the selected file.
        override (dict[str, object]): Inline values with higher precedence.

    Returns:
        dict[str, object]: Independent merged document.
    """
    result = copy.deepcopy(base)
    for key, value in override.items():
        previous = result.get(key)
        result[key] = merge_config(mapping(previous), mapping(value)) if isinstance(previous, dict) and isinstance(value, dict) else value
    return result


def resolve_paths(document: dict[str, object], root: Path) -> dict[str, object]:
    """
    Preserve each layer's resource files and local chart selectors before moving it.

    Args:
        document (dict[str, object]): One unmerged configuration layer.
        root (Path): Original configuration directory, or workspace for inline YAML.

    Returns:
        dict[str, object]: Copy with absolute local references.
    """
    result = copy.deepcopy(document)
    if result.get("resource_schemas"):
        result["resource_schemas"] = {
            identity: str((root / filename).resolve()) if isinstance(filename, str) else filename
            for identity, filename in mapping(result["resource_schemas"]).items()
        }
    for raw in sequence(result.get("input_constraints") or []):
        rule = mapping(raw)
        rule["charts"] = selectors(rule.get("charts"), root)
    return result


def prepare_config(filename: str, inline: str, destination: Path) -> Path | None:
    """
    Write and validate a private effective policy only when inline overrides are supplied.

    Args:
        filename (str): Explicit file, or empty to discover .hypothesis-helm.yaml.
        inline (str): Optional single YAML mapping.
        destination (Path): Private runner temporary file, outside uploaded artifacts.

    Returns:
        Path | None: Effective policy, original explicit file, or normal CLI discovery.
    """
    source = Path(filename).resolve() if filename else None
    if not inline.strip():
        if source is not None:
            load_policy(source)
        return source
    try:
        override = yamlio.load(inline)
    except YAMLError as error:
        # Parser exceptions include source lines, which may contain secret input.
        raise ValueError("config-inline must be valid single-document YAML without duplicate keys") from error
    if not isinstance(override, dict):
        raise ValueError("config-inline must contain one YAML mapping")
    base = resolve_paths(configuration(source), (source or Path(".hypothesis-helm.yaml")).resolve().parent)
    merged = merge_config(base, resolve_paths(mapping(override), Path.cwd()))
    destination.parent.mkdir(parents=True, exist_ok=True)
    # The file can contain credentials supplied through GitHub secrets. Never print it
    # or include it in uploaded artifacts; the runner owns its temporary directory.
    with destination.open("x", encoding="utf-8") as stream:
        destination.chmod(0o600)
        stream.write(yamlio.dump(merged))
    load_policy(destination)
    return destination

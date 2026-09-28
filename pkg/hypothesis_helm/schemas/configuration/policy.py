"""
Load explicit generation domains without changing a chart's accepted contract.
"""

from __future__ import annotations

import copy
import json
import re
from functools import lru_cache
from pathlib import Path

from hypothesis_helm_catalog.profiles import schema as profile_schema
from jsonschema import validators

from hypothesis_helm.charts.values import yamlio
from hypothesis_helm.charts.values.parsers import validate_backend
from hypothesis_helm.compiler.limits import compiler_limits
from hypothesis_helm.environment import env
from hypothesis_helm.findings.catalog import CATALOG
from hypothesis_helm.findings.severity import validate as validate_findings
from hypothesis_helm.schemas.configuration.characters import validate_character_sets
from hypothesis_helm.schemas.configuration.selectors import selectors
from hypothesis_helm.schemas.configuration.settings import SETTING_KEYS, validate_settings
from hypothesis_helm.schemas.contracts import json_value, mapping, number, sequence
from hypothesis_helm.schemas.dialects import canonical, walk

__all__ = (
    "ENVIRONMENT",
    "FILE_ENVIRONMENT",
    "PROFILES",
    "check_schema",
    "configuration",
    "inherited_policy",
    "intersect",
    "load_policy",
    "path_parts",
    "restrict",
)


ENVIRONMENT = "HYPOTHESIS_HELM_INPUT_POLICY"
FILE_ENVIRONMENT = "HYPOTHESIS_HELM_INPUT_POLICY_FILE"
PROFILES: dict[str, dict[str, object]] = {
    "kubernetes-secret-name": profile_schema("dns1123-subdomain"),
    "kubernetes-configmap-name": profile_schema("dns1123-subdomain"),
    "absolute-posix-path": {"type": "string", "pattern": r"^/[^\x00\r\n]*(?![\s\S])"},
}


def configuration(config: Path | None) -> dict[str, object]:
    """
    Read the local policy and reject misspelled top-level options.

    Args:
        config (Path | None): Explicit file or working-directory default.

    Returns:
        dict[str, object]: Unresolved configuration, empty when no default file exists.
    """
    path = config or Path(".hypothesis-helm.yaml")
    if config is None and not path.is_file():
        return {}
    document = yamlio.load(path.read_text())
    if not isinstance(document, dict) or set(document) - {
        "ignored",
        "input_constraints",
        "resource_schemas",
        "strict",
        "downstream_inputs",
        "yaml_parser",
        "compiler",
        "findings",
        *SETTING_KEYS,
    }:
        raise ValueError(f"{path}: unknown configuration key; see the complete example in docs/input-domains/README.md")
    return mapping(document)


def path_parts(value: str) -> tuple[str, ...]:
    """
    Parse explicit object paths and array-item wildcards without name guessing.

    Args:
        value (str): Dollar-rooted dotted path, with optional [*] array selectors.

    Returns:
        tuple[str, ...]: Object keys and wildcard segments.
    """
    if value == "$":
        return ()
    if not re.fullmatch(r"\$(?:\.[A-Za-z_][A-Za-z_0-9-]*|\[\*\])+", value):
        raise ValueError(f"Invalid input constraint path {value!r}; use $.field.nested or $.items[*].field")
    return tuple(key or "*" for key, _ in re.findall(r"\.([A-Za-z_][A-Za-z_0-9-]*)|(\[\*\])", value[1:]))


def check_schema(schema: dict[str, object], *, inline: bool = False) -> None:
    """
    Validate an independent schema without allowing implicit reference downloads.

    Args:
        schema (dict[str, object]): User-supplied inline or resource schema.
        inline (bool): Reject references whose roots would change when embedded in chart values.

    Returns:
        None: Valid schema, or a configuration error before generation starts.
    """
    for node in walk(schema):
        if inline and any(keyword in node for keyword in ("$ref", "$dynamicRef", "$recursiveRef", "$id")):
            raise ValueError("Inline input constraints must be self-contained without references or schema identifiers")
        for keyword in ("$ref", "$dynamicRef", "$recursiveRef"):
            reference = node.get(keyword)
            if keyword in node and (not isinstance(reference, str) or not reference.startswith("#")):
                raise ValueError("Input and resource schemas must use local references only")
    normalized = canonical(schema)
    validators.validator_for(normalized).check_schema(normalized)


def load_policy(
    config: Path | None,
    *,
    character_sets: str | None = None,
    max_examples: int | None = None,
    yaml_parser: str | None = None,
    strict: bool | None = None,
) -> dict[str, object]:
    """
    Resolve chart-scoped restrictions and freeze supplied resource schemas for workers.

    Args:
        config (Path | None): Policy file; schema filenames are relative to this file.
        character_sets (str | None): Optional CLI override for the configured character domain.
        max_examples (int | None): Explicit CLI override for the global Hypothesis example budget.
        yaml_parser (str | None): Explicit CLI override for the manifest parser backend.
        strict (bool | None): Explicit CLI override requiring schemas for every rendered custom resource.

    Returns:
        dict[str, object]: JSON-compatible policy with resource schema contents embedded.
    """
    document = configuration(config)
    if "strict" in document and type(document["strict"]) is not bool:
        raise ValueError("strict must be a Boolean")
    # Preserve an absent override so saved suites can retain their recorded mode.
    strict_policy = {"strict": strict if strict is not None else document["strict"]} if strict is not None or "strict" in document else {}
    parser_policy = (
        {"yaml_parser": validate_backend(yaml_parser if yaml_parser is not None else document["yaml_parser"])}
        if yaml_parser is not None or "yaml_parser" in document
        else {}
    )
    findings = validate_findings(document.get("findings", {}))
    limits = compiler_limits(document.get("compiler", {}))
    defaults = validate_settings(document)
    if max_examples is not None:
        defaults["hypothesis"] = {**mapping(defaults.get("hypothesis", {})), "max_examples": max_examples}
        validate_settings(defaults)
    root = (config or Path(".hypothesis-helm.yaml")).resolve().parent
    selected = validate_character_sets(defaults.get("character_sets", "ascii"))
    if character_sets is not None:
        selected = validate_character_sets(character_sets)
    if type(document.get("downstream_inputs", True)) is not bool:
        raise ValueError("downstream_inputs must be a Boolean")
    rules = document.get("input_constraints", []) or []
    resources = document.get("resource_schemas", {}) or {}
    if not isinstance(rules, list) or not isinstance(resources, dict):
        raise ValueError("input_constraints must be a list; resource_schemas must map apiVersion/Kind to JSON schema files")
    resolved: list[dict[str, object]] = []
    for raw in rules:
        rule = mapping(raw)
        if set(rule) - {"charts", "path", "profile", "schema", "allow_empty", "ignored", "enabled", "compiler", "findings", *SETTING_KEYS}:
            raise ValueError("Unknown input constraint option")
        charts = selectors(rule.get("charts"), root)
        generation = validate_settings(rule)
        path = rule.get("path")
        if not isinstance(path, str):
            raise ValueError("Each input constraint requires a string 'path'")
        path_parts(path)
        if "renderer_policy" in mapping(generation.get("hypothesis", {})) and path != "$":
            raise ValueError("Random renderer overrides require path: $; native calls are not ordinary values paths")
        compiler: dict[str, object] = {}
        if "compiler" in rule:
            if path != "$":
                raise ValueError("Chart compiler overrides require path: $; compiler budgets cannot vary by values branch")
            validated = compiler_limits(rule["compiler"])
            compiler = {"compiler": {key: validated[key] for key in mapping(rule["compiler"])}}
        controls: dict[str, object] = {}
        if "findings" in rule:
            controls["findings"] = validate_findings(rule["findings"], partial=True)
        for key in ("ignored", "enabled"):
            if key in rule:
                codes = rule[key]
                if not isinstance(codes, list) or any(not isinstance(code, str) or code not in CATALOG for code in codes):
                    raise ValueError(f"Input constraint '{key}' must be a list of known finding codes")
                controls[key] = sorted(set(codes))
        if set(sequence(controls.get("ignored", []))) & set(sequence(controls.get("enabled", []))):
            raise ValueError("An input constraint cannot both ignore and enable the same code")
        constrained = "profile" in rule or "schema" in rule
        if "profile" in rule and "schema" in rule or not constrained and not controls and not generation and not compiler:
            raise ValueError("Each input constraint requires a profile, schema, finding settings, generation settings or compiler settings")
        resolved_rule: dict[str, object] = {"charts": charts, "path": path, **controls, **generation, **compiler}
        if not constrained:
            if "allow_empty" in rule:
                raise ValueError("allow_empty requires a profile or schema")
            resolved.append(resolved_rule)
            continue
        if "profile" in rule:
            profile = str(rule["profile"])
            if profile not in PROFILES:
                raise ValueError(f"Unknown input profile {profile!r}; choose from {', '.join(PROFILES)}")
            schema = copy.deepcopy(PROFILES[profile])
        else:
            schema = canonical(mapping(rule["schema"]))
        check_schema(schema, inline=True)
        from hypothesis_helm.schemas.generation.compatibility import validation_view

        # Inline rules and compiler guards share the modern dialect, irrespective
        # of the syntax the user chose when declaring an independent restriction.
        schema = validation_view(schema)
        if type(rule.get("allow_empty", False)) is not bool:
            raise ValueError("allow_empty must be a Boolean")
        if rule.get("allow_empty"):
            if schema.get("type") != "string":
                raise ValueError("allow_empty requires a string constraint")
            schema = {"type": "string", "anyOf": [schema, {"const": ""}]}
        resolved.append({**resolved_rule, "schema": schema, "source": rule.get("profile", "inline")})
    supplied: dict[str, object] = {}
    for identity, filename in resources.items():
        if not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z0-9./-]+/[A-Za-z][A-Za-z0-9]*", identity):
            raise ValueError("Resource schema keys must be apiVersion/Kind, such as example.org/v1/Widget")
        if not isinstance(filename, str):
            raise ValueError(f"Resource schema {identity} must name a JSON schema file")
        schema = canonical(mapping(json.loads((root / filename).read_text())))
        check_schema(schema)
        supplied[identity] = schema
    return {
        **defaults,
        **parser_policy,
        **strict_policy,
        "input_constraints": resolved,
        "resource_schemas": supplied,
        "downstream_inputs": document.get("downstream_inputs", True),
        "character_sets": selected,
        "compiler": limits,
        "findings": findings,
    }


@lru_cache(maxsize=16)
def _file_policy(path: str) -> dict[str, object]:
    """
    Read an immutable command-owned snapshot once per process.

    Args:
        path (str): Absolute policy snapshot path inherited by workers.

    Returns:
        dict[str, object]: Complete resolved policy; missing or invalid files raise rather than disable validation.
    """
    return mapping(json.loads(Path(path).read_text()))


def inherited_policy(environment: dict[str, str] | None = None) -> dict[str, object]:
    """
    Load the full policy from its command-owned file or a legacy inline environment value.

    Args:
        environment (dict[str, str] | None): Explicit worker environment, or the central snapshot.

    Returns:
        dict[str, object]: Resolved constraints and schemas, independent of transport location.
    """
    source = env if environment is None else environment
    if path := source.get(FILE_ENVIRONMENT):
        return copy.deepcopy(_file_policy(path))
    return mapping(json.loads(source.get(ENVIRONMENT, "{}")))


def intersect(original: dict[str, object], restriction: dict[str, object]) -> dict[str, object]:
    """
    Intersect schemas while retaining simple finite domains when possible.

    Args:
        original (dict[str, object]): Existing authoritative or inferred schema.
        restriction (dict[str, object]): Additional generation restriction.

    Returns:
        dict[str, object]: A subset of both schemas, never a widened domain.
    """
    if "$ref" in original:
        return {"allOf": [copy.deepcopy(original), copy.deepcopy(restriction)]}
    result = copy.deepcopy(original)
    remaining: dict[str, object] = {}
    for key, value in restriction.items():
        if key not in result or result[key] == value:
            result[key] = copy.deepcopy(value)
        elif key in {"minimum", "minLength", "minItems", "minProperties"}:
            result[key] = max(result[key], value, key=number)
        elif key in {"maximum", "maxLength", "maxItems", "maxProperties"}:
            result[key] = min(result[key], value, key=number)
        elif key == "type":
            left = sequence(result[key]) if isinstance(result[key], list) else [result[key]]
            right = sequence(value) if isinstance(value, list) else [value]
            common = [kind for kind in left if kind in right or kind == "integer" and "number" in right]
            if "number" in left and "integer" in right:
                common.append("integer")
            if not common:
                raise ValueError("Input constraint has no types in common with the chart schema")
            result[key] = common[0] if len(common) == 1 else common
        else:
            remaining[key] = copy.deepcopy(value)
    if remaining:
        sequence(result.setdefault("allOf", [])).append(remaining)
    validator = validators.validator_for(result)(result)
    if "enum" in result or "const" in result:
        values = [result["const"]] if "const" in result else sequence(result["enum"])
        allowed = [value for value in values if validator.is_valid(json_value(value))]
        if not allowed:
            raise ValueError("Input constraint excludes every declared enum/const value")
        result["enum"] = allowed
    for lower, upper in (("minimum", "maximum"), ("minLength", "maxLength"), ("minItems", "maxItems")):
        if lower in result and upper in result and number(result[lower]) > number(result[upper]):
            raise ValueError(f"Input constraint has contradictory {lower}/{upper}")
    return result


def restrict(schema: dict[str, object], path: tuple[str, ...], restriction: dict[str, object]) -> dict[str, object]:
    """
    Add a path constraint without making optional parents required.

    Args:
        schema (dict[str, object]): Generation schema to copy.
        path (tuple[str, ...]): Exact object path, with * for collection members.
        restriction (dict[str, object]): Schema applied where that path exists.

    Returns:
        dict[str, object]: Restricted copy, leaving the supplied document untouched.
    """
    if not path:
        return intersect(schema, restriction)
    if "$ref" in schema:
        return {"allOf": [copy.deepcopy(schema), restrict({}, path, restriction)]}
    result = copy.deepcopy(schema)
    head, *tail = path
    if head == "*":
        member = restrict({}, tuple(tail), restriction)
        kind = result.get("type")
        kinds = kind if isinstance(kind, list) else [kind]
        if "object" in kinds:
            # An independent applicator reaches every map value without changing
            # which properties the authored schema allows or requires.
            clause: dict[str, object] = {"additionalProperties": member}
            if "array" in kinds:
                clause["items"] = member
            sequence(result.setdefault("allOf", [])).append(clause)
        elif isinstance(result.get("items", {}), dict) and "prefixItems" not in result:
            result["items"] = restrict(mapping(result.get("items", {})), tuple(tail), restriction)
        else:
            # Homogeneous items in a separate clause constrain both tuple prefixes
            # and tails, without rewriting positional or Boolean item schemas.
            sequence(result.setdefault("allOf", [])).append({"items": member})
    else:
        properties = mapping(result.setdefault("properties", {}))
        if head not in properties and ("additionalProperties" in result or "patternProperties" in result):
            sequence(result.setdefault("allOf", [])).append(restrict({}, path, restriction))
            return result
        existing = properties.get(head, {})
        if existing is not False:
            properties[head] = restrict({} if existing is True else mapping(existing), tuple(tail), restriction)
    return result

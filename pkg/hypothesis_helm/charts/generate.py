"""
Coalesce chart levers and emit one typed Hypothesis Python test per value path.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import math
import os
import re
from pathlib import Path

from attrs import asdict, define
from ruamel.yaml.comments import CommentedMap

from hypothesis_helm.charts import yamlio
from hypothesis_helm.charts.generated import RenderOptions
from hypothesis_helm.charts.runner import Chart, _schema_nodes
from hypothesis_helm.charts.templates import Action, Reference, discover, parse
from hypothesis_helm.reporting.progress import format_path
from hypothesis_helm.schemas.contracts import mapping, number, sequence, text

LOGGER = logging.getLogger(__name__)


@define
class ValuePath:
    """
    Describe a schema path and the provenance of its strategy.

    Attributes:
        path (tuple[str | int, ...]): Resolved value path or chart location.
        schema (dict[str, object]): Schema describing accepted values.
        origin (str): Source of the inferred or documented contract.
    """

    path: tuple[str | int, ...]
    schema: dict[str, object]
    origin: str = "schema"


@define
class Model:
    """
    Hold coalesced values, inferred schemas, paths, and diagnostics.

    Attributes:
        values (dict[str, object]): Round-trip coalesced values document.
        schema (dict[str, object]): Schema describing accepted values.
        paths (list[ValuePath]): Enumerated value paths and strategies.
        diagnostics (list[dict[str, object]]): Unresolved or inferred input details.
    """

    values: dict[str, object]
    schema: dict[str, object]
    paths: list[ValuePath]
    diagnostics: list[dict[str, object]]


def infer_schema(value: object) -> dict[str, object]:
    """
    Infer JSON types, never bounds or enums, from an observed YAML value.

    Args:
        value (object): Candidate value supplied by the property strategy.

    Returns:
        dict[str, object]: Resulting schema, values mapping, or structured report.
    """
    if value is None:
        return {}  # No evidence that a missing/null default only accepts null.
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int):
        return {"type": "integer"}
    if isinstance(value, float):
        return {"type": "number"}
    if isinstance(value, str):
        return {"type": "string"}
    if isinstance(value, dict):
        return {"type": "object", "properties": {k: infer_schema(v) for k, v in value.items()}}
    if isinstance(value, list):
        kinds = list({json.dumps(infer_schema(v), sort_keys=True) for v in value})
        items = {} if not kinds else json.loads(kinds[0]) if len(kinds) == 1 else {"anyOf": [json.loads(k) for k in sorted(kinds)]}
        return {"type": "array", "items": items}
    raise ValueError(f"non-JSON YAML value: {type(value).__name__}")


def dereference(schema: dict[str, object], root: dict[str, object], seen: tuple[str, ...] = ()) -> dict[str, object]:
    """
    Expand local references without discarding sibling constraints.

    Args:
        schema (dict[str, object]): JSON Schema defining the accepted value domain.
        root (dict[str, object]): Root schema used to resolve local references.
        seen (tuple[str, ...]): References already visited while resolving this schema.

    Returns:
        dict[str, object]: Resulting schema, values mapping, or structured report.
    """
    if not isinstance(schema, dict):
        return schema
    if "$ref" not in schema:
        return schema
    ref = text(schema["$ref"])
    if ref in seen:
        raise ValueError(f"recursive schema path cannot be enumerated: {ref}")
    if not ref.startswith("#"):
        raise ValueError("only local schema references are supported")
    target = root
    for segment in ref[2:].split("/") if ref != "#" else []:
        target = mapping(target[segment.replace("~1", "/").replace("~0", "~")])
    resolved = dereference(target, root, (*seen, ref))
    siblings = {k: v for k, v in schema.items() if k != "$ref"}
    if not siblings:
        return resolved
    return {"allOf": [resolved, siblings]}


def enumerate_paths(schema: dict[str, object]) -> list[ValuePath]:
    """
    Enumerate containers, leaves, array items and schema-defined map entries.

    `*` denotes array items or arbitrary map keys, and integer segments denote
    positional array schemas. Branch constraints are retained as a union of candidate
    subschemas; the complete schema is checked again when running each generated test.

    Args:
        schema (dict[str, object]): JSON Schema defining the accepted value domain.

    Returns:
        list[ValuePath]: Result of the documented operation.
    """
    collected: dict[tuple[str | int, ...], list[dict[str, object]]] = {}
    primary: dict[tuple[str | int, ...], list[dict[str, object]]] = {}
    root = schema

    def walk(
        node: object,
        path: tuple[str | int, ...],
        ancestors: tuple[int, ...] = (),
        unconditional: bool = True,
    ) -> None:
        """
        Collect schema paths and their unconditional declarations.

        Args:
            node (object): Current schema or template node.
            path (tuple[str | int, ...]): Value path or chart location to inspect.
            ancestors (tuple[int, ...]): Node identities already visited along this traversal.
            unconditional (bool): Whether the schema declaration applies outside conditional
                branches.

        Returns:
            None: None. The operation completes through its documented side effects.
        """
        if not isinstance(node, dict):
            if node is True and path:
                collected.setdefault(path, []).append({})
            return
        if id(node) in ancestors:
            raise ValueError(f"recursive schema at {path}")
        ancestors = (*ancestors, id(node))
        node = dereference(node, root)
        if path:
            collected.setdefault(path, []).append(copy.deepcopy(node))
            if unconditional:
                primary.setdefault(path, []).append(copy.deepcopy(node))
        for key, child in mapping(node.get("properties", {})).items():
            walk(child, (*path, key), ancestors, unconditional)
        items = node.get("items")
        if isinstance(items, dict):
            walk(items, (*path, "*"), ancestors, unconditional)
        elif isinstance(items, list):
            for index, child in enumerate(items):
                walk(child, (*path, index), ancestors, unconditional)
        for index, child in enumerate(sequence(node.get("prefixItems", []))):
            walk(child, (*path, index), ancestors, unconditional)
        if isinstance(node.get("additionalProperties"), dict):
            walk(node["additionalProperties"], (*path, "*"), ancestors, unconditional)
        for child in mapping(node.get("patternProperties", {})).values():
            walk(child, (*path, "*"), ancestors, unconditional)
        for keyword in ("allOf", "anyOf", "oneOf"):
            for branch in sequence(node.get(keyword, [])):
                walk(branch, path, ancestors, False)
        for keyword in ("then", "else"):
            if keyword in node:
                walk(node[keyword], path, ancestors, False)

    walk(schema, ())
    result = []
    for path, branches in collected.items():
        # Repeated branch paths generate one test whose complete input must still
        # satisfy the original full contract, including conjunctions/conditionals.
        # Outer declarations constrain all branches. A conditional minItems
        # fragment must not broaden a declared array into arbitrary JSON.
        branches = primary.get(path, branches)
        unique = {json.dumps(b, sort_keys=True): b for b in branches}
        node = next(iter(unique.values())) if len(unique) == 1 else {"anyOf": list(unique.values())}

        def expand(value: object, refs: tuple[str, ...] = ()) -> object:
            """
            Inline local schema references for standalone path strategies.

            Args:
                value (object): Candidate value supplied by the property strategy.
                refs (tuple[str, ...]): Reference pointers already expanded on this path.

            Returns:
                object: Parsed or generated value at the requested boundary.
            """
            if isinstance(value, list):
                return [expand(v, refs) for v in value]
            if not isinstance(value, dict):
                return value
            if "$ref" in value:
                ref = value["$ref"]
                if ref in refs:
                    raise ValueError(f"recursive schema path cannot be generated: {ref}")
                return expand(dereference(value, root), (*refs, ref))
            return {k: expand(v, refs) for k, v in value.items() if k not in ("$defs", "definitions")}

        result.append(ValuePath(path, mapping(expand(node))))
    return result


def _literal(token: str) -> tuple[bool, object]:
    """
    Check  literal.

    Args:
        token (str): Template token to resolve.

    Returns:
        tuple[bool, object]: Result of the documented operation.
    """
    if token.startswith('"'):
        try:
            return True, json.loads(token)
        except ValueError:
            return False, None
    if token.startswith("`") and token.endswith("`"):
        return True, token[1:-1]
    if token in ("true", "false"):
        return True, token == "true"
    if re.fullmatch(r"-?\d+(?:\.\d+)?", token):
        return True, json.loads(token)
    return False, None


def _fallbacks(chart: Chart, references: list[Reference]) -> dict[tuple[str, ...], list[object]]:
    """
    Use literal fallback evidence only when one resolved value path owns it.

    Args:
        chart (Chart): Loaded chart and its schema and defaults.
        references (list[Reference]): Resolved template value references with source locations.

    Returns:
        dict[tuple[str, ...], list[object]]: Result of the documented operation.
    """
    evidence: dict[tuple[str, ...], list[object]] = {}
    for file in sorted((chart.path / "templates").rglob("*")):
        if not file.is_file():
            continue
        try:
            nodes = parse(file.read_text())
        except ValueError:
            continue

        def walk(nodes: list[Action], file_path: Path = file) -> None:
            """
            Collect literal fallback evidence from nested template actions.

            Args:
                nodes (list[Action]): Template actions to inspect in lexical order.
                file_path (Path): File path used by this operation.

            Returns:
                None: None. The operation completes through its documented side effects.
            """
            for node in nodes:
                paths = {r.path for r in references if r.file == str(file_path.relative_to(chart.path)) and r.line == node.line and r.path}
                # Parent references introduced by index/aliases are not separate levers.
                paths = {p for p in paths if not any(q[: len(p)] == p and q != p for q in paths)}
                if len(paths) == 1:
                    path = next(iter(paths))
                    for i, token in enumerate(node.tokens[:-1]):
                        if token == "default":
                            known, value = _literal(node.tokens[i + 1])
                            if known:
                                evidence.setdefault(path, []).append(value)
                    if node.tokens[0] == "dig":
                        ts = node.tokens[: node.tokens.index("|")] if "|" in node.tokens else node.tokens
                        if len(ts) >= 4:
                            known, value = _literal(ts[-2])
                            if known:
                                evidence.setdefault(path, []).append(value)
                walk(node.children)
                walk(node.otherwise)

        walk(nodes)
    return evidence


def _get(values: dict[str, object], path: tuple[str, ...]) -> tuple[bool, object]:
    """
    Check  get.

    Args:
        values (dict[str, object]): Values document used as the rendering baseline.
        path (tuple[str, ...]): Value path or chart location to inspect.

    Returns:
        tuple[bool, object]: Result of the documented operation.
    """
    current: object = values
    try:
        for segment in path:
            current = mapping(current)[segment]
        return True, current
    except (KeyError, IndexError, TypeError, ValueError):
        return False, None


def _insert(values: dict[str, object], path: tuple[str, ...], value: object) -> bool:
    """
    Check  insert.

    Args:
        values (dict[str, object]): Values document used as the rendering baseline.
        path (tuple[str, ...]): Value path or chart location to inspect.
        value (object): Candidate value supplied by the property strategy.

    Returns:
        bool: Whether the requested condition holds.
    """
    current: object = values
    for segment in path[:-1]:
        if not isinstance(current, dict):
            return False
        if segment not in current:
            current[segment] = CommentedMap()
        current = mapping(current)[segment]
    if not isinstance(current, dict):
        return False
    current.setdefault(path[-1], value)
    return True


def _add_schema(root: dict[str, object], path: tuple[str, ...], inferred: dict[str, object]) -> None:
    """
    Check  add schema.

    Args:
        root (dict[str, object]): Root schema used to resolve local references.
        path (tuple[str, ...]): Value path or chart location to inspect.
        inferred (dict[str, object]): Type information inferred for an undocumented value.

    Returns:
        None: None. The operation completes through its documented side effects.
    """
    current = root
    for key in path:
        current.setdefault("type", "object")
        current = mapping(mapping(current.setdefault("properties", {})).setdefault(key, {}))
    for key, value in inferred.items():
        current.setdefault(key, value)


def coalesce(chart: Chart) -> Model:
    """
    Merge missing template levers into a round-trip, in-memory values document.

    Existing values and schema constraints win. Unknown values are explicit null
    placeholders with unconstrained strategies and diagnostics, not invented types.
    The original chart files are never modified.

    Args:
        chart (Chart): Loaded chart and its schema and defaults.

    Returns:
        Model: Result of the documented operation.
    """
    values = mapping(yamlio.load(yamlio.dump(chart.defaults)))
    schema = copy.deepcopy(chart.schema)
    references, warnings = discover(chart.path)
    diagnostics = [asdict(w) for w in warnings]
    fallbacks = _fallbacks(chart, references)
    inferred_paths = set()
    for path in sorted({r.path for r in references if r.path}, key=lambda p: (len(p), p)):
        LOGGER.info("Coalescing path %s", format_path(path))
        if "*" in path:
            diagnostics.append(
                {
                    "path": list(path),
                    "message": "wildcard resolved by schema/item tests; no invented key or item",
                }
            )
            continue
        found, value = _get(values, path)
        nodes = _schema_nodes(chart.schema, path, chart.schema)
        if not found:
            candidates = [n["default"] for n in nodes if "default" in n]
            candidates += fallbacks.get(path, [])
            if candidates and all(v == candidates[0] and type(v) is type(candidates[0]) for v in candidates):
                value = copy.deepcopy(candidates[0])
            elif any(r.path[: len(path)] == path and len(r.path) > len(path) for r in references):
                value = CommentedMap()
            else:
                value = None
                diagnostics.append(
                    {
                        "path": list(path),
                        "message": ("no unambiguous default; null placeholder, type from schema if available"),
                    }
                )
            if not _insert(values, path, value):
                diagnostics.append({"path": list(path), "message": "cannot insert through a non-object value"})
                continue
        if not nodes:
            _add_schema(schema, path, infer_schema(value))
            inferred_paths.add(path)

    # Every values.yaml path gets a strategy even if templates do not reference it.
    def complete(value: object, path: tuple[str, ...] = ()) -> None:
        """
        Infer schemas for values that remain undocumented.

        Args:
            value (object): Candidate value supplied by the property strategy.
            path (tuple[str, ...]): Value path or chart location to inspect.

        Returns:
            None: None. The operation completes through its documented side effects.
        """
        nodes = _schema_nodes(schema, path, schema) if path else []
        if path and not nodes:
            _add_schema(schema, path, infer_schema(value))
            inferred_paths.add(path)
        elif path and nodes and all(not any(k in n for k in ("type", "enum", "const", "anyOf", "oneOf", "allOf", "$ref")) for n in nodes):
            inferred = infer_schema(value)
            for node in nodes:
                for key, item in inferred.items():
                    node.setdefault(key, item)
            if inferred:
                inferred_paths.add(path)
        if isinstance(value, dict):
            for key, child in value.items():
                complete(child, (*path, key))
        # Inferred array items are handled by infer_schema and enumerate_paths.

    complete(values)
    paths = enumerate_paths(schema)
    known_paths = {entry.path for entry in paths}
    for path in sorted({r.path for r in references if r.path} - known_paths):
        paths.append(ValuePath(path, {}, "unresolved"))
        diagnostics.append(
            {
                "path": list(path),
                "message": "no schema for referenced path; generated unconstrained path test",
            }
        )
    for entry in paths:
        if any(entry.path[: len(p)] == p for p in inferred_paths):
            entry.origin = "inferred"
    return Model(values, schema, paths, diagnostics)


def strategy_source(schema: dict[str, object]) -> str:
    """
    Compile common path types to Hypothesis strategies, retaining all constraints.

    Args:
        schema (dict[str, object]): JSON Schema defining the accepted value domain.

    Returns:
        str: Serialized output or resolved strategy expression.
    """
    node = {k: v for k, v in schema.items() if k not in ("description", "title", "default", "examples", "$schema", "$defs", "definitions")}
    fallback = f"from_schema({schema!r})"
    if set(node) == {"const"}:
        return f"st.just({node['const']!r})"
    if set(node) <= {"enum", "type"} and "enum" in node:
        return f"st.sampled_from({node['enum']!r})"
    kind = node.get("type")
    if node == {"type": "boolean"}:
        return "st.booleans()"
    if node == {"type": "null"}:
        return "st.none()"
    if kind == "integer" and set(node) <= {
        "type",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
    }:
        low = math.ceil(number(node["minimum"])) if "minimum" in node else None
        high = math.floor(number(node["maximum"])) if "maximum" in node else None
        for key in ("exclusiveMinimum", "exclusiveMaximum"):
            if isinstance(node.get(key), bool):
                return fallback  # Draft 4 boolean exclusive bounds.
        if "exclusiveMinimum" in node:
            low = (
                max(low, math.floor(number(node["exclusiveMinimum"])) + 1)
                if low is not None
                else math.floor(number(node["exclusiveMinimum"])) + 1
            )
        if "exclusiveMaximum" in node:
            high = (
                min(high, math.ceil(number(node["exclusiveMaximum"])) - 1)
                if high is not None
                else math.ceil(number(node["exclusiveMaximum"])) - 1
            )
        return f"st.integers(min_value={low!r}, max_value={high!r})"
    if kind == "number" and set(node) <= {"type", "minimum", "maximum"}:
        return f"st.floats(min_value={node.get('minimum')!r}, max_value={node.get('maximum')!r}, allow_nan=False, allow_infinity=False)"
    if kind == "string" and set(node) <= {"type", "minLength", "maxLength"}:
        return f"st.text(min_size={node.get('minLength', 0)!r}, max_size={node.get('maxLength')!r})"
    if kind == "array" and isinstance(node.get("items"), dict) and set(node) <= {"type", "items", "minItems", "maxItems"}:
        return (
            f"st.lists({strategy_source(mapping(node['items']))}, min_size={node.get('minItems', 0)!r}, max_size={node.get('maxItems')!r})"
        )
    # Regex, multipleOf, uniqueItems, object required/optional keys, unions and
    # references are delegated to the existing JSON Schema strategy library.
    return fallback


def generate_tests(
    chart: Chart | str | Path,
    output: Path,
    *,
    max_examples: int = 100,
    options: RenderOptions | None = None,
    suite_location: Path | None = None,
) -> dict[str, object]:
    """
    Write a reviewable pytest module, coalesced YAML, schema and path inventory.

    Args:
        chart (Chart | str | Path): Loaded chart and its schema and defaults.
        output (Path): Directory receiving the generated test artifacts.
        max_examples (int): Maximum number of generated examples per property.
        options (RenderOptions | None): Helm rendering settings embedded in the generated suite.
        suite_location (Path | None): Logical output location for temporarily staged dry runs.

    Returns:
        dict[str, object]: Resulting schema, values mapping, or structured report.
    """
    if not isinstance(chart, Chart):
        chart = Chart.load(chart)
    if max_examples < 1:
        raise ValueError("max_examples must be positive")
    model = coalesce(chart)
    from hypothesis_helm.compiler.inputs import InputInventory

    input_inventory = InputInventory.build(chart)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "values.coalesced.yaml").write_text(yamlio.dump(model.values))
    (output / "values.inferred.schema.json").write_text(json.dumps(model.schema, indent=2) + "\n")
    inventory = {
        "paths": [dict(asdict(p), strategy=strategy_source(p.schema)) for p in model.paths],
        "diagnostics": model.diagnostics,
        "input_inventory": input_inventory.report(),
        "planned_known_fields": [
            list(path)
            for path in sorted(input_inventory.known)
            if path in {tuple(str(part) for part in entry.path) for entry in model.paths}
        ],
    }
    (output / "paths.json").write_text(json.dumps(inventory, indent=2) + "\n")
    relative = os.path.relpath(chart.path, suite_location or output)
    (output / "chart-source.json").write_text(json.dumps({"chart": relative}) + "\n")
    lines = [
        '"""\nVerify generated chart value paths against their inferred contracts.\n"""',
        "from collections.abc import Iterator",
        "from pathlib import Path",
        "import pytest",
        "from hypothesis import HealthCheck, given, settings",
        "from hypothesis import strategies as st",
        "from hypothesis.strategies import DataObject",
        "from hypothesis_jsonschema import from_schema",
        "from hypothesis_helm import Chart",
        "from hypothesis_helm.charts.generated import RenderOptions, check_path, prepared_chart",
        "",
        "HERE = Path(__file__).resolve().parent",
        f"OPTIONS = RenderOptions(**{asdict(options or RenderOptions())!r})",
        "",
        '@pytest.fixture(scope="module")',
        "def chart() -> Iterator[Chart]:",
        '    """',
        "    Prepare a temporary chart with the generated values contract.",
        "",
        "    Yields:",
        "        Chart: Isolated chart shared by this generated module.",
        '    """',
        f"    with prepared_chart(HERE / {relative!r}, HERE) as chart:",
        "        yield chart",
        "",
    ]
    for entry in model.paths:
        LOGGER.info("Generating test for path %s (%s)", format_path(entry.path), entry.origin)
        label = "_".join(str(p) for p in entry.path)
        name = re.sub(r"[^a-zA-Z0-9_]", "_", label)[:80]
        digest = hashlib.sha256(repr(entry.path).encode()).hexdigest()[:10]
        lines += [
            f"# Path: {entry.path!r}; contract: {entry.origin}",
            f"@pytest.mark.hypothesis_helm_path({entry.path!r})",
            f"@settings(max_examples={max_examples}, deadline=None, suppress_health_check=[HealthCheck.too_slow])",
            f"@given(value={strategy_source(entry.schema)}, data=st.data())",
            f"def test_{name}_{digest}(chart: Chart, value: object, data: DataObject) -> None:",
            '    """',
            "    Verify that this value path renders valid resource envelopes.",
            "",
            "    Args:",
            "        chart (Chart): Temporary chart containing the coalesced values.",
            "        value (object): Candidate drawn from the path strategy.",
            "        data (DataObject): Draw context for schema-dependent siblings.",
            "",
            "    Returns:",
            "        None: Rendered resources satisfy the configured contract.",
            '    """',
            f"    check_path(chart, {entry.path!r}, value, data, options=OPTIONS)",
            "",
        ]
    (output / "test_chart_values.py").write_text("\n".join(lines) + "\n")
    return {"output": str(output), "tests": len(model.paths), "diagnostics": model.diagnostics}

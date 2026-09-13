"""
Verify generate.
"""

import ast
import copy
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis_jsonschema import from_schema
from jsonschema import validate

from hypothesis_helm import Chart
from hypothesis_helm.charts import yamlio
from hypothesis_helm.charts.generate import (
    coalesce,
    enumerate_paths,
    generate_tests,
    strategy_source,
)
from hypothesis_helm.schemas.contracts import mapping, number, schema_strategy, sequence


def test_coalesce_fallbacks_in_memory() -> None:
    """
    Verify coalesce fallbacks in memory.

    Returns:
        None: None. The operation completes through its documented side effects.
    """
    chart = Chart.load("examples/hidden-levers")
    original = copy.deepcopy(chart.defaults)
    model = coalesce(chart)
    assert model.values["secretSwitch"] == "fallback"
    assert model.values["other-switch"] == "off"
    assert chart.defaults == original
    for name in ("secretSwitch", "other-switch"):
        assert mapping(mapping(model.schema["properties"])[name])["type"] == "string"
        assert any(p.path == (name,) and p.origin == "inferred" for p in model.paths)


def test_roundtrip_comments_and_merge_keys(tmp_path: Path) -> None:
    """
    Verify roundtrip comments and merge keys.

    Args:
        tmp_path (Path): Temporary directory supplied by pytest.

    Returns:
        None: None. The operation completes through its documented side effects.
    """
    chart_dir = tmp_path / "chart"
    shutil.copytree("examples/hidden-levers", chart_dir)
    (chart_dir / "values.yaml").write_text(
        '# keep this comment\nvisible: "hello" # inline\nbase: &base\n  enabled: true\ncopy:\n  <<: *base\n'
    )
    result = coalesce(Chart.load(chart_dir))
    output = yamlio.dump(result.values)
    assert "# keep this comment" in output and "# inline" in output
    assert "&base" in output and "<<: *base" in output
    assert mapping(result.values["copy"])["enabled"] is True
    assert mapping(mapping(mapping(mapping(result.schema["properties"])["copy"])["properties"])["enabled"])["type"] == "boolean"


def test_schema_paths_refs_arrays_and_branches() -> None:
    """
    Verify schema paths refs arrays and branches.

    Returns:
        None: None. The operation completes through its documented side effects.
    """
    schema: dict[str, object] = {
        "type": "object",
        "definitions": {"item": {"type": "object", "properties": {"port": {"type": "integer"}}}},
        "properties": {
            "items": {"type": "array", "items": {"$ref": "#/definitions/item"}},
            "settings": {
                "anyOf": [
                    {"type": "object", "properties": {"a": {"type": "boolean"}}},
                    {"type": "object", "properties": {"b": {"type": "string"}}},
                ]
            },
        },
    }
    paths = {p.path for p in enumerate_paths(schema)}
    assert {
        ("items",),
        ("items", "*"),
        ("items", "*", "port"),
        ("settings", "a"),
        ("settings", "b"),
    } <= paths


@pytest.mark.parametrize(
    "schema,expected",
    [
        ({"type": "boolean"}, "st.booleans()"),
        ({"type": "integer", "minimum": 2, "maximum": 7}, "st.integers(min_value=2, max_value=7)"),
        (
            {"type": "integer", "exclusiveMinimum": 2, "exclusiveMaximum": 7},
            "st.integers(min_value=3, max_value=6)",
        ),
        ({"type": "string", "minLength": 1, "maxLength": 3}, "st.text(min_size=1, max_size=3)"),
        ({"type": "string", "enum": ["a", "b"]}, "st.sampled_from(['a', 'b'])"),
        (
            {"type": "array", "items": {"type": "boolean"}, "maxItems": 2},
            "st.lists(st.booleans(), min_size=0, max_size=2)",
        ),
    ],
)
def test_strategy_compiler(schema: dict[str, object], expected: str) -> None:
    """
    Verify strategy compiler.

    Args:
        schema (dict[str, object]): JSON Schema defining the accepted value domain.
        expected (str): Expected strategy expression for the schema.

    Returns:
        None: None. The operation completes through its documented side effects.
    """
    source = strategy_source(schema)
    assert source == expected

    @settings(max_examples=12)
    @given(eval(source, {"st": st, "from_schema": from_schema}))
    def valid(value: object) -> None:
        """
        Assert that generated values satisfy the test contract.

        Args:
            value (object): Candidate value supplied by the property strategy.

        Returns:
            None: None. The operation completes through its documented side effects.
        """
        validate(value, schema)

    valid()


def test_complex_constraints_use_library() -> None:
    """
    Verify complex constraints use library.

    Returns:
        None: None. The operation completes through its documented side effects.
    """
    for schema in (
        {"type": "integer", "multipleOf": 3},
        {"type": "string", "pattern": "^[ab]+$"},
        {"type": "array", "items": {"type": "integer"}, "uniqueItems": True},
    ):
        assert strategy_source(mapping(schema)).startswith("from_schema(")


def test_generated_source_one_function_per_path(tmp_path: Path) -> None:
    """
    Verify generated source one function per path.

    Args:
        tmp_path (Path): Temporary directory supplied by pytest.

    Returns:
        None: None. The operation completes through its documented side effects.
    """
    report = generate_tests("examples/workload", tmp_path, max_examples=3)
    source = (tmp_path / "test_chart_values.py").read_text()
    functions = [n.name for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
    assert len(functions) == report["tests"] == 4
    assert "st.integers(min_value=0, max_value=5)" in source
    assert len(json.loads((tmp_path / "paths.json").read_text())["paths"]) == 4


@pytest.mark.integration
@pytest.mark.skipif(not shutil.which("helm"), reason="Helm is required")
def test_generated_suite_runs(tmp_path: Path) -> None:
    """
    Verify generated suite runs.

    Args:
        tmp_path (Path): Temporary directory supplied by pytest.

    Returns:
        None: None. The operation completes through its documented side effects.
    """
    import sys

    generate_tests("examples/workload", tmp_path, max_examples=3)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(tmp_path / "test_chart_values.py")],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "4 passed" in result.stdout


def test_reference_to_property_is_self_contained() -> None:
    """
    Verify reference to property is self contained.

    Returns:
        None: None. The operation completes through its documented side effects.
    """
    schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "port": {"type": "integer", "minimum": 1, "maximum": 2},
            "ports": {"type": "array", "maxItems": 2, "items": {"$ref": "#/properties/port"}},
        },
    }
    item = next(p for p in enumerate_paths(schema) if p.path == ("ports",))
    assert "$ref" not in repr(item.schema)

    @settings(max_examples=5)
    @given(schema_strategy(item.schema))
    def valid(value: object) -> None:
        """
        Assert that generated values satisfy the test contract.

        Args:
            value (object): Candidate value supplied by the property strategy.

        Returns:
            None: None. The operation completes through its documented side effects.
        """
        assert all(1 <= number(p) <= 2 for p in sequence(value))

    valid()


def test_recursive_reference_is_explicit() -> None:
    """
    Verify recursive reference is explicit.

    Returns:
        None: None. The operation completes through its documented side effects.
    """
    with pytest.raises(ValueError, match="recursive"):
        enumerate_paths({"type": "object", "properties": {"next": {"$ref": "#"}}})


@pytest.mark.integration
@pytest.mark.skipif(not shutil.which("helm"), reason="Helm is required")
def test_array_paths_and_dependent_context(tmp_path: Path) -> None:
    """
    Verify array paths and dependent context.

    Args:
        tmp_path (Path): Temporary directory supplied by pytest.

    Returns:
        None: None. The operation completes through its documented side effects.
    """
    import sys

    chart_dir = tmp_path / "chart"
    shutil.copytree("examples/configmap", chart_dir)
    (chart_dir / "values.yaml").write_text("items: []\nenabled: false\n")
    schema: dict[str, object] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["items", "enabled"],
        "properties": {
            "items": {
                "type": "array",
                "maxItems": 2,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["port", "name"],
                    "properties": {
                        "port": {"type": "integer", "minimum": 1, "maximum": 3},
                        "name": {"enum": ["a", "b"]},
                    },
                },
            },
            "enabled": {"type": "boolean"},
        },
        "if": {"properties": {"enabled": {"const": True}}},
        "then": {"properties": {"items": {"minItems": 1}}},
    }
    (chart_dir / "values.schema.json").write_text(json.dumps(schema))
    (chart_dir / "templates/resource.yaml").write_text(
        "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: example\ndata:\n  items: {{ .Values.items | toJson | quote }}\n"
    )
    generated = tmp_path / "generated"
    generate_tests(chart_dir, generated, max_examples=4)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(generated / "test_chart_values.py")],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_conditional_fragment_does_not_broaden_base_type() -> None:
    """
    Verify conditional fragment does not broaden base type.

    Returns:
        None: None. The operation completes through its documented side effects.
    """
    schema: dict[str, object] = {
        "type": "object",
        "properties": {"items": {"type": "array", "items": {"type": "boolean"}}},
        "if": {"properties": {"enabled": {"const": True}}},
        "then": {"properties": {"items": {"minItems": 1}}},
    }
    entry = next(p for p in enumerate_paths(schema) if p.path == ("items",))
    assert entry.schema["type"] == "array"


def test_infers_untyped_yaml_path(tmp_path: Path) -> None:
    """
    Verify infers untyped yaml path.

    Args:
        tmp_path (Path): Temporary directory supplied by pytest.

    Returns:
        None: None. The operation completes through its documented side effects.
    """
    chart_dir = tmp_path / "chart"
    shutil.copytree("examples/workload", chart_dir)
    schema = json.loads((chart_dir / "values.schema.json").read_text())
    schema["properties"]["replicas"] = {"description": "Count"}
    (chart_dir / "values.schema.json").write_text(json.dumps(schema))
    model = coalesce(Chart.load(chart_dir))
    entry = next(p for p in model.paths if p.path == ("replicas",))
    assert entry.schema["type"] == "integer"
    assert entry.origin == "inferred"

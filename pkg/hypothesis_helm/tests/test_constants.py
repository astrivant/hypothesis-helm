"""
Exercise deterministic configuration scaffolds without generated-value repair or API inference.
"""

import json
import shutil
from pathlib import Path
from textwrap import dedent

import pytest

from hypothesis_helm.charts import yamlio
from hypothesis_helm.charts.runner import Chart
from hypothesis_helm.compiler.constants import fill_missing, zero_candidate
from hypothesis_helm.compiler.minimum import export_minimal
from hypothesis_helm.schemas.contracts import mapping
from hypothesis_helm.schemas.model import Missing, ValuesModel


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("boolean", False),
        ("integer", 0),
        ("number", 0.0),
        ("string", ""),
        ("array", []),
        ("object", {}),
        ("null", None),
    ],
)
def test_type_constants(kind: str, expected: object) -> None:
    """
    Distinguish scalar types and allocate independent collection defaults.

    Args:
        kind (str): Declared JSON type.
        expected (object): Deterministic type constant.

    Returns:
        None: Each known type has its zero; unknown types never become null placeholders.
    """
    node = ValuesModel.from_schema({"type": kind}).root
    first, second = zero_candidate(node), zero_candidate(node)
    assert first == second == expected
    assert type(first) is type(expected)
    if isinstance(first, (list, dict)):
        assert first is not second
    assert isinstance(zero_candidate(ValuesModel.from_schema({}).root), Missing)


def test_supplied_values_defaults_and_unknown_types() -> None:
    """
    Populate required and referenced gaps without changing supplied values or solving constraints.

    Returns:
        None: Existing values win; known defaults and constants precede typed zeros.
    """
    schema: dict[str, object] = {
        "type": "object",
        "required": ["flag", "count", "text", "nullable", "unknown", "bounded", "declared", "fixed", "items"],
        "properties": {
            "flag": {"type": "boolean", "default": True},
            "count": {"type": "integer", "default": 10},
            "text": {"type": "string", "default": "hello"},
            "nullable": {"type": ["string", "null"], "default": "hello"},
            "unknown": {},
            "bounded": {"type": "integer", "minimum": 1},
            "declared": {"type": "integer", "default": 8},
            "fixed": {"const": "known"},
            "optional": {"type": "string"},
            "items": {"type": "array", "minItems": 1, "items": {"type": "string"}},
            "service": {"type": "object", "properties": {"port": {"type": "integer"}}},
        },
    }
    values: dict[str, object] = {"flag": False, "count": 0, "text": "", "nullable": None}
    original = dict(values)
    generated = fill_missing(ValuesModel.from_schema(schema), values, {("service", "port")})
    assert generated == {**values, "bounded": 0, "declared": 8, "fixed": "known", "items": [], "service": {"port": 0}}
    assert values == original
    assert "unknown" not in generated and "optional" not in generated


@pytest.mark.integration
@pytest.mark.skipif(not shutil.which("helm"), reason="Helm required")
@pytest.mark.parametrize("downstream_rejects", [False, True])
def test_invalid_zero_stays_in_example(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, downstream_rejects: bool) -> None:
    """
    Export a deterministic zero even when input or downstream validation rejects it.

    Args:
        tmp_path (Path): Source chart and export directory.
        monkeypatch (pytest.MonkeyPatch): Replace downstream validation with a deterministic rejection.
        downstream_rejects (bool): Reject during manifest validation instead of input validation.

    Returns:
        None: The example remains zero, records the error, and is stable across repeated exports.
    """
    (tmp_path / "templates").mkdir()
    (tmp_path / "Chart.yaml").write_text(
        dedent("""
        apiVersion: v2
        name: example
        version: 1.0.0
    """)
    )
    (tmp_path / "templates/resource.yaml").write_text(
        dedent("""
        apiVersion: example.test/v1
        kind: Indexed
        metadata:
          name: example
        spec:
          index: {{ .Values.index }}
    """)
    )
    schema: dict[str, object] = {
        "type": "object",
        "required": ["index"],
        "properties": {"index": {"type": "integer", "minimum": 0 if downstream_rejects else 1}},
    }
    (tmp_path / "values.schema.json").write_text(json.dumps(schema))
    (tmp_path / "values.yaml").write_text("{}\n")

    def reject(manifests: str, timeout: float) -> None:
        """
        Model a downstream rule requiring a positive index.

        Args:
            manifests (str): Actual Helm-rendered YAML.
            timeout (float): Validation budget.

        Returns:
            None: The zero candidate fails without proposing a replacement.
        """
        assert mapping(mapping(yamlio.load_all(manifests)[0])["spec"])["index"] == 0
        raise AssertionError("API index must be at least 1")

    if downstream_rejects:
        monkeypatch.setattr("hypothesis_helm.charts.runner.validate", reject)
    chart = Chart(tmp_path, schema, {})
    target = tmp_path / "values-minimal.yaml"
    result = export_minimal(chart, target)
    verification = mapping(result["verification"])
    assert not verification["verified"]
    assert not verification["deletion_minimal"]
    assert verification["candidates_checked"] == 2
    assert yamlio.load_all(target.read_text())[0] == {"index": 0}
    assert "API index" in str(verification["validation_error"]) if downstream_rejects else "schema" in str(verification["validation_error"])
    previous = target.read_bytes()
    export_minimal(chart, target)
    assert target.read_bytes() == previous
    assert (tmp_path / "values.yaml").read_text() == "{}\n"

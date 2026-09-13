"""
Require configurable fields in original values rather than inferred defaults.
"""

import json
from pathlib import Path

import pytest

from hypothesis_helm.charts.presence import has_path
from hypothesis_helm.charts.runner import Chart, audit
from hypothesis_helm.cli import main
from hypothesis_helm.schemas.contracts import mapping, sequence


def chart_files(directory: Path, values: dict[str, object]) -> Path:
    """
    Create a chart with a schema-only field and a template fallback.

    Args:
        directory (Path): Chart directory.
        values (dict[str, object]): Source values to serialize unchanged.

    Returns:
        Path: Chart containing both documented configurable fields.
    """
    directory.mkdir()
    (directory / "templates").mkdir()
    (directory / "Chart.yaml").write_text("apiVersion: v2\nname: strict\nversion: 0.1.0\n")
    (directory / "values.yaml").write_text(json.dumps(values))
    (directory / "values.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {
                    "schemaOnly": {
                        "type": "boolean",
                        "default": False,
                        "description": "Optional setting",
                    },
                    "fallback": {"type": "string", "description": "Template fallback"},
                },
            }
        )
    )
    (directory / "templates/resource.yaml").write_text(
        'apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: {{ .Values.fallback | default "fallback" }}\n'
    )
    return directory


@pytest.mark.parametrize("command", ["audit", "test", "generate", "run"])
def test_strict_requires_source_fields(tmp_path: Path, command: str, capsys: pytest.CaptureFixture[str]) -> None:
    """
    Reject schema defaults and template fallbacks as substitutes for source values.

    Args:
        tmp_path (Path): Isolated chart and generated suite.
        command (str): Helm command enforcing strict checks.
        capsys (pytest.CaptureFixture[str]): Capture audit diagnostics.

    Returns:
        None: Missing fields fail before testing and explicit fields satisfy presence.
    """
    chart = chart_files(tmp_path / "chart", {})
    suite = tmp_path / "suite"
    assert main(["generate", str(chart), "--output", str(suite)]) == 0
    capsys.readouterr()
    original = (chart / "values.yaml").read_bytes()
    arguments = [command, str(suite if command == "run" else chart), "--strict"]
    if command in ("test", "run"):
        arguments += ["--dry-run"]
    if command == "generate":
        arguments += ["--output", str(tmp_path / "strict-suite")]
    assert main(arguments) == 1
    report = json.loads(capsys.readouterr().out)
    missing = {tuple(entry["path"]) for entry in report["findings"] if entry["issue"] == "no-default"}
    assert missing == {("schemaOnly",), ("fallback",)}
    assert (chart / "values.yaml").read_bytes() == original
    assert not (tmp_path / "strict-suite").exists()
    (chart / "values.yaml").write_text('{"schemaOnly":false,"fallback":"fallback"}')
    assert main(arguments) == 0


@pytest.mark.parametrize(
    ("values", "path", "present"),
    [
        ({"field": None}, ("field",), True),
        ({"field": None}, ("field", "child"), False),
        ({"items": []}, ("items", "*"), True),
        ({"items": []}, ("items", "*", "name"), False),
        ({"items": [{"name": "a"}, {}]}, ("items", "*", "name"), False),
        ({"items": [{"name": "a"}, {"name": None}]}, ("items", "*", "name"), True),
        ({"map": {"first": {"name": "a"}, "second": {}}}, ("map", "*", "name"), False),
        ({"items": ["a"]}, ("items", 1), False),
    ],
)
def test_collection_presence(values: dict[str, object], path: tuple[str | int, ...], present: bool) -> None:
    """
    Require named fields in all entries and distinguish explicit null from missing keys.

    Args:
        values (dict[str, object]): Original YAML values.
        path (tuple[str | int, ...]): Configurable path.
        present (bool): Expected presence result.

    Returns:
        None: Collection and scalar presence follow strict source-document semantics.
    """
    assert has_path(values, path) == present


def test_audit_checks_unreferenced_collection_fields(tmp_path: Path) -> None:
    """
    Inspect schema-only nested item fields even when no template reads them.

    Args:
        tmp_path (Path): Chart fixture location.

    Returns:
        None: Missing nested fields are exposed as audit findings.
    """
    path = chart_files(tmp_path / "chart", {"schemaOnly": False, "fallback": "ok"})
    chart = Chart.load(path)
    chart.schema["properties"] = {
        "items": {
            "type": "array",
            "description": "Items",
            "items": {
                "type": "object",
                "description": "Item",
                "properties": {
                    "name": {"type": "string", "description": "Name"},
                },
            },
        },
    }
    chart.defaults["items"] = [{"name": "a"}, {}]
    assert any(
        mapping(finding)["path"] == ["items", "*", "name"] and mapping(finding)["issue"] == "no-default"
        for finding in sequence(audit(chart)["findings"])
    )

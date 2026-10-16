"""
Preserve valid chart defaults when templates reference omitted optional fields.
"""

from __future__ import annotations

import json
from pathlib import Path

from hypothesis_helm import Chart
from hypothesis_helm.charts.suites.generate import coalesce
from jsonschema import validate


def test_optional_configuration_stays_empty(tmp_path: Path) -> None:
    """
    Retain an explicitly empty configuration despite references in a disabled branch.

    Args:
        tmp_path (Path): Temporary synthetic chart, without credentials or dependencies.

    Returns:
        None: Coalescing preserves the valid baseline and still discovers its fields.
    """
    schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "enabled": {"type": "boolean"},
            "configuration": {
                "anyOf": [
                    {"type": "object", "maxProperties": 0},
                    {
                        "type": "object",
                        "required": ["kind", "path"],
                        "properties": {
                            "kind": {"type": "string", "enum": ["git"], "default": "git"},
                            "path": {"type": "string", "minLength": 1},
                        },
                    },
                ]
            },
        },
    }
    (tmp_path / "Chart.yaml").write_text("apiVersion: v2\nname: optional\nversion: 0.1.0\n")
    (tmp_path / "values.yaml").write_text("enabled: false\nconfiguration: {}\n")
    (tmp_path / "values.schema.json").write_text(json.dumps(schema))
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates/config.yaml").write_text(
        "{{ if .Values.enabled }}\nkind: {{ .Values.configuration.kind }}\npath: {{ .Values.configuration.path }}\n{{ end }}\n"
    )
    chart = Chart.load(tmp_path)
    model = coalesce(chart)

    validate(model.values, schema)
    assert model.values == chart.defaults == {"enabled": False, "configuration": {}}
    assert {("configuration", "kind"), ("configuration", "path")} <= {path.path for path in model.paths}

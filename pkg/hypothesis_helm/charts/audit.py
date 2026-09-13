"""
Audit original chart values, declared schemas, and template references.
"""

from __future__ import annotations

import logging

from hypothesis_helm.charts.model import Chart, _default_paths, _schema_nodes
from hypothesis_helm.charts.presence import has_path
from hypothesis_helm.charts.templates import discover
from hypothesis_helm.compiler.passes.complexity import measure
from hypothesis_helm.compiler.passes.inputs import InputInventory
from hypothesis_helm.reporting.progress import format_path

LOGGER = logging.getLogger(__name__)


def audit(chart: Chart) -> dict[str, object]:
    """
    Inventory schema, template, and default paths against the original values document.

    Args:
        chart (Chart): Loaded chart and its schema and defaults.

    Returns:
        dict[str, object]: Resulting schema, values mapping, or structured report.
    """
    from attrs import asdict

    from hypothesis_helm.schemas.paths import enumerate_paths

    references, diagnostics = discover(chart.path, prune_literals=True)
    defaults = set(_default_paths(chart.defaults))
    declared = {entry.path: entry.schema for entry in enumerate_paths(chart.schema)}
    paths = defaults | {r.path for r in references if r.path} | declared.keys()
    findings = []
    for path in sorted(paths, key=repr):
        LOGGER.info("Auditing path %s", format_path(path))
        nodes = _schema_nodes(chart.schema, tuple(str(segment) for segment in path), chart.schema)
        if not nodes and path in declared:
            nodes = [declared[path]]
        locations = [asdict(r) for r in references if r.path == path]
        if not nodes:
            findings.append({"path": list(path), "issue": "undocumented", "references": locations})
        elif not any("type" in n or "enum" in n or "const" in n for n in nodes):
            findings.append({"path": list(path), "issue": "untyped", "references": locations})
        elif not any(n.get("description") for n in nodes):
            findings.append({"path": list(path), "issue": "missing-description", "references": locations})
        if not has_path(chart.defaults, path):
            findings.append(
                {
                    "path": list(path),
                    "issue": "no-default",
                    "references": locations,
                    "message": "Configurable field is absent from the original values.yaml",
                }
            )
    return {
        "chart": str(chart.path),
        "complexity": measure(chart),
        "references": [asdict(r) for r in references],
        "findings": findings,
        "unresolved": [asdict(d) for d in diagnostics],
        "input_inventory": InputInventory.build(chart).report(),
    }

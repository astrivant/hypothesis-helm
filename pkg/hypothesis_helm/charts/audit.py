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
from hypothesis_helm.compiler.passes.sampling import profile as sampling_profile
from hypothesis_helm.findings.generator import FindingGenerator
from hypothesis_helm.reporting.progress import format_path
from hypothesis_helm.rules import AUDIT_RULES, ignored, ignored_codes

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
    findings: list[dict[str, object]] = []
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
    for finding in findings:
        finding["code"] = AUDIT_RULES[str(finding["issue"])]
    unresolved: list[dict[str, object]] = [{**asdict(d), "code": "HH2005"} for d in diagnostics]
    for finding in [*findings, *unresolved]:
        finding["finding"] = FindingGenerator.create(
            str(finding["code"]), str(finding.get("message", finding.get("issue", "Unresolved value access")))
        ).record()
    suppressed = [finding for finding in [*findings, *unresolved] if ignored(str(finding["code"]))]
    findings = [finding for finding in findings if not ignored(str(finding["code"]))]
    complexity = measure(chart)
    return {
        "chart": str(chart.path),
        "complexity": complexity,
        "sampling_profile": sampling_profile(chart, complexity),
        "references": [asdict(r) for r in references],
        "findings": findings,
        "unresolved": [finding for finding in unresolved if not ignored("HH2005")],
        "ignored_findings": suppressed,
        "ignored_rules": ignored_codes(),
        "input_inventory": InputInventory.build(chart).report(),
    }

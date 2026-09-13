"""
Portable Markdown and paginated PDF summaries for repository scans.
"""

from __future__ import annotations

import json
import re
import textwrap
from pathlib import Path

from reportlab.pdfgen.canvas import Canvas  # type: ignore[import-untyped]

from hypothesis_helm.reporting.errors import deduplicate_errors
from hypothesis_helm.schemas.contracts import mapping, sequence

HELM_DEBUG_HINT = re.compile(r"(?m)^[ \t]*Use --debug flag to render out invalid YAML[ \t]*\r?$\n?")


def wrap_markdown(content: str) -> str:
    """
    Wrap report prose to 140 columns without changing code blocks or link targets.

    Headings, tables, indented code, and indivisible tokens may exceed the limit.

    Args:
        content (str): Generated Markdown report.

    Returns:
        str: Wrapped Markdown with a final newline.
    """
    lines: list[str] = []
    fence = ""
    for line in content.splitlines():
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if fence:
            lines.append(line)
            if re.fullmatch(r" {0,3}" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}\s*", line):
                fence = ""
            continue
        if marker:
            fence = marker[1]
        if marker or len(line) <= 140 or line.startswith(("#", "|", "    ", "\t")):
            lines.append(line)
            continue
        bullet = re.match(r"^(\s*(?:[-+*]|\d+[.)])\s+)", line)
        prefix = bullet[0] if bullet else ""
        continuation = " " * len(prefix)
        # Keep inline code and complete links together, including paths with spaces.
        tokens = re.findall(r"(?:!?\[[^\]]*\]\((?:<[^>]*>|[^)\s]*)\)|`+[^`]*`+|\S)+", line[len(prefix) :])
        current = prefix
        width = 138 if line.endswith("  ") else 140
        for token in tokens:
            separator = " " if current.strip() and current != prefix else ""
            if len(current) + len(separator) + len(token) > width and current.strip() and current != prefix:
                lines.append(current)
                current = continuation
                separator = ""
            current += separator + token
        lines.append(current + ("  " if line.endswith("  ") else ""))
    return "\n".join(lines) + "\n"


def display_error(error: object) -> str:
    """
    Present useful diagnostics while leaving raw errors in the JSON artifacts.

    Args:
        error (object): Recorded error, including historical tooling failures.

    Returns:
        str: Human-readable diagnostic without Helm's redundant debug suggestion.
    """
    return (
        HELM_DEBUG_HINT.sub("", str(error))
        .rstrip()
        .replace(
            "invalid rendered manifest: Object of type TaggedScalar is not JSON serializable",
            "The test tool could not convert a YAML-tagged value to JSON. "
            "See this chart's reproducing values. "
            "This diagnostic alone does not establish a chart defect.",
        )
    )


def write_reports(report: dict[str, object], stem: Path) -> tuple[Path, Path]:
    """
    Write both report formats, accepting an explicit stem or either extension.

    Args:
        report (dict[str, object]): Scan summary including chart diagnostics.
        stem (Path): Output stem, Markdown filename, or PDF filename.

    Returns:
        tuple[Path, Path]: Markdown and PDF output paths.
    """
    deduplicate_errors(report)
    if stem.suffix.lower() in (".md", ".pdf"):
        stem = stem.with_suffix("")
    markdown, pdf = Path(f"{stem}.md"), Path(f"{stem}.pdf")
    markdown.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {report.get('title', 'Helm chart scan')}",
        "",
        f"Directory: {report['directory']}",
        f"Started (Unix epoch): {report['started_epoch']}",
        f"Elapsed (wall clock): {float(str(report['elapsed_seconds'])):.2f} seconds",
        f"Charts discovered: {report['charts_discovered']}",
        f"Scan status: {report.get('scan_status', 'not recorded')}",
        f"Discovery complete: {report.get('discovery_complete', 'not recorded')}",
        f"Unstarted charts: {report.get('unstarted_charts', 'not recorded')}",
        "",
        "Results describe the tested sample; they do not prove chart correctness.",
        "Baseline-only, skipped, blocked, and incomplete charts are not property-test passes.",
        "",
        "## Status counts",
        "",
        "```json",
        json.dumps(report["counts"], indent=2),
        "```",
        "",
        "## Settings",
        "",
        "```json",
        json.dumps(report["settings"], indent=2),
        "```",
        "",
    ]
    if "testing_seconds" in report:
        lines[5:5] = [
            f"Chart testing: {float(str(report['testing_seconds'])):.2f} seconds",
            f"Dependency preparation: {float(str(report['dependency_preparation_seconds'])):.2f} seconds (excluded from testing budgets)",
        ]
    summary = report.get("summary", [])
    if isinstance(summary, list):
        lines[2:2] = [str(line) for line in summary] + [""]
    errors = sequence(report["error_groups"])
    if errors:
        counts = mapping(report["error_summary"])
        lines.extend(
            [
                "## Errors",
                "",
                f"{counts['unique_errors']} distinct diagnostics across "
                f"{counts['occurrences']} occurrences; {counts['duplicates']} repeats grouped.",
                "Matching diagnostics do not establish a shared root cause.",
                "",
            ]
        )
        for entry in errors:
            group = mapping(entry)
            lines.extend([f"### {group['id']}", ""])
            source = group.get("source")
            if isinstance(source, dict):
                lines.extend(
                    [
                        f"Source: {source['name']} {source['version']} / {source['template']}",
                        "",
                    ]
                )
            content = display_error(group["error"])
            fence = "`" * max(3, max(map(len, re.findall(r"`+", content)), default=0) + 1)
            lines.extend([f"{fence}text", content, fence, ""])
            for occurrence in sequence(group["occurrences"]):
                item = mapping(occurrence)
                label = f"{item['chart']} ({item['phase']}; {item['status']})"
                artifacts = item.get("artifacts")
                lines.append(f"- [{label}](<{artifacts}>)" if artifacts else f"- {label}")
            lines.append("")
    lines.extend(["## Charts", ""])
    charts = report["charts"]
    assert isinstance(charts, list)
    for chart in charts:
        assert isinstance(chart, dict)
        title = str(chart["chart"]).replace("\n", " ")
        lines.extend([f"### {title}", ""])
        package = chart.get("package")
        if isinstance(package, dict):
            lines.extend(
                [
                    f"Package: {package['reference']} | Version: {package['version']}",
                    f"Package SHA-256: `{package['sha256']}`",
                    "",
                ]
            )
        remaining = chart.get("remaining_iterations")
        artifacts = str(chart.get("artifacts", "none"))
        lines.extend(
            [
                f"Result: {chart.get('result', 'N/A')} | Status: {chart['status']}",
                f"Attempts: {chart.get('attempts', 'N/A')} | Remaining iterations: {remaining if remaining is not None else 'unknown'}",
                f"Coverage: {chart.get('coverage', 'not exercised')}",
                f"Artifacts: [{artifacts}](<{artifacts}>)" if artifacts != "none" else "Artifacts: none",
                "",
            ]
        )
        if "testing_seconds" in chart:
            lines.extend(
                [
                    f"Chart testing: {float(str(chart['testing_seconds'])):.2f} seconds | "
                    f"Dependency preparation: {float(str(chart.get('dependency_preparation_seconds', 0))):.2f} seconds | "
                    f"Wall clock: {float(str(chart.get('elapsed_seconds', 0))):.2f} seconds",
                    "",
                ]
            )
        filtering = chart.get("filtering")
        if isinstance(filtering, dict) and filtering.get("requested"):
            lines.extend(
                [
                    f"Filtering applied: {filtering.get('applied', False)}",
                    str(filtering.get("reason", "Topology trimming and failure expansion")),
                    "",
                ]
            )
        phases = chart.get("phases", [])
        inventory = chart.get("input_inventory")
        if isinstance(inventory, dict):
            measured = chart.get("field_coverage", {})
            varied = measured.get("varied_count", "not measured") if isinstance(measured, dict) else "not measured"
            lines.extend(
                [
                    f"Identified input fields (lower bound): {inventory.get('lower_bound_fields')} | Varied in render attempts: {varied}",
                    f"Missing values: {len(inventory.get('missing_values', []))} "
                    "| Undocumented template fields: "
                    f"{len(inventory.get('undocumented_template_fields', []))}",
                    f"Unreferenced values: {len(inventory.get('unreferenced_values', []))} ({inventory.get('unreferenced_usage')})",
                    "Field variation does not prove branch or output coverage.",
                    "",
                ]
            )
        dumped = chart.get("minimal_values")
        if isinstance(dumped, dict):
            destination = str(dumped["yaml"])
            lines.extend([f"Minimal values: [{destination}](<{destination}>)", ""])
            if dumped.get("proof"):
                proof = str(dumped["proof"])
                lines.extend([f"Verification record: [{proof}](<{proof}>)", ""])
        if isinstance(phases, list):
            for phase in phases:
                if isinstance(phase, dict):
                    lines.extend(
                        [
                            f"Phase {phase.get('phase')}: {phase.get('status')} | Attempts: {phase.get('attempts', 'unknown')}",
                            "",
                        ]
                    )
        references = sequence(chart.get("error_refs", []))
        if references:
            lines.extend(
                [
                    "Errors: " + ", ".join(f"[{reference}](#{str(reference).lower()})" for reference in references),
                    "",
                ]
            )
        elif chart.get("error"):
            content = display_error(chart["error"])
            fence = "`" * max(3, max(map(len, re.findall(r"`+", content)), default=0) + 1)
            lines.extend([f"{fence}text", content, fence, ""])
        counterexamples = [
            (str(phase.get("phase", "chart")), phase["values"])
            for phase in sequence(phases)
            if isinstance(phase, dict) and isinstance(phase.get("values"), dict)
        ]
        if isinstance(chart.get("values"), dict):
            counterexamples.append(("chart", chart["values"]))
        for phase_name, values in counterexamples:
            content = json.dumps(values, indent=2, ensure_ascii=True)
            fence = "`" * max(3, max(map(len, re.findall(r"`+", content)), default=0) + 1)
            lines.extend([f"Reproducing values ({phase_name}):", "", f"{fence}json", content, fence, ""])
    markdown.write_text(wrap_markdown("\n".join(lines)))
    canvas = Canvas(str(pdf), pagesize=(612, 792))
    canvas.setTitle(str(report.get("title", "Helm chart scan")))
    y = 750
    canvas.setFont("Courier", 8)
    in_code = False
    for line in "\n".join(lines).splitlines():
        if line.startswith("```"):
            in_code = not in_code
            continue
        if not in_code:
            line = re.sub(r"\[([^\]]+)\]\(<\1>\)", r"\1", line)
            line = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", line)
            line = line.replace("**", "").replace("`", "")
        heading = line.startswith("#")
        if heading and y < 120:
            canvas.showPage()
            y = 750
        font = "Helvetica-Bold" if heading else "Courier"
        size = 14 if line.startswith("# ") else 11 if heading else 8
        content = line.lstrip("# ") if heading else line
        for wrapped in textwrap.wrap(content, width=85 if heading else 100) or [""]:
            if y < 42:
                canvas.showPage()
                y = 750
            canvas.setFont(font, size)
            canvas.drawString(36, y, wrapped.encode("latin-1", "backslashreplace").decode("latin-1"))
            y -= size + 4
    canvas.save()
    return markdown, pdf

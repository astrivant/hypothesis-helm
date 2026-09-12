"""
Portable Markdown and paginated PDF summaries for repository scans.
"""

from __future__ import annotations

import json
import re
import textwrap
from pathlib import Path

from reportlab.pdfgen.canvas import Canvas  # type: ignore[import-untyped]


def write_reports(report: dict[str, object], stem: Path) -> tuple[Path, Path]:
    """
    Write both report formats, accepting an explicit stem or either extension.

    Args:
        report (dict[str, object]): Scan summary including chart diagnostics.
        stem (Path): Output stem, Markdown filename, or PDF filename.

    Returns:
        tuple[Path, Path]: Markdown and PDF output paths.
    """
    if stem.suffix.lower() in (".md", ".pdf"):
        stem = stem.with_suffix("")
    markdown, pdf = Path(f"{stem}.md"), Path(f"{stem}.pdf")
    markdown.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {report.get('title', 'Helm chart scan')}",
        "",
        f"Directory: {report['directory']}",
        f"Started (Unix epoch): {report['started_epoch']}",
        f"Elapsed: {float(str(report['elapsed_seconds'])):.2f} seconds",
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
        "## Charts",
        "",
    ]
    summary = report.get("summary", [])
    if isinstance(summary, list):
        lines[2:2] = [str(line) for line in summary] + [""]
    charts = report["charts"]
    assert isinstance(charts, list)
    for chart in charts:
        assert isinstance(chart, dict)
        title = str(chart["chart"]).replace("\n", " ")
        lines.extend([f"### {title}", ""])
        remaining = chart.get("remaining_iterations")
        artifacts = str(chart.get("artifacts", "none"))
        lines.extend(
            [
                f"Result: {chart.get('result', 'N/A')} | Status: {chart['status']}",
                f"Attempts: {chart.get('attempts', 'N/A')} | "
                f"Remaining iterations: {remaining if remaining is not None else 'unknown'}",
                f"Coverage: {chart.get('coverage', 'not exercised')}",
                f"Artifacts: [{artifacts}](<{artifacts}>)"
                if artifacts != "none"
                else "Artifacts: none",
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
        if isinstance(phases, list):
            for phase in phases:
                if isinstance(phase, dict):
                    lines.extend(
                        [
                            f"Phase {phase.get('phase')}: {phase.get('status')} | "
                            f"Attempts: {phase.get('attempts', 'unknown')}",
                            "",
                        ]
                    )
        if chart.get("error"):
            content = str(chart["error"])
            fence = "`" * max(3, max(map(len, re.findall(r"`+", content)), default=0) + 1)
            lines.extend([f"{fence}text", content, fence, ""])
    markdown.write_text("\n".join(lines) + "\n")
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
            canvas.drawString(
                36, y, wrapped.encode("latin-1", "backslashreplace").decode("latin-1")
            )
            y -= size + 4
    canvas.save()
    return markdown, pdf

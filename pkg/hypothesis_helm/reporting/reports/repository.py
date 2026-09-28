"""
Portable Markdown and paginated PDF summaries for repository scans.
"""

from __future__ import annotations

import os
import re
import textwrap
from pathlib import Path
from urllib.parse import quote, unquote

from hypothesis_helm.reporting.console.progress import format_path
from hypothesis_helm.reporting.documentation.contents import heading_inventory, with_contents
from hypothesis_helm.reporting.documentation.markup import inline_code
from hypothesis_helm.reporting.evidence.errors import deduplicate_errors, numbered_diagnostic
from hypothesis_helm.reporting.evidence.provenance import trace_run
from hypothesis_helm.reporting.evidence.reproductions import input_summary
from hypothesis_helm.reporting.reports.audits import write_audit_data
from hypothesis_helm.reporting.reports.figures import study_figures
from hypothesis_helm.reporting.reports.links import LINK, Publication, chart_source_url, commit_url, publish_links, repository_url, web_url
from hypothesis_helm.reporting.reports.overview import summarize, write_overview
from hypothesis_helm.reporting.reports.pca import PCA_LABEL, write_pca
from hypothesis_helm.reporting.reports.pdf import write_pdf
from hypothesis_helm.reporting.reports.plot_reference import with_plot_reference, with_sensitivity_reference
from hypothesis_helm.reporting.reports.references import with_finding_reference
from hypothesis_helm.reporting.reports.topology import write_graph_overview
from hypothesis_helm.schemas.contracts import mapping, sequence

__all__ = ("HELM_DEBUG_HINT", "artifact_link", "chart_heading", "display_error", "wrap_markdown", "write_reports")


HELM_DEBUG_HINT = re.compile(r"(?m)^[ \t]*Use --debug flag to render out invalid YAML[ \t]*\r?$\n?")


def artifact_link(label: str, destination: object, report: Path, *, prefer: tuple[str, ...] = ()) -> str:
    """
    Link artifacts relative to the report location rather than the working directory.

    Args:
        label (str): Short human-readable link text.
        destination (object): Recorded filesystem artifact path or HTTPS URL.
        report (Path): Markdown report destination.
        prefer (tuple[str, ...]): Existing files to prefer inside a local artifact directory, in order.

    Returns:
        str: Portable Markdown link with an escaped relative target.
    """
    url = web_url(destination)
    if url is not None:
        return f"[{label}](<{url}>)"
    path = Path(str(destination))
    # Finalized scan archives already store paths relative to the human report.
    target = os.path.relpath(path, report.parent) if path.is_absolute() or path.exists() else str(path)
    for filename in prefer:
        if (report.parent / target / filename).is_file():
            target = str(Path(target) / filename)
            break
    return f"[{label}](<{quote(target, safe='/._-')}>)"


def _public_artifact(
    label: str,
    destination: object,
    report: Path,
    publication: Publication | None,
    *,
    prefer: tuple[str, ...] = (),
) -> str | None:
    """
    Link explicitly hosted evidence or existing files assigned a public publication destination.

    Args:
        label (str): Visible link text.
        destination (object): Recorded evidence URL or local path.
        report (Path): Report path for resolving local artifacts.
        publication (Publication | None): Explicit public artifact destination.
        prefer (tuple[str, ...]): Evidence filenames to prefer over a containing directory.

    Returns:
        str | None: HTTPS Markdown link, or no link for unpublished or missing local evidence.
    """
    if not destination:
        return None
    link = artifact_link(label, destination, report, prefer=prefer)
    if web_url(destination) is not None:
        return link
    match = LINK.fullmatch(link)
    if publication is not None and match is not None:
        target = match[2] or match[3]
        if (report.parent / unquote(target)).exists():
            return publish_links(link, report, publication)
    return None


def chart_heading(
    chart: dict[str, object],
    source: dict[str, object],
    report: Path,
    *,
    artifact_links: bool = True,
    publication: Publication | None = None,
) -> str:
    """
    Make chart names open their source code, falling back to retained run artifacts.

    Args:
        chart (dict[str, object]): Chart identity and available artifact destinations.
        source (dict[str, object]): Stable repository provenance recorded by the scan.
        report (Path): Markdown report location for relative artifact links.
        artifact_links (bool): Whether the report publishes retained run artifacts.
        publication (Publication | None): Explicit public destination for retained artifacts.

    Returns:
        str: Chart heading with an optional source or artifact link.
    """
    title = str(chart["chart"]).replace("\n", " ")
    destination = chart_source_url(chart, source)
    if destination is None and artifact_links:
        return "### " + (_public_artifact(title, chart.get("artifacts"), report, publication) or title)
    return "### " + (artifact_link(title, destination, report) if destination else title)


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


def _scan_title(report: dict[str, object]) -> str:
    """
    Identify the scanned source consistently in the report title and PDF headers.

    Args:
        report (dict[str, object]): Scan provenance and original target directory.

    Returns:
        str: Scan-results title naming the repository, package source, or local directory.
    """
    source = mapping(report.get("source", {}))
    remote = repository_url(source.get("url")) or web_url(source.get("url"))
    if remote:
        identity = remote.removeprefix("https://").rstrip("/")
        subdirectory = str(source.get("path", ".")).strip("/")
        if subdirectory not in ("", "."):
            identity += "/" + subdirectory
    else:
        identity = str(report["directory"])
    return "Scan results: " + " ".join(identity.split())


def write_reports(
    report: dict[str, object], stem: Path, *, publication: Publication | None = None, artifact_links: bool = True
) -> tuple[Path, Path]:
    """
    Write both report formats, accepting an explicit stem or either extension.

    Args:
        report (dict[str, object]): Scan summary including chart diagnostics.
        stem (Path): Output stem, Markdown filename, or PDF filename.
        publication (Publication | None): Public repository destination for shareable artifact links.
        artifact_links (bool): Link local run evidence; disable for standalone published reports.

    Returns:
        tuple[Path, Path]: Markdown and PDF output paths.
    """
    # Both formats share one grouping and one run identity; formatting must not change the underlying findings.
    deduplicate_errors(report)
    trace_run(report)
    if stem.suffix.lower() in (".md", ".pdf"):
        stem = stem.with_suffix("")
    markdown, pdf = Path(f"{stem}.md"), Path(f"{stem}.pdf")
    markdown.parent.mkdir(parents=True, exist_ok=True)
    overview = summarize(report)
    figure = Path(f"{stem}-overview.png")
    overview_cells = write_overview(overview, figure)
    pca_figure = Path(f"{stem}-pca.png")
    pca_caption = write_pca(report, pca_figure)
    studies = study_figures(report, markdown)
    images: dict[str, Path] = {}
    caption_kinds: dict[str, str] = {}
    caption_references: dict[str, tuple[str, ...]] = {overview.caption: ("Overview matrices",)}
    field_key_caption = "Sensitivity field key"
    settings = mapping(report["settings"])
    title = _scan_title(report)
    lines = [
        f"# {title}",
        "",
        f"Directory: {report['directory']}",
        f"Started (Unix epoch): {report['started_epoch']}",
        f"Elapsed (wall clock): {float(str(report['elapsed_seconds'])):.2f} seconds",
        f"Charts discovered: {report['charts_discovered']}",
        f"Manifest test attempts: {sum(int(str(mapping(chart).get('attempts') or 0)) for chart in sequence(report['charts']))}",
        f"Scan status: {report.get('scan_status', 'not recorded')}",
        f"Discovery complete: {report.get('discovery_complete', 'not recorded')}",
        f"Unstarted charts: {report.get('unstarted_charts', 'not recorded')}",
        "",
        "Results record outcomes for the tested sample and selected checks.",
        "Baseline-only, skipped, blocked, and incomplete charts retain their respective statuses.",
        "",
        "## Status counts",
        "",
        "; ".join(f"{count} {status}" for status, count in mapping(report["counts"]).items()) + ".",
        "",
        "## Settings",
        "",
        f"Filtering: {settings.get('filter', 'not recorded')} | Seed: {settings.get('seed', 'not recorded')} | "
        f"Traversal: {settings.get('traversal_strategy', 'not recorded')}",
        *(
            [f"Maximum dependency depth: {settings['max_depth'] if settings['max_depth'] is not None else 'inf'}"]
            if "max_depth" in settings
            else []
        ),
        f"Chart timeout: {settings.get('chart_timeout_seconds', 'not recorded')} seconds | "
        f"Workers: {settings.get('workers', settings.get('jobs', 'not recorded'))}",
        "Complete settings are retained in the JSON report.",
        "",
    ]
    if "testing_seconds" in report:
        lines[5:5] = [
            f"Chart testing: {float(str(report['testing_seconds'])):.2f} seconds",
            f"Dependency preparation: {float(str(report['dependency_preparation_seconds'])):.2f} seconds (excluded from testing budgets)",
        ]
    timing_note = " (estimated from recorded timing)" if str(report["finish_time_source"]).startswith("derived") else ""
    cover_details = [
        ("Started (UTC)", str(report["started_at"]).replace("T", " ").removesuffix("+00:00")),
        ("Finished (UTC)" + timing_note, str(report["finished_at"]).replace("T", " ").removesuffix("+00:00")),
    ]
    scan_source = mapping(report.get("source", {}))
    revision = scan_source.get("revision")
    if scan_source.get("kind") != "helm" and isinstance(revision, str) and revision.strip():
        revision_url = commit_url(scan_source)
        cover_details.append(("Source commit", artifact_link(revision, revision_url, markdown) if revision_url else revision))
    # Read saved execution metadata only: the machine publishing a PDF may have newer dependencies installed.
    execution = mapping(report.get("execution", {}))
    versions = mapping(execution.get("versions", {}))
    version_text = (
        f"Hypothesis {versions.get('hypothesis') or 'not recorded'}; hypothesis-helm {versions.get('hypothesis-helm') or 'not recorded'}"
    )
    cover_details.append(("Versions", version_text))
    working_directory = execution.get("working_directory")
    if working_directory:
        cover_details.append(("Working directory", str(working_directory)))
    command = str(execution.get("command") or "Not recorded for this run")
    cover_details.append(("Scan command", command))
    lines[4:4] = [
        f"Started (UTC): {report['started_at']}",
        f"Finished (UTC): {report['finished_at']}{timing_note}",
        f"Run fingerprint (SHA-256): `{report['run_hash']}`",
        f"Versions: {version_text}",
    ]
    if working_directory:
        lines.extend([f"Command working directory: `{working_directory}`", ""])
    # A fence longer than any literal backticks keeps unusual path names copyable without parsing them as Markdown.
    if execution.get("command"):
        fence = "`" * max(3, 1 + max((len(match[0]) for match in re.finditer(r"`+", command)), default=0))
        lines.extend(["Scan command:", "", fence + "bash", command, fence, ""])
    else:
        lines.extend([f"Scan command: {command}", ""])
    summary = report.get("summary", [])
    if isinstance(summary, list):
        lines[2:2] = [str(line) for line in summary] + [""]
    if "input_policy" in report:
        lines.extend(
            [
                "Generated values use the configured input domains and any supported destination constraints. "
                "Coverage excludes inputs outside these domains; supplied defaults are tested unchanged. "
                "The JSON report records constraints and unresolved mappings.",
                "",
            ]
        )
    if report.get("ignored_rules"):
        lines.extend(["Disabled checks: " + ", ".join(str(code) for code in sequence(report["ignored_rules"])), ""])
    errors = sequence(report["error_groups"])
    if errors:
        counts = mapping(report["error_summary"])
        lines.extend(
            [
                "## Errors",
                "",
                f"{counts['unique_errors']} distinct diagnostics across "
                f"{counts['occurrences']} occurrences; {counts['duplicates']} repeats grouped.",
                "Diagnostics and their triggering inputs are grouped under each chart below.",
                "Up to two examples per diagnostic, with six fields each. Long values are shortened; YAML parser details stay in run data.",
                "Full inputs, diagnostics, and remaining cases are retained in local run data.",
                "Selected fields identify the inputs varied by the test. Causal attribution requires further investigation.",
                "",
            ]
        )
    # Keep the overview up front; aggregate analyses belong after chart results.
    front_matter = [
        "## Overview",
        "",
        "!" + artifact_link("Chart severity and scan-time matrices", figure, markdown),
        "",
        overview.caption,
        "",
    ]
    appendix_figures: list[str] = []
    if studies.metrics:
        label = "Published compiler graph invariants"
        graph_image = Path(f"{stem}-topology.png")
        graph_caption = write_graph_overview(studies.metrics, graph_image, len(sequence(report["charts"])))
        images[label] = graph_image
        caption_kinds[label] = "Graph structure metrics"
        caption_references[graph_caption] = ("Graph structure metrics",)
        appendix_figures.extend(
            [
                "## Appendix: graph structure",
                "",
                "!" + artifact_link(label, graph_image, markdown),
                "",
                graph_caption,
                "",
            ]
        )
    if pca_caption is not None:
        images[PCA_LABEL] = pca_figure
        caption_kinds[PCA_LABEL] = "Output-space PCA"
        caption_references[pca_caption] = ("Output-space PCA",)
        appendix_figures.extend(
            ["## Appendix: output space", "", "!" + artifact_link(PCA_LABEL, pca_figure, markdown), "", pca_caption, ""]
        )
    lines.extend(["## Charts", ""])
    charts = report["charts"]
    assert isinstance(charts, list)
    for index, chart in enumerate(charts, 1):
        assert isinstance(chart, dict)
        has_failures = any(
            mapping(occurrence)["chart"] == chart["chart"] for group in errors for occurrence in sequence(mapping(group)["occurrences"])
        )
        heading = chart_heading(chart, mapping(report.get("source", {})), markdown, artifact_links=artifact_links, publication=publication)
        lines.extend([heading, ""])
        if chart["chart"] in studies.charts:
            topology, sensitivity = studies.charts[str(chart["chart"])]
            cells = []
            for kind, image_path in (("Topology", topology), ("Sensitivity", sensitivity)):
                label = f"{kind}: {chart['chart']}"
                if image_path is None:
                    message = studies.sensitivity_messages.get(str(chart["chart"])) if kind == "Sensitivity" else None
                    cells.append(message or f"{kind} measurements unavailable.")
                else:
                    images[label] = image_path
                    caption_kinds[label] = "Chart topology" if kind == "Topology" else "Field interactions"
                    cells.append("!" + artifact_link(label, image_path, markdown))
            lines.extend(
                [
                    "| Chart topology | Mutation sensitivity |",
                    "| --- | --- |",
                    f"| {cells[0]} | {cells[1]} |",
                    "",
                ]
                if topology or sensitivity
                else [cells[0], "", cells[1], ""]
            )
            if studies.sensitivity_fields.get(str(chart["chart"])):
                lines.extend([field_key_caption, ""])
        lines.extend([f"Overview cell: [{index:02d}](#overview)", ""])
        package = chart.get("package")
        if isinstance(package, dict):
            lines.extend(
                [
                    f"Package: {package['reference']} | Version: {package['version']}",
                    f"Package SHA-256: `{package['sha256']}`",
                    "",
                ]
            )
        lines.extend(
            [
                f"Status: {chart['status']} | Attempts: {chart.get('attempts', 'N/A')}",
                "",
            ]
        )
        if not has_failures and chart.get("attempts"):
            message = "No failing test cases were recorded."
            if chart["status"] == "time-limit":
                message += " The time limit was reached before testing finished."
            elif chart["status"] == "interrupted":
                message += " Testing was interrupted before it finished."
            lines.extend([message, ""])
        if chart.get("error") and not numbered_diagnostic(chart):
            lines.extend(["Testing limitation: " + " ".join(display_error(chart["error"]).split()), ""])
        coverage_fallback = mapping(chart.get("coverage_fallback", {}))
        if coverage_fallback and not has_failures:
            lines.extend(["Coverage: sampled values paths; full interaction coverage was not established.", ""])
        elif coverage_fallback:
            strength = coverage_fallback.get("requested_permutations")
            requested = f"Requested {strength}-way interaction coverage" if strength is not None else "Finite interaction coverage"
            lines.extend(
                [
                    f"Coverage: generated path tests. {requested} was unavailable: {coverage_fallback['reason']}. "
                    "The sampled paths do not establish N-way coverage.",
                    "",
                ]
            )
            unavailable_options = sequence(coverage_fallback.get("unavailable_options", []))
            if unavailable_options:
                lines.extend(["Unavailable finite-plan options: " + ", ".join(f"`{option}`" for option in unavailable_options) + ".", ""])
        fallback = mapping(chart.get("traversal_fallback", {}))
        if fallback:
            lines.extend(
                [
                    f"Traversal: `{fallback['effective']}` (requested `{fallback['requested']}`). {fallback['reason']}.",
                    "",
                ]
            )
        audit = mapping(chart.get("audit", {}))
        findings = [mapping(item) for item in [*sequence(audit.get("findings", [])), *sequence(audit.get("unresolved", []))]]
        if findings:
            audit_data = write_audit_data(report, chart, stem, index)
            audit_link = artifact_link("JSON", audit_data, markdown)
            lines.extend([f"Audit findings: {len(findings)}. Full paths and template references: {audit_link}.", ""])
            for observed_finding in findings[:6] if has_failures else []:
                path = tuple(str(part) for part in sequence(observed_finding.get("path", [])))
                lines.append(
                    f"- `{observed_finding['code']}` at `{format_path(path)}`: "
                    f"{mapping(observed_finding.get('finding', {})).get('title', '')}"
                    f"{(' (' + str(observed_finding['severity']) + ')') if 'severity' in observed_finding else ''}"
                )
            if has_failures and len(findings) > 6:
                lines.append(f"- {len(findings) - 6} additional audit findings in {audit_link}.")
            lines.append("")
        sampling = chart.get("sampling")
        if isinstance(sampling, dict) and sampling.get("applied"):
            lines.extend(
                [
                    f"Random sample: {sampling['retained']} / {sampling['eligible']} eligible cases retained; "
                    f"{sampling['omitted']} omitted. Minimum: {sampling['minimum']}. Seed: {sampling['seed']}. "
                    "Bug recall depends on the defect-triggering inputs retained.",
                    "",
                ]
            )
        rejections = chart.get("configuration_rejections")
        if isinstance(rejections, dict) and (rejections.get("rejected_candidates") or rejections.get("schema_conflicts")):
            lines.extend(
                [
                    f"Configuration rejections: {rejections['filtered_candidates']} excluded; "
                    f"{rejections['adjusted_candidates']} adjusted and tested; "
                    f"{rejections['verification_renders']} Helm verification renders (separate from manifest-test attempts).",
                    "",
                ]
            )
            requirements = sequence(rejections.get("requirements", []))
            if rejections.get("schema_conflicts"):
                lines.extend(["The template rejected inputs admitted by the declared values schema; these remain reported failures.", ""])
            for requirement in requirements[:3]:
                record = mapping(requirement)
                message = " ".join(str(record["requirement"]).split())
                lines.extend([f"Requirement ({record['source']}:{record['line']}): {message[:500]}", ""])
                for input_path, choices in mapping(record.get("enums", {})).items():
                    values = sequence(choices)
                    shown = ", ".join(f"`{value}`" for value in values[:12])
                    extra = f" (+{len(values) - 12} more in artifacts)" if len(values) > 12 else ""
                    lines.extend([f"Template choices for `{input_path}` on this branch: {shown}{extra}.", ""])
                lines.extend(input_summary({"recorded": True, "paths": record["inputs"]}))
                lines.append("")
            if len(requirements) > 3:
                lines.extend([f"{len(requirements) - 3} more requirements are retained in chart artifacts.", ""])
        dumped = chart.get("minimal_values")
        if isinstance(dumped, dict) and artifact_links:
            destination = str(dumped["yaml"])
            lines.extend([artifact_link("Minimal values", destination, markdown), ""])
            if dumped.get("proof"):
                proof = str(dumped["proof"])
                lines.extend([artifact_link("Verification record", proof, markdown), ""])
        for entry in errors:
            group = mapping(entry)
            occurrences = [mapping(item) for item in sequence(group["occurrences"]) if mapping(item)["chart"] == chart["chart"]]
            if not occurrences:
                continue
            lines.extend([f"#### {group['id']}" + (f" ({group['code']})" if group.get("code") else ""), ""])
            finding = group.get("finding")
            if isinstance(finding, dict):
                lines.extend(
                    [
                        f"**{finding['title']}** ({finding['category']} / {finding['kind']}). "
                        f"{('Severity: **' + str(finding['severity']) + '**. ') if 'severity' in finding else ''}"
                        f"{finding['remediation']}",
                        "",
                    ]
                )
            source = group.get("source")
            if isinstance(source, dict):
                lines.extend([f"Source: {source['name']} {source['version']} / {source['template']}", ""])
            # Parser exceptions repeat source excerpts and library advice. Their
            # finding title identifies the failure; retain the full diagnostic
            # in run data without printing it above the reproducing inputs.
            if group.get("code") != "HH1101":
                content = " ".join(display_error(group["error"]).split())
                if len(content) > 500:
                    content = "[Diagnostic shortened; full text in artifacts] ... " + content[-450:]
                fence = "`" * max(3, max(map(len, re.findall(r"`+", content)), default=0) + 1)
                lines.extend(
                    [fence + "text", *textwrap.wrap(content, width=140, break_long_words=False, break_on_hyphens=False), fence, ""]
                )
            for occurrence in occurrences[:2]:
                phase = str(occurrence["phase"])
                phase_label = inline_code(phase) if phase.startswith("$") else phase
                lines.extend([f"Status: {occurrence['status']} | Phase: {phase_label}", ""])
                lines.extend(input_summary(mapping(occurrence["input"])))
                lines.append("")
                occurrence_artifacts = occurrence.get("artifacts")
                # Local file URLs are blocked by many PDF viewers and disappear when a report is shared.
                if artifact_links:
                    link = _public_artifact(
                        "Full input and diagnostic",
                        occurrence_artifacts,
                        markdown,
                        publication,
                        prefer=("report.json", "observed-failure.json"),
                    )
                    if link:
                        lines.extend([link, ""])
            if len(occurrences) > 2:
                lines.extend([f"{len(occurrences) - 2} additional occurrences are retained in the JSON report and chart artifacts.", ""])
        artifacts = chart.get("artifacts")
        suppressions = chart.get("suppression_export")
        if artifact_links and isinstance(suppressions, dict) and suppressions.get("yaml"):
            lines.extend([artifact_link("Review suggested suppressions (not applied)", suppressions["yaml"], markdown), ""])
        if artifact_links:
            link = _public_artifact("Chart artifacts", artifacts, markdown, publication)
            if link:
                lines.extend([link, ""])
    lines.extend(appendix_figures)
    lines[2:2] = [*front_matter, "## Scan summary", ""]
    details: dict[str, list[str]] = {}
    if pca_caption is not None:
        in_charts = False
        key = ["| Color number | Chart | Measured / retained reference outputs |", "| :---: | :--- | ---: |"]
        positions = []
        for _, level, label, anchor in heading_inventory("\n".join(lines)):
            if level <= 2:
                in_charts = level == 2 and label == "Charts"
            elif in_charts and level == 3:
                positions.append((label, anchor))
        for index, (chart, (label, anchor)) in enumerate(zip(charts, positions, strict=True), 1):
            reference = mapping(chart.get("output_space", {}))
            observations = [mapping(row) for row in sequence(reference.get("observations", []))]
            retained = sum(row.get("retained") is True for row in observations)
            count = f"{len(observations)} / {retained}" if observations else "Unavailable"
            if any(row.get("retained") is None for row in observations):
                count = f"{len(observations)} / selection unavailable"
            key.append(f"| {index:02d} | [{label}](#{anchor}) | {count} |")
        details["Output-space PCA"] = [*key, ""]
    content, plot_targets = with_plot_reference(
        "\n".join(lines), {kind for kinds in caption_references.values() for kind in kinds} | set(caption_kinds.values()), details
    )
    content, field_targets = with_sensitivity_reference(content, studies.sensitivity_fields)
    lines = content.splitlines()
    headings = {index: (level, label) for index, level, label, _ in heading_inventory(content)}
    active_chart = ""
    for index, line in enumerate(lines):
        if index in headings:
            level, label = headings[index]
            active_chart = label if level == 3 else ""
        if line in caption_references:
            links = ", ".join(f"[{kind}](#{plot_targets[kind]})" for kind in caption_references[line])
            lines[index] += f" Plot guide: {links}."
        if line == field_key_caption and active_chart in field_targets:
            lines[index] = f"[Sensitivity field key](#{field_targets[active_chart]})."
    lines = with_finding_reference("\n".join(lines)).splitlines()
    if publication is not None:
        fence = ""
        for index, line in enumerate(lines):
            marker = re.match(r"^(`{3,})", line)
            if marker and not fence:
                fence = marker[1]
            elif fence and re.fullmatch(re.escape(fence) + r"`*\s*", line):
                fence = ""
            elif not fence:
                lines[index] = publish_links(line, markdown, publication)
    markdown.write_text(with_contents(wrap_markdown("\n".join(lines)), max_depth=3))
    write_pdf(
        "\n".join(lines),
        pdf,
        title=title,
        overview=figure,
        overview_cells=overview_cells,
        images=images,
        caption_targets={
            **{label: plot_targets[kind] for label, kind in caption_kinds.items()},
            **{f"Sensitivity: {chart}": target for chart, target in field_targets.items()},
        },
        cover_details=tuple(cover_details),
        cover_source_url=repository_url(scan_source.get("url")) or web_url(scan_source.get("url")),
    )
    return markdown, pdf

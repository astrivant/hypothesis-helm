"""
Define report plots beside the findings they help interpret.
"""

from hypothesis_helm.reporting.documentation.contents import heading_inventory

__all__ = ("PLOT_APPENDIX_TITLE", "SENSITIVITY_APPENDIX_TITLE", "with_plot_reference", "with_sensitivity_reference")

PLOT_APPENDIX_TITLE = "Appendix: plot guide"
SENSITIVITY_APPENDIX_TITLE = "Appendix: sensitivity field keys"
DEFINITIONS = {
    "Overview matrices": (
        "Each numbered cell links to one chart. The left matrix shows findings or test status; the right shows recorded testing time. "
        "A dash means no timing was recorded. "
        "Incomplete and untested charts have not passed."
    ),
    "Chart topology": (
        "Vertices represent values paths, branch conditions, templates and manifest fields. Connections show the relationships "
        "the compiler could establish between them. Rendered fields, when available, describe the measured baseline. "
        "An absent connection does not prove independence when analysis is incomplete."
    ),
    "Field interactions": (
        "Both axes use the field numbers in the chart's sensitivity appendix entry, linked from its plot caption. "
        "Each measured cell compares changing two fields together "
        "with changing each separately from the same baseline. Manifests are encoded as path-and-value indicators, including empty "
        "containers. The color measures the sum of absolute differences in f(ij) - f(i) - f(j) + f(0). "
        "A larger value means a stronger interaction for those particular changes; zero means no interaction was measured. "
        "Blank cells are unmeasured, not zero. These measurements describe sampled changes, not all possible field values or bug counts."
    ),
    "Graph structure metrics": (
        "Each point represents one chart with published graph measurements. The upper panel compares vertices with connections. "
        "The lower counts independent loops after ignoring connection direction: connections minus vertices plus disconnected groups. "
        "Parallel connections count separately. The axes compress large values while retaining zero. "
        "These counts describe graph structure, not execution loops, runtime or the number of defects."
    ),
    "Output-space PCA": (
        "The panels pool bounded reference measurements from the charts in this report. Colors identify chart numbers in the key below. "
        "Both panels use one PCA fit and identical axis limits; axis percentages show variance retained in the encoded features. "
        "Resource identities, structure and typed field values enter 256 signed hash bins; numeric values use a signed log transform, "
        "and bins are standardized before PCA. Hash collisions and projection can overlap distinct manifests. "
        "One observation represents one measured configuration, including repeated outputs. "
        "References use schema-valid Boolean flips, adjacent integers and joint changes from the supplied baseline; they do not enumerate "
        "the full input or output space. Path scans use recorded retained properties. Finite filtering selectors are replayed on the "
        "bounded reference, so their sampling floors apply to that reference size. Runtime rejection, equivalence reuse and failure "
        "expansion are not reconstructed. Failed renders have no coordinate. "
        "Missing or unfinished measurements do not imply zero variation. "
        "With no filtering, the two panels show the same reference sample."
    ),
}


def with_plot_reference(content: str, kinds: set[str], details: dict[str, list[str]] | None = None) -> tuple[str, dict[str, str]]:
    """
    Append only the definitions used by this report and resolve their actual anchors.

    Args:
        content (str): Report body before its appendices are added.
        kinds (set[str]): Plot definitions referenced by the report captions.
        details (dict[str, list[str]] | None): Report-specific keys appended to their plot definition.

    Returns:
        tuple[str, dict[str, str]]: Expanded report and collision-safe destinations indexed by plot kind.
    """
    if not kinds:
        return content, {}
    lines = content.rstrip().splitlines()
    start = len(lines)
    lines.extend(["", f"## {PLOT_APPENDIX_TITLE}", ""])
    for kind, explanation in DEFINITIONS.items():
        if kind in kinds:
            lines.extend([f"### {kind}", "", explanation, ""])
            lines.extend((details or {}).get(kind, []))
    content = "\n".join(lines)
    # A chart may share a name with a definition, so use the allocated anchor.
    targets = {label: anchor for index, level, label, anchor in heading_inventory(content) if index >= start and level == 3}
    return content, targets


def with_sensitivity_reference(content: str, fields: dict[str, tuple[str, ...]]) -> tuple[str, dict[str, str]]:
    """
    Group numbered sensitivity paths by chart in a separate appendix.

    Args:
        content (str): Report body and any preceding appendices.
        fields (dict[str, tuple[str, ...]]): Exact ordered paths read from each chart's plotted image.

    Returns:
        tuple[str, dict[str, str]]: Expanded report and chart-specific appendix destinations.
    """
    available = {chart: paths for chart, paths in fields.items() if paths}
    if not available:
        return content, {}
    chart_targets = {}
    in_charts = False
    for _, level, label, anchor in heading_inventory(content):
        if level <= 2:
            in_charts = level == 2 and label == "Charts"
        elif in_charts and level == 3:
            chart_targets[label] = anchor
    lines = content.rstrip().splitlines()
    start = len(lines)
    lines.extend(["", f"## {SENSITIVITY_APPENDIX_TITLE}", "", "Both heatmap axes use the same field numbers for each chart.", ""])
    for chart, paths in available.items():
        lines.extend([f"### {chart}", ""])
        lines.extend(f"- **{number}**: `{path}`" for number, path in enumerate(paths, 1))
        lines.append("")
        if chart in chart_targets:
            lines.extend([f"[Back to chart](#{chart_targets[chart]})", ""])
    content = "\n".join(lines)
    # Appendix chart headings repeat the body headings; allocate distinct
    # destinations using the same inventory as Markdown and PDF navigation.
    targets = {label: anchor for index, level, label, anchor in heading_inventory(content) if index >= start and level == 3}
    return content, targets

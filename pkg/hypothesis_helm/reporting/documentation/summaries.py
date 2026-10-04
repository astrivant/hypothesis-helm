"""
Refresh marked documentation summaries from recorded scan measurements.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from hypothesis_helm.reporting.reports.links import commit_url
from hypothesis_helm.schemas.contracts import mapping, sequence

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ("replace_summary", "repository_summary")


def replace_summary(text: str, name: str, replacement: str) -> str:
    """
    Replace one generated block while preserving surrounding editorial text.

    Args:
        text (str): Existing document.
        name (str): Generated block identifier.
        replacement (str): Newly measured summary.

    Returns:
        str: Document with only the selected block replaced, retaining commented-out summaries.

    Raises:
        ValueError: Summary markers are missing, duplicated or reversed.
    """
    start = f"<!-- refresh:{name}:start -->"
    end = f"<!-- refresh:{name}:end -->"
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError(f"Expected exactly one pair of {name} summary markers")
    before, rest = text.split(start)
    if end not in rest:
        raise ValueError(f"Reversed {name} summary markers")
    previous, after = rest.split(end)
    # Keep unpublished case studies hidden until their surrounding comments are removed.
    if previous.strip().startswith("<!--") and previous.strip().endswith("-->"):
        replacement = f"<!--\n{replacement.strip()}\n-->"
    return f"{before}{start}\n{replacement.strip()}\n{end}{after}"


def repository_summary(report: dict[str, object], title: str, stem: Path) -> str:
    """
    Describe a completed scan using its recorded counts, settings and source revision.

    Args:
        report (dict[str, object]): Verified repository scan or aggregate report.
        title (str): Reader-facing repository name.
        stem (Path): Published report path without an extension, relative to the root README.

    Returns:
        str: Markdown summary linking the measured source commit and final report formats.
    """
    charts = sequence(report["charts"])
    settings = mapping(report["settings"])
    attempts = sum(int(str(mapping(chart).get("attempts") or 0)) for chart in charts)
    policy = "`--filter-adaptive`" if settings.get("filter_adaptive") else "`--filter`" if settings["filter"] else "no filtering"
    worker_count = settings["workers"] if "workers" in settings else settings["jobs"]
    workers = f"**{worker_count} path workers per chart**"
    if "shards" in settings:
        workers = f"**{settings['shards']} shards** and **{worker_count} path workers per shard**"
    timeout = float(str(settings["chart_timeout_seconds"]))
    budget = f"a **{timeout / 60:g}-minute budget per chart**" if timeout else "no per-chart time limit"
    source = mapping(report.get("source", {}))
    revision_url = commit_url(source)
    revision = f"Source commit: [`{source['revision']}`]({revision_url}).\n\n" if revision_url else ""
    return (
        f"We scanned **{len(charts):,} {title} {'chart' if len(charts) == 1 else 'charts'}**, "
        f"recording **{attempts:,} test attempts**\n"
        f"with {policy}, {workers}, and {budget}.\n"
        "The reports distinguish test failures, blocked checks and incomplete coverage; chart bugs require triage.\n\n"
        f"{revision}"
        f"Read the [scan results]({stem.as_posix()}.md), download the\n"
        f"[combined PDF]({stem.as_posix()}.pdf)."
    )

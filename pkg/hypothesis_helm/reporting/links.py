"""
Resolve published report links and render linked prose in PDF paragraphs.
"""

import re
from collections.abc import Iterator
from html import escape
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from attrs import frozen

LINK = re.compile(r"\[([^\]]+)\]\((?:<([^>]+)>|([^\s)]+))\)")
CODE = re.compile(r"(`+)(.*?)\1(?!`)")


def link_matches(line: str) -> Iterator[re.Match[str]]:
    """
    Find links outside inline code, preserving literal failing input values.

    Args:
        line (str): Markdown prose containing optional inline code.

    Yields:
        re.Match[str]: Link syntax occurring outside code spans.
    """
    spans = [match.span() for match in CODE.finditer(line)]
    for match in LINK.finditer(line):
        if not any(start <= match.start() < end for start, end in spans):
            yield match


@frozen
class Publication:
    """
    Locate report artifacts in a publicly browsable GitHub repository.

    Attributes:
        root (Path): Local checkout containing every published artifact.
        repository (str): HTTPS GitHub repository URL.
        revision (str): Branch, tag, or commit that will contain the published files.
    """

    root: Path
    repository: str
    revision: str

    def url(self, target: str, report: Path) -> str:
        """
        Convert a report-relative artifact target into an absolute public URL.

        Args:
            target (str): Markdown link destination.
            report (Path): Markdown file from which relative links are resolved.

        Returns:
            str: Existing HTTPS destination or a GitHub file/directory URL.

        Raises:
            ValueError: An artifact escapes the checkout or uses a nonpublic URL scheme.
        """
        parsed = urlsplit(target)
        if parsed.scheme == "https":
            return target
        if parsed.scheme or parsed.netloc:
            raise ValueError(f"Published reports require HTTPS links: {target}")
        path = (report.parent / unquote(parsed.path)).resolve() if parsed.path else report.resolve()
        relative = path.relative_to(self.root.resolve())
        kind = "tree" if path.is_dir() else "blob"
        url = f"{self.repository.rstrip('/')}/{kind}/{quote(self.revision, safe='')}/{quote(relative.as_posix(), safe='/')}"
        return url + (f"#{parsed.fragment}" if parsed.fragment else "")


def publish_links(line: str, report: Path, publication: Publication) -> str:
    """
    Rewrite every Markdown link in a prose line for public consumption.

    Args:
        line (str): Report prose outside code fences.
        report (Path): Markdown output location.
        publication (Publication): Public repository destination.

    Returns:
        str: Prose retaining labels and using absolute HTTPS targets.
    """
    for match in reversed(list(link_matches(line))):
        replacement = f"[{match[1]}](<{publication.url(match[2] or match[3], report)}>)"
        line = line[: match.start()] + replacement + line[match.end() :]
    return line


def linked_prose(line: str) -> str:
    """
    Convert Markdown links to visibly underlined, clickable ReportLab paragraph markup.

    Args:
        line (str): Prose that may contain multiple inline links.

    Returns:
        str: XML-escaped paragraph content with blue underlined links.
    """
    parts = []
    offset = 0
    for match in link_matches(line):
        parts.append(escape(line[offset : match.start()]))
        target = escape(match[2] or match[3], quote=True)
        parts.append(f'<link href="{target}" color="#1459a6"><u>{escape(match[1])}</u></link>')
        offset = match.end()
    parts.append(escape(line[offset:]))
    return "".join(parts)

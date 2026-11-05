"""
Publish finished study documents and figures while retaining run data in the cache.
"""

import hashlib
import os
import re
import shutil
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import unquote, urlsplit

from hypothesis_helm.reporting.reports.links import link_matches

__all__ = ("FINAL_SUFFIXES", "STUDIES", "WORK_DIRECTORIES", "document_links", "final_files", "publish_study", "verify_study")


STUDIES = Path("studies")
FINAL_SUFFIXES = frozenset({".md", ".pdf", ".png", ".svg"})
WORK_DIRECTORIES = frozenset({"runs", "cases", "reports", "logs", "helm", "frozen-source", "__pycache__"})


def final_files(directory: Path) -> Iterator[Path]:
    """
    Visit finished documents and plots without descending into run or chart workspaces.

    Args:
        directory (Path): One study's output directory.

    Yields:
        Path: Final documents and images; measurements, fixtures and worker state are excluded.
    """
    for parent, directories, filenames in os.walk(directory):
        base = Path(parent)
        if "Chart.yaml" in filenames:
            directories.clear()
            continue
        directories[:] = sorted(name for name in directories if name not in WORK_DIRECTORIES and not name.startswith("."))
        for name in sorted(filenames):
            path = base / name
            if path.suffix.lower() in FINAL_SUFFIXES and not path.is_symlink():
                yield path


def document_links(content: str, original: Path, destination: Path) -> str:
    """
    Relocate study links and describe private run data without publishing cache URLs.

    Args:
        content (str): Study Markdown before publication.
        original (Path): Previous published location used to resolve relative links.
        destination (Path): New published document location.

    Returns:
        str: Markdown linking final results and documentation, with raw artifacts labelled local.
    """
    project = Path.cwd().resolve()
    legacy = project / "studies"
    published = project / STUDIES
    lines = []
    fence = ""
    for line in content.splitlines():
        marker = line.lstrip()
        if marker.startswith(("```", "~~~")):
            fence = "" if fence else marker[:3]
        if not fence and not marker.startswith(("```", "~~~")):
            for match in reversed(list(link_matches(line))):
                target = match[2] or match[3]
                parsed = urlsplit(target)
                if parsed.scheme or parsed.netloc or not parsed.path:
                    continue
                path = (original.parent / unquote(parsed.path)).resolve()
                if path.is_relative_to(legacy):
                    path = published / path.relative_to(legacy)
                study_artifact = path.is_relative_to(published)
                private = (
                    path.is_relative_to(project / ".cache") or any(part.endswith("-runs") for part in path.relative_to(project).parts)
                    if path.is_relative_to(project)
                    else False
                )
                if (
                    private
                    or study_artifact
                    and (
                        path.suffix.lower() not in FINAL_SUFFIXES
                        or any(part in WORK_DIRECTORIES for part in path.relative_to(published).parts)
                    )
                ):
                    replacement = f"{match[1]} (local run data)"
                else:
                    relative = os.path.relpath(path, destination.parent.resolve())
                    fragment = f"#{parsed.fragment}" if parsed.fragment else ""
                    replacement = match[0] if relative + fragment == target else f"[{match[1]}](<{relative}{fragment}>)"
                line = line[: match.start()] + replacement + line[match.end() :]
            # Image links and escaped superscript labels can wrap a link parsed above.
            for match in reversed(list(re.finditer(r"\]\((?:<([^>]+)>|([^\s)]+))\)", line))):
                target = match[1] or match[2]
                parsed = urlsplit(target)
                if parsed.scheme or parsed.netloc or not parsed.path:
                    continue
                path = (original.parent / unquote(parsed.path)).resolve()
                if path.is_relative_to(legacy):
                    relative = os.path.relpath(published / path.relative_to(legacy), destination.parent.resolve())
                    fragment = f"#{parsed.fragment}" if parsed.fragment else ""
                    line = line[: match.start()] + f"](<{relative}{fragment}>)" + line[match.end() :]
        lines.append(line)
    return "\n".join(lines) + "\n"


def verify_study(directory: Path, *, require_readme: bool = True) -> None:
    """
    Check study guides and figure pairs before expensive downstream work or publication.

    Args:
        directory (Path): Completed study output, excluding raw workspaces and charts.
        require_readme (bool): Require the guide unless a later refresh recipe produces it.

    Returns:
        None: Every vector figure has a reader question and a matching raster image.

    Raises:
        ValueError: One or more publication artifacts are missing or incomplete.
    """
    problems = []
    if require_readme and not (directory / "README.md").is_file():
        problems.append("missing README.md")
    for figure in final_files(directory):
        if figure.suffix.lower() != ".svg":
            continue
        if 'id="plot-question"' not in figure.read_text():
            problems.append(f"{figure.relative_to(directory)}: missing reader question")
        if not figure.with_suffix(".png").is_file():
            problems.append(f"{figure.relative_to(directory)}: missing PNG")
    if problems:
        raise ValueError(f"Incomplete study publication in {directory}:\n" + "\n".join(problems))


def publish_study(source: Path, destination: Path) -> dict[str, str]:
    """
    Replace one study's published files with its finished documents and figures.

    Args:
        source (Path): Cached run containing raw measurements and finished plots.
        destination (Path): Dedicated final study directory under studies.

    Returns:
        dict[str, str]: SHA-256 checksums of the published files, keyed by destination path.
    """
    sources = tuple(final_files(source))
    if not sources:
        raise ValueError(f"No final documents or plots to publish in {source}")
    if source.resolve() == destination.resolve() or source.resolve().is_relative_to(destination.resolve()):
        raise ValueError("Study measurements must be outside the final publication directory")
    verify_study(source)
    # Only final documents and figures cross this boundary; raw data and worker state remain in the cache.
    expected = {path.relative_to(source) for path in sources}
    checksums = {}
    for path in sources:
        relative = path.relative_to(source)
        output = destination / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() == ".md":
            original = Path("studies") / destination.name / relative
            output.write_text(document_links(path.read_text(), original, output))
        else:
            shutil.copy2(path, output)
        checksums[str(output)] = hashlib.sha256(output.read_bytes()).hexdigest()
    # Only publication-owned files are replaced. Raw run evidence remains at source.
    for path in tuple(final_files(destination)):
        if path.relative_to(destination) not in expected:
            path.unlink()
    return checksums

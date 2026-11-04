"""
Publish finished study documents and figures while retaining run data in the cache.
"""

import hashlib
import os
import re
import shutil
from collections.abc import Iterator, Sequence
from pathlib import Path
from urllib.parse import unquote, urlsplit

from attrs import asdict
from hypothesis_helm.compiler.backends.scheduler import BackendOptions
from hypothesis_helm.reporting.reports.links import CODE, link_matches
from hypothesis_helm.schemas.contracts import mapping, sequence

from hypothesis_helm_benchmarking.catalog import CATALOG, publication_path
from hypothesis_helm_benchmarking.execution.backends import read_evidence

__all__ = (
    "FINAL_SUFFIXES",
    "STUDIES",
    "WORK_DIRECTORIES",
    "document_links",
    "final_files",
    "publish_study",
    "publication_targets",
    "relocated_path",
    "verify_study",
    "verify_publication",
)


STUDIES = Path("studies")
FINAL_SUFFIXES = frozenset({".md", ".pdf", ".png", ".svg"})
WORK_DIRECTORIES = frozenset({"runs", "cases", "reports", "logs", "helm", "frozen-source", "__pycache__"})


def relocated_path(path: Path, backend: str = "reference") -> Path:
    """
    Map legacy study links to their reviewed destination without guessing unknown names.

    Args:
        path (Path): Absolute path resolved from the original document.
        backend (str): Execution lane of the destination document.

    Returns:
        Path: Relocated known study path; unrelated and already separated paths are unchanged.
    """
    project = Path.cwd().resolve()
    studies = project / STUDIES
    if path.is_relative_to(studies):
        relative = path.relative_to(studies)
        if relative.parts and relative.parts[0] in {study.name for study in CATALOG}:
            return project / publication_path(relative.parts[0], backend) / Path(*relative.parts[1:])
    return path


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


def document_links(content: str, original: Path, destination: Path, *, hide_work_data: bool = True) -> str:
    """
    Relocate study links and describe private run data without publishing cache URLs.

    Args:
        content (str): Study Markdown before publication.
        original (Path): Previous published location used to resolve relative links.
        destination (Path): New published document location.
        hide_work_data (bool): Replace raw-data links only when publishing final study artifacts.

    Returns:
        str: Markdown linking final results and documentation, with raw artifacts labelled local.
    """
    project = Path.cwd().resolve()
    published = project / STUDIES
    backend = "gpu" if destination.resolve().is_relative_to(published / "gpu") else "reference"
    lines = []
    fence = ""
    for line in content.splitlines():
        marker = line.lstrip()
        if marker.startswith(("```", "~~~")):
            fence = "" if fence else marker[:3]
        if not fence and not marker.startswith(("```", "~~~")):
            # Match destination spans independently of labels so nested images and
            # escaped citation brackets keep their exact original Markdown labels.
            labels = {match.end(): match for match in link_matches(line)}
            code = [match.span() for match in CODE.finditer(line)]
            targets = re.finditer(r"(?<=\])\((?:<([^>]+)>|([^\s)]+))\)", line)
            for match in reversed(list(targets)):
                if any(start <= match.start() < end for start, end in code):
                    continue
                target = match[1] or match[2]
                parsed = urlsplit(target)
                if parsed.scheme or parsed.netloc or not parsed.path:
                    continue
                path = (original.parent / unquote(parsed.path)).resolve()
                path = relocated_path(path, backend)
                study_artifact = path.is_relative_to(published)
                private = (
                    path.is_relative_to(project / ".cache") or any(part.endswith("-runs") for part in path.relative_to(project).parts)
                    if path.is_relative_to(project)
                    else False
                )
                if hide_work_data and (
                    private
                    or study_artifact
                    and (
                        path.suffix.lower() not in FINAL_SUFFIXES
                        or any(part in WORK_DIRECTORIES for part in path.relative_to(published).parts)
                    )
                ):
                    label = labels.get(match.end())
                    if label is not None:
                        line = line[: label.start()] + f"{label[1]} (local run data)" + line[match.end() :]
                        continue
                    replacement = " (local run data)"
                else:
                    relative = os.path.relpath(path, destination.parent.resolve())
                    query = f"?{parsed.query}" if parsed.query else ""
                    fragment = f"#{parsed.fragment}" if parsed.fragment else ""
                    replacement = match[0] if relative + query + fragment == target else f"(<{relative}{query}{fragment}>)"
                line = line[: match.start()] + replacement + line[match.end() :]
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


def verify_publication(source: Path, destination: Path) -> None:
    """
    Validate artifacts, backend evidence and destination before changing a publication.

    Args:
        source (Path): Cached run containing raw measurements and finished plots.
        destination (Path): Dedicated final study directory under studies.

    Returns:
        None: The destination is compatible with the verified measurement evidence.

    Raises:
        ValueError: Artifacts or backend evidence cannot safely populate the destination.
    """
    sources = tuple(final_files(source))
    if not sources:
        raise ValueError(f"No final documents or plots to publish in {source}")
    if source.resolve() == destination.resolve() or source.resolve().is_relative_to(destination.resolve()):
        raise ValueError("Study measurements must be outside the final publication directory")
    verify_study(source)
    evidence = read_evidence(source)
    requested = str(mapping(evidence["options"])["name"]) if evidence is not None else "reference"
    name = destination.name
    known = next((study for study in CATALOG if study.name == name), None)
    if known is not None and known.backend_dependent:
        expected_destination = publication_path(name, requested).resolve()
        if destination.resolve() != expected_destination:
            raise ValueError(f"Study backend evidence requires publication at {expected_destination}")
        if requested == "gpu":
            plans = [mapping(plan) for plan in sequence(evidence["plans"])] if evidence is not None else []
            if (
                not plans
                or any(plan["selected"] != "gpu" for plan in plans)
                or sum(int(str(plan["physical_cases"])) for plan in plans) <= 0
            ):
                raise ValueError("GPU publication requires actual device work without reference fallback")


def publication_targets(sources: Sequence[Path]) -> dict[Path, Path]:
    """
    Preflight a complete refresh and reject mixed backend settings before any replacement.

    Args:
        sources (Sequence[Path]): Completed study directories from one refresh.

    Returns:
        dict[Path, Path]: Verified source-to-publication mapping in input order.

    Raises:
        ValueError: A study is invalid or dependent studies use different backend options.
    """
    targets = {}
    options: dict[str, object] | None = None
    for source in sources:
        evidence = read_evidence(source)
        current = mapping(evidence["options"]) if evidence is not None else asdict(BackendOptions())
        destination = publication_path(source.name, str(current["name"]))
        verify_publication(source, destination)
        if next(study for study in CATALOG if study.name == source.name).backend_dependent:
            if options is not None and current != options:
                raise ValueError("Refresh studies use different backend settings")
            options = current
        targets[source] = destination
    return targets


def publish_study(source: Path, destination: Path) -> dict[str, str]:
    """
    Replace one study's published files with its finished documents and figures.

    Args:
        source (Path): Cached run containing raw measurements and finished plots.
        destination (Path): Dedicated final study directory under studies.

    Returns:
        dict[str, str]: SHA-256 checksums of the published files, keyed by destination path.
    """
    verify_publication(source, destination)
    sources = tuple(final_files(source))
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

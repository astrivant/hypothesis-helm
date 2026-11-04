"""
Reconcile the reviewed study inventory without manufacturing new measurements.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from hypothesis_helm.reporting.documentation.contents import with_contents

from hypothesis_helm_benchmarking.catalog import CATALOG, publication_path
from hypothesis_helm_benchmarking.reporting.publication import document_links, relocated_path

__all__ = ("reconcile",)

LOGGER = logging.getLogger(__name__)


def reconcile(*, check: bool = False) -> bool:
    """
    Move historical CPU results, repair Markdown links and create unmeasured GPU study guides.

    Args:
        check (bool): Report stale layout without writing files or moving directories.

    Returns:
        bool: Whether the existing layout already matched the reviewed inventory.

    Raises:
        ValueError: Both legacy and CPU destinations exist; neither may be silently replaced.
        subprocess.CalledProcessError: The current directory is not an accessible Git checkout.
    """
    project = Path.cwd().resolve()
    moves: dict[Path, Path] = {}
    for study in CATALOG:
        source = project / "studies" / study.name
        if study.backend_dependent and source.exists():
            destination = project / publication_path(study.name)
            if destination.exists():
                raise ValueError(f"Both study locations exist: {source} and {destination}")
            moves[source] = destination
    documents = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", "*.md"], check=True, capture_output=True, text=True
    ).stdout.split("\0")
    updates: dict[Path, str] = {}
    for name in filter(None, documents):
        original = project / name
        if not original.is_file() or original.is_symlink():
            continue
        destination = relocated_path(original)
        content = original.read_text()
        revised = document_links(content, original, destination, hide_work_data=False)
        if original.parent in moves and original.name == "README.md":
            title, _, body = revised.partition("\n")
            revised = (
                title + "\n\n"
                "These retained measurements used the reference CPU implementation. "
                "They have not been rerun with `cpu-vector`; moving this report did not create new observations.\n" + body
            )
        if revised != content or destination != original:
            updates[destination] = revised

    index = [
        "# Benchmark studies",
        "",
        "[Benchmarking guide](../docs/benchmarking/README.md) | [CPU studies](cpu/README.md) | [GPU studies](gpu/README.md)",
        "",
        "The inventory follows the executed code paths. Backend-dependent studies have separate CPU and GPU destinations. "
        "Shared studies do not invoke finite predicate planning. Existing figures retain their recorded measurements; "
        "an unmeasured GPU guide is not evidence of a GPU run.",
        "",
        "Run `hypothesis-helm-benchmark inventory` for the machine-readable inventory and classification reasons.",
        "",
        "## Shared studies",
        "",
        "| Study | Scope |",
        "| --- | --- |",
        *(f"| [{study.name}]({study.name}/README.md) | {study.reason} |" for study in CATALOG if not study.backend_dependent),
        "",
        "## Backend comparisons",
        "",
        "| Study | CPU | GPU | Scope |",
        "| --- | --- | --- | --- |",
        *(
            f"| {study.name} | [Results](cpu/{study.name}/README.md) | [Study](gpu/{study.name}/README.md) | {study.reason} |"
            for study in CATALOG
            if study.backend_dependent
        ),
        "",
    ]
    updates[project / "studies/README.md"] = with_contents("\n".join(index))
    for lane in ("cpu", "gpu"):
        description = (
            "Retained results identify their original reference CPU implementation. "
            "Fresh compiled CPU runs use `--execution-backend cpu-vector`."
            if lane == "cpu"
            else "Each study requires recorded physical CUDA execution. "
            "Unmeasured guides contain no copied CPU figures or inferred GPU results."
        )
        lines = [f"# {lane.upper()} studies", "", "[All studies](../README.md)", "", description, ""]
        lines.extend(f"- [{study.name}]({study.name}/README.md)" for study in CATALOG if study.backend_dependent)
        updates[project / f"studies/{lane}/README.md"] = with_contents("\n".join([*lines, ""]))
    for study in CATALOG:
        if not study.backend_dependent:
            continue
        destination = project / publication_path(study.name, "gpu") / "README.md"
        if destination.exists():
            continue
        command = f"hypothesis-helm-benchmark --execution-backend gpu {study.command}"
        if study.name == "error-surface-quartic":
            command += " --input .cache/benchmarks/gpu/error-surface/results.json"
        elif study.name == "bug-density":
            command += " --input-complexity 8 --max-strength 6 --bug-percent 5 --seed 2026 --time-limit 9m"
        command += f" --output .cache/benchmarks/gpu/{study.name}"
        lines = [
            f"# {study.name}: GPU study",
            "",
            "**Status: not measured on a GPU.**",
            "",
            study.reason,
            "",
            f"[CPU study](../../cpu/{study.name}/README.md) | [Backend contract](../../../docs/benchmarking/backends.md)",
            "",
            "Use Linux with a physical NVIDIA CUDA device, its driver, Helm 4 and the locked GPU/benchmarking dependencies. "
            "From the repository root:",
            "",
            "```sh",
            command,
            "```",
            "",
            "Use the matching CPU parameters and seeds for a paired comparison. "
            "A successful run retains backend receipts with the actual engine, native work, host fallbacks and measurement hashes. "
            "Publishing requires those receipts; CPU measurements cannot populate this directory as GPU observations.",
            "",
        ]
        updates[destination] = with_contents("\n".join(lines))

    changed = {path: content for path, content in updates.items() if not path.exists() or path.read_text() != content}
    LOGGER.info("Study layout: %d directory moves, %d document updates, check=%s", len(moves), len(changed), check)
    if check:
        return not moves and not changed
    for source, destination in moves.items():
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.rename(destination)
    for destination, content in changed.items():
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content)
    return not moves and not changed

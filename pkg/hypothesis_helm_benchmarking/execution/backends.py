"""
Bind study outputs to actual backend execution and reject mixed-backend replay inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
from collections.abc import Callable
from pathlib import Path

from attrs import asdict
from hypothesis_helm.compiler.backends.scheduler import BackendOptions
from hypothesis_helm.schemas.contracts import mapping, sequence

from hypothesis_helm_benchmarking.catalog import CATALOG
from hypothesis_helm_benchmarking.charts.fixture import FixtureWorkspace

__all__ = ("execute", "prepare_arguments", "read_evidence")

LOGGER = logging.getLogger(__name__)
MEASUREMENTS = ("results.json", "calibration.json")
DEPENDENT_COMMANDS = frozenset(study.command for study in CATALOG if study.backend_dependent)


def read_evidence(directory: Path) -> dict[str, object] | None:
    """
    Verify the retained backend receipt against its exact measurement bytes.

    Args:
        directory (Path): Existing measurement directory.

    Returns:
        dict[str, object] | None: Verified receipt, or None for historical unlabelled data.

    Raises:
        ValueError: Receipt is incomplete, malformed or detached from its measurements.
    """
    path = directory / "backend.json"
    if not path.exists():
        return None
    receipt = mapping(json.loads(path.read_text()))
    if receipt.get("version") != 1 or receipt.get("status") != "complete":
        raise ValueError(f"Incomplete backend evidence: {directory}")
    hashes = mapping(receipt["measurements"])
    if not hashes or set(hashes) - set(MEASUREMENTS):
        raise ValueError(f"Invalid backend measurement inventory: {directory}")
    for name, expected in hashes.items():
        if hashlib.sha256((directory / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Backend evidence no longer matches {directory / name}")
    return receipt


def prepare_arguments(command: str, arguments: list[str], backend: BackendOptions) -> list[str]:
    """
    Isolate default CPU/GPU measurements without changing explicit destinations.

    Args:
        command (str): Selected benchmark command.
        arguments (list[str]): Caller-owned command options.
        backend (BackendOptions): Explicit invocation selection.

    Returns:
        list[str]: New argument list with a backend-specific default output when applicable.

    Raises:
        ValueError: A compiled backend is requested for a study with no compiled planning.
    """
    result = list(arguments)
    if command not in DEPENDENT_COMMANDS:
        if backend.name != "reference" and command != "inventory":
            raise ValueError(f"{command} is backend-independent; omit --execution-backend")
        return result
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument("--output", type=Path)
    settings, _ = parser.parse_known_args(result)
    # Derived fits default beside their supplied observations, retaining their source lane.
    if settings.output is None and command != "polynomial-surface":
        lane = "gpu" if backend.name == "gpu" else "cpu"
        result.extend(["--output", str(Path(".cache/benchmarks") / lane / command)])
    return result


def execute(command: str, arguments: list[str], workspace: FixtureWorkspace, invoke: Callable[[], int]) -> int:
    """
    Preserve source receipts for replay and retain actual planner work after a new study.

    Args:
        command (str): Benchmark command being measured or replayed.
        arguments (list[str]): Explicit final command options.
        workspace (FixtureWorkspace): Invocation owner, backend settings and completed plan receipts.
        invoke (Callable[[], int]): Selected study entrypoint with explicit inputs already bound.

    Returns:
        int: The selected study's exit status.

    Raises:
        ValueError: Replay inputs mix backends, lack native evidence or would overwrite an existing receipt.
    """
    if command not in DEPENDENT_COMMANDS or any(value in {"-h", "--help"} for value in arguments):
        return invoke()
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--plot-only", action="store_true")
    parser.add_argument("--merge-shards", type=Path, nargs="+")
    settings, _ = parser.parse_known_args(arguments)
    output = settings.output
    if output is None:
        if settings.input is None:
            raise ValueError("backend study requires an output directory")
        output = settings.input.parent / "polynomial-comparison"
    sources = [path.parent for path in settings.merge_shards or []]
    if settings.input is not None:
        sources.append(settings.input.parent)
    if settings.plot_only:
        sources.append(output)
    inherited: list[dict[str, object]] = []
    for source in sources:
        evidence = read_evidence(source)
        if evidence is None:
            if workspace.backend.name != "reference":
                raise ValueError(f"Native replay requires recorded backend evidence: {source}")
            continue
        if evidence["options"] != asdict(workspace.backend):
            raise ValueError("Study inputs and requested backend settings differ")
        inherited.extend(mapping(report) for report in sequence(evidence["plans"]))
    if settings.plot_only:
        # Plotting cannot create evidence of new device work or change measured options.
        return invoke()
    if (output / "backend.json").exists() or any((output / name).exists() for name in MEASUREMENTS):
        raise ValueError("choose a fresh backend study output directory")
    LOGGER.info("Starting study=%s backend=%s", command, workspace.backend.name)
    status = "incomplete"
    try:
        result = invoke()
        if result == 0 and workspace.backend.name != "reference" and not (inherited or workspace.backend_reports):
            raise ValueError("Study completed without executing the requested finite planner")
        status = "complete" if result == 0 else "incomplete"
        return result
    finally:
        measurements = {
            name: hashlib.sha256((output / name).read_bytes()).hexdigest() for name in MEASUREMENTS if (output / name).is_file()
        }
        if measurements:
            plans = [*inherited, *workspace.backend_reports]
            receipt = {
                "version": 1,
                "status": status,
                "options": asdict(workspace.backend),
                "plans": plans,
                "measurements": measurements,
            }
            # Exclusive creation prevents a failed retry from silently relabelling prior measurements.
            with (output / "backend.json").open("x") as stream:
                stream.write(json.dumps(receipt, indent=2) + "\n")
            counts = {
                key: sum(int(str(plan[key])) for plan in plans)
                for key in ("physical_cases", "logical_cases", "committed_cases", "unknown_cases", "batches")
            }
            selected = ", ".join(sorted({str(plan["selected"]) for plan in plans})) or "none recorded"
            lines = [
                "# Backend execution evidence",
                "",
                f"Requested engine: `{workspace.backend.name}`. Observed engines: {selected}. Status: **{status}**.",
                "",
                "Compiled work evaluates finite schema predicates. Helm rendering, template specialization, seeded selection, "
                "failure callbacks and reporting remain on the host. No end-to-end GPU speedup is implied.",
                "",
                "| Counter | Observed |",
                "| --- | ---: |",
                *(f"| {key.replace('_', ' ')} | {value} |" for key, value in counts.items()),
                "",
                "Physical evaluations include speculative work; committed cases are planner selections, not completed chart tests.",
                "",
                "[Exact run receipt](backend.json)",
                "",
            ]
            (output / "BACKEND.md").write_text("\n".join(lines))
            LOGGER.info("Recorded study=%s status=%s planner_calls=%d", command, status, len(plans))

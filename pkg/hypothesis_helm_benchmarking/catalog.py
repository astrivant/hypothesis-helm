"""
Declare study ownership and the publication lanes actually affected by finite planning.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from attrs import asdict, frozen

from hypothesis_helm_benchmarking.charts.fixture import FixtureWorkspace

__all__ = ("CATALOG", "Study", "main", "publication_path")

LOGGER = logging.getLogger(__name__)


@frozen
class Study:
    """
    Bind one published study to its execution contract.

    Attributes:
        name (str): Stable directory identifier.
        command (str | None): Benchmark command, or no standalone measurement command.
        backend_dependent (bool): Whether finite compiled planning contributes to the study.
        reason (str): Inspected basis for separating or sharing results.
    """

    name: str
    command: str | None
    backend_dependent: bool
    reason: str


CATALOG = (
    Study("bug-density", "discovery", True, "Finite interaction planning and defect recall at increasing strengths."),
    Study("calibration-variation", "calibration", True, "Finite population planning before calibration and selection."),
    Study("chart-topologies", "topology", False, "Template graph export and baseline Helm renders, without finite predicate planning."),
    Study("discovery", "discovery", True, "Finite interaction planning and defect recall at increasing strengths."),
    Study("error-surface", "error-surface", True, "Fresh finite planning for every filtering strategy and error placement."),
    Study("error-surface-quartic", "polynomial-surface", True, "Fits retained error-surface observations from the selected backend."),
    Study("expansion", "expansion", True, "Finite population planning before paired failure-region expansion."),
    Study("filtering", "filtering", True, "Production chart testing, including finite planning and filtering phase timings."),
    Study("flamegraphs", "flamegraph", False, "Profiles the shared rendering/scaling workload, which does not call finite planning."),
    Study("matrix", "matrix", True, "Fresh finite planning for each structural case and strategy."),
    Study("nesting", "nesting", True, "Finite population and interaction planning across chart nesting profiles."),
    Study("pca", "pca", True, "Finite population planning before output projection and filtering comparisons."),
    Study("performance", "run", False, "Explicit input-prefix rendering and exact-output pruning; no finite predicate planning."),
    Study("resource-sizing", None, False, "Chart inventories and historical process observations."),
    Study("sampling", "sampling", False, "Independent complete-population oracle and seeded sampling of observed defects."),
    Study("sensitivity", "sensitivity", False, "Explicit mutation renders and output distances, without finite predicate planning."),
    Study("sensitivity-ordering", "sensitivity-ordering", True, "Finite interaction planning before order and discovery comparisons."),
    Study("sparsity", "sparsity", False, "Nested samples of an explicit workload and observed output distributions."),
    Study("stress", "stress", True, "Fresh finite planning across the structural stress progression."),
    Study("structural-sparsity", "structural-sparsity", True, "Finite planning and filtering with distant relevant inputs."),
    Study("structure-depth", "structure-depth", True, "Finite population planning before topology filter-depth comparisons."),
    Study("structure-mixtures", "generate", False, "Seeded fixture definitions and generation instructions."),
    Study("structure-sparsity", "sparsity", False, "Nested samples of an explicit structural workload."),
)


def publication_path(name: str, backend: str = "reference") -> Path:
    """
    Resolve a study's publication lane without implying that measurements exist.

    Args:
        name (str): Declared study identifier.
        backend (str): Actual reference, cpu-vector or gpu execution selection.

    Returns:
        Path: Relative publication directory, shared or under cpu/gpu.

    Raises:
        ValueError: Study or backend is unknown.
    """
    if backend not in {"reference", "cpu-vector", "gpu"}:
        raise ValueError(f"unknown study backend: {backend}")
    study = next((item for item in CATALOG if item.name == name), None)
    if study is None:
        raise ValueError(f"unknown study: {name}")
    if study.backend_dependent:
        return Path("studies") / ("gpu" if backend == "gpu" else "cpu") / name
    return Path("studies") / name


def main(argv: list[str] | None = None, *, workspace: FixtureWorkspace | None = None) -> int:
    """
    Print the complete reviewed inventory and backend-specific destinations.

    Args:
        argv (list[str] | None): Explicit command arguments.
        workspace (FixtureWorkspace | None): Optional invocation owner; inventory does not create fixtures.

    Returns:
        int: Zero after emitting JSON; diagnostics remain on stderr.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=("all", "shared", "backend"), default="all")
    parser.add_argument("--backend", choices=("reference", "cpu-vector", "gpu"), default="reference")
    parser.add_argument("--debug", action="store_true", help="include diagnostic logs on stderr")
    layout = parser.add_mutually_exclusive_group()
    layout.add_argument("--write-layout", action="store_true", help="reconcile study directories and generated indexes in this checkout")
    layout.add_argument("--check-layout", action="store_true", help="check directory and index freshness without changing files")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)
    if args.write_layout or args.check_layout:
        from hypothesis_helm_benchmarking.reporting.layout import reconcile

        current = reconcile(check=args.check_layout)
        return int(args.check_layout and not current)
    studies = [study for study in CATALOG if args.scope == "all" or study.backend_dependent == (args.scope == "backend")]
    LOGGER.info("Inventorying %d studies for backend=%s", len(studies), args.backend)
    print(json.dumps([{**asdict(study), "destination": str(publication_path(study.name, args.backend))} for study in studies], indent=2))
    return 0

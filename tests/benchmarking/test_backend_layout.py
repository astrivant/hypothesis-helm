"""
Check study routing, exact backend provenance and safe legacy document relocation.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import subprocess
import sys
from pathlib import Path

import pytest
from hypothesis_helm.compiler.backends.scheduler import BackendOptions, Report
from hypothesis_helm_benchmarking.catalog import CATALOG, publication_path
from hypothesis_helm_benchmarking.charts.fixture import FixtureWorkspace
from hypothesis_helm_benchmarking.execution.backends import execute, prepare_arguments, read_evidence
from hypothesis_helm_benchmarking.refresh.plan import Refresh
from hypothesis_helm_benchmarking.reporting.publication import document_links, publication_targets, publish_study
from hypothesis_helm_benchmarking.studies.polynomial_surface import main as compare_surfaces


@pytest.mark.parametrize("damage", [None, "source", "fit", "figure"])
def test_refresh_quartic_requires_complete_source_bound_results(tmp_path: Path, damage: str | None) -> None:
    """
    Accept a derived study only while its source, fits and figure pairs remain complete.

    Args:
        tmp_path (Path): Synthetic refresh workspace.
        damage (str | None): One corrupted input, or None for a complete comparison.

    Returns:
        None: The verification recipe rejects stale or incomplete comparisons.
    """
    project = Path(__file__).resolve().parents[2]
    (tmp_path / "provenance.json").write_text(json.dumps({"code_sha256": "synthetic"}))
    source = tmp_path / "outputs/error-surface/results.json"
    source.parent.mkdir(parents=True)
    source.write_text('{"synthetic": true}\n')
    destination = tmp_path / "outputs/error-surface-quartic"
    destination.mkdir()
    result = {"source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "fits": [{"status": "completed"}]}
    if damage == "fit":
        result["fits"][0]["status"] = "unavailable"
    (destination / "results.json").write_text(json.dumps(result))
    (destination / "README.md").write_text("# Synthetic comparison\n")
    (destination / "comparison-1.png").write_bytes(b"x" * 1001)
    if damage != "figure":
        (destination / "comparison-1.svg").write_text('<svg><g id="plot-question" />' + " " * 1001 + "</svg>")
    if damage == "source":
        source.write_text('{"synthetic": false}\n')
    run = subprocess.run(
        [
            sys.executable,
            str(project / "pkg/hypothesis_helm_benchmarking/refresh/recipes/verify-measurements.py"),
            str(tmp_path),
            "--study",
            "error-surface-quartic",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert (run.returncode == 0) == (damage is None), run.stdout + run.stderr


def test_quartic_inherits_gpu_measurement_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Generate and preflight a comparison from the exact selected GPU source receipt.

    Args:
        tmp_path (Path): Isolated synthetic measurements and output.
        monkeypatch (pytest.MonkeyPatch): Resolve the publication destination in the fixture.

    Returns:
        None: Derived output retains the source receipt and rejects changed input bytes.
    """
    monkeypatch.chdir(tmp_path)
    source = Path(".cache/refresh/outputs/error-surface")
    destination = Path(".cache/refresh/outputs/error-surface-quartic")
    workspace = FixtureWorkspace(backend=BackendOptions("gpu"))

    def measure() -> int:
        """
        Provide a synthetic complete surface with explicitly simulated GPU evidence.

        Returns:
            int: Successful fixture creation, without executing a GPU.
        """
        source.mkdir(parents=True)
        rows = [
            {
                "axis": "clustering",
                "axis_value": x,
                "error_percent": y,
                "repeat": repeat,
                "strategy": "filter",
                "status": "passed",
                "total_seconds": 10 + (x * y) ** 2,
                "errors_missed": x * y,
            }
            for x, y, repeat in itertools.product(range(5), range(5), range(2))
        ]
        (source / "results.json").write_text(json.dumps({"metadata": {"repeats": 2}, "rows": rows}))
        workspace.backend_reports.append(Report("gpu", "gpu", device="cuda", physical_cases=1).export())
        return 0

    assert execute("error-surface", ["--output", str(source)], workspace, measure) == 0
    arguments = ["--input", str(source / "results.json"), "--output", str(destination)]
    assert (
        execute("polynomial-surface", arguments, FixtureWorkspace(backend=BackendOptions("gpu")), lambda: compare_surfaces(arguments)) == 0
    )
    receipt = read_evidence(destination)
    assert receipt is not None and receipt["plans"] == read_evidence(source)["plans"]
    assert publication_targets([destination])[destination] == publication_path("error-surface-quartic", "gpu")
    (source / "results.json").write_text("{}")
    with pytest.raises(ValueError, match="no longer matches"):
        execute("polynomial-surface", arguments, FixtureWorkspace(backend=BackendOptions("gpu")), lambda: 0)


def test_inventory_routes_only_backend_dependent_work() -> None:
    """
    Keep shared work singular and separate every declared dependent publication.

    Returns:
        None: Every study has one shared destination or two distinct backend lanes.
    """
    assert len(CATALOG) == len({study.name for study in CATALOG}) == 23
    for study in CATALOG:
        cpu = publication_path(study.name, "cpu-vector")
        gpu = publication_path(study.name, "gpu")
        assert (cpu != gpu) == study.backend_dependent
        assert cpu == publication_path(study.name, "reference")
    plan = {operation.name: operation for operation in Refresh(Path(".cache/refresh/example"), BackendOptions("gpu")).operations()}
    for study in CATALOG:
        if study.backend_dependent:
            assert "gpu" in plan[study.name].command
    assert plan["error-surface-quartic"].requires == ("error-surface",)
    assert "--execution-backend" not in plan["performance"].command


def test_links_relocate_once_and_keep_shared_targets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Keep figures, sibling studies and external documentation valid at the deeper GPU location.

    Args:
        tmp_path (Path): Isolated publication project.
        monkeypatch (pytest.MonkeyPatch): Select the project without changing other tests.

    Returns:
        None: Each local link resolves in the appropriate lane; literal commands remain unchanged.
    """
    monkeypatch.chdir(tmp_path)
    original = Path("studies/pca/README.md")
    destination = Path("studies/gpu/pca/README.md")
    content = (
        "![Plot](plot.png)\n[CPU/GPU sibling](../matrix/README.md)\n[Shared](../sampling/README.md)\n"
        "[Guide](../../docs/benchmarking/README.md#run)\n[Raw](results.json)\n"
        "```sh\ncat studies/pca/README.md\n```\n"
    )
    revised = document_links(content, original, destination)
    assert "![Plot](plot.png)" in revised
    assert "[CPU/GPU sibling](../matrix/README.md)" in revised
    assert "[Shared](<../../sampling/README.md>)" in revised
    assert "[Guide](<../../../docs/benchmarking/README.md#run>)" in revised
    assert "Raw (local run data)" in revised
    assert "cat studies/pca/README.md" in revised


def test_nested_and_escaped_link_labels(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Relocate destinations without confusing image links or escaped citation labels.

    Args:
        tmp_path (Path): Isolated project root.
        monkeypatch (pytest.MonkeyPatch): Select the synthetic project.

    Returns:
        None: Both nested destinations move once and inline examples remain literal.
    """
    monkeypatch.chdir(tmp_path)
    content = (
        "[![Plot](studies/pca/plot.png)](studies/pca/README.md)\n"
        r"<sup>[\[4\]](studies/pca/README.md)</sup>"
        "\n"
        "`[literal](studies/pca/README.md)`\n"
    )
    revised = document_links(content, Path("README.md"), Path("README.md"))
    assert "[![Plot](<studies/cpu/pca/plot.png>)](<studies/cpu/pca/README.md>)" in revised
    assert r"<sup>[\[4\]](<studies/cpu/pca/README.md>)</sup>" in revised
    assert "`[literal](studies/pca/README.md)`" in revised
    assert document_links(revised, Path("README.md"), Path("README.md")) == revised


def test_refresh_preflights_all_backend_receipts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Reject a late native fallback or mixed settings before replacing earlier publications.

    Args:
        tmp_path (Path): Isolated measurement and publication root.
        monkeypatch (pytest.MonkeyPatch): Select the synthetic project.

    Returns:
        None: Failed validation leaves the entire publication set untouched.
    """
    monkeypatch.chdir(tmp_path)
    sources = [Path(".cache/outputs") / name for name in ("discovery", "matrix")]
    for source in sources:
        source.mkdir(parents=True)
        (source / "README.md").write_text("# Synthetic study\n")
    workspace = FixtureWorkspace(backend=BackendOptions("gpu", "reference"))

    def record() -> int:
        """
        Supply a fallback receipt for the last study in the synthetic refresh.

        Returns:
            int: Successful fixture production, with no claimed GPU work.
        """
        (sources[1] / "results.json").write_text("{}\n")
        workspace.backend_reports.append(Report("gpu", "reference").export())
        return 0

    execute("matrix", ["--output", str(sources[1])], workspace, record)
    with pytest.raises(ValueError, match="actual device work"):
        publication_targets(sources)
    assert not Path("studies").exists()
    receipt_path = sources[1] / "backend.json"
    receipt = json.loads(receipt_path.read_text())
    receipt["options"]["name"] = "cpu-vector"
    receipt_path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="different backend settings"):
        publication_targets(sources)


@pytest.mark.parametrize(
    "selected,device,valid",
    [("gpu", "cuda", True), ("gpu", "mps", True), ("gpu", "", False), ("gpu", "cuda,mps", False), ("reference", "", False)],
)
def test_gpu_publication_requires_actual_native_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, selected: str, device: str, valid: bool
) -> None:
    """
    Distinguish native evidence from an explicitly permitted host fallback before publication.

    Args:
        tmp_path (Path): Isolated measurement and publication project.
        monkeypatch (pytest.MonkeyPatch): Resolve publication destinations locally.
        selected (str): Simulated receipt route, without claiming a hardware test.
        device (str): Recorded device types, or empty when provenance is missing.
        valid (bool): Whether the synthetic receipt is admissible.

    Returns:
        None: GPU receipts publish only with native work; fallback leaves the destination untouched.
    """
    monkeypatch.chdir(tmp_path)
    source = Path(".cache/gpu-matrix")
    workspace = FixtureWorkspace(backend=BackendOptions("gpu", "reference"))

    def run() -> int:
        """
        Create synthetic measurement data and a planner receipt for publication testing.

        Returns:
            int: Zero for a completed synthetic fixture.
        """
        source.mkdir(parents=True)
        (source / "results.json").write_text('{"synthetic": true}\n')
        (source / "README.md").write_text("# Matrix\n")
        for observed_device in device.split(","):
            workspace.backend_reports.append(
                Report("gpu", selected, device=observed_device, physical_cases=8 if selected == "gpu" else 0).export()
            )
        return 0

    assert execute("matrix", ["--output", str(source)], workspace, run) == 0
    assert read_evidence(source) is not None
    destination = publication_path("matrix", "gpu")
    if not valid:
        with pytest.raises(ValueError, match="actual device work"):
            publish_study(source, destination)
        assert not destination.exists()
    else:
        publish_study(source, destination)
        assert (destination / "BACKEND.md").is_file()
        with pytest.raises(ValueError, match="requires publication"):
            publish_study(source, publication_path("matrix", "cpu-vector"))
    # Changing any measured bytes invalidates replay and publication evidence.
    (source / "results.json").write_text('{"synthetic": "modified"}\n')
    with pytest.raises(ValueError, match="no longer matches"):
        read_evidence(source)


def test_native_replay_cannot_relabel_historical_data(tmp_path: Path) -> None:
    """
    Prevent a GPU flag on plot-only or merge commands from manufacturing GPU provenance.

    Args:
        tmp_path (Path): Unlabelled historical measurement directory.

    Returns:
        None: Replay fails before the supplied renderer is called.
    """
    (tmp_path / "results.json").write_text(json.dumps({"historical": True}))
    workspace = FixtureWorkspace(backend=BackendOptions("gpu"))
    with pytest.raises(ValueError, match="recorded backend evidence"):
        execute("matrix", ["--output", str(tmp_path), "--plot-only"], workspace, lambda: pytest.fail("must not render"))
    with pytest.raises(ValueError, match="backend-independent"):
        prepare_arguments("sampling", [], workspace.backend)
    arguments: list[str] = []
    assert prepare_arguments("matrix", arguments, workspace.backend) == ["--output", ".cache/benchmarks/gpu/matrix"]
    assert arguments == []

"""
Exercise the retained full-refresh recipes with isolated repositories and native workers.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from attrs import asdict

from hypothesis_helm.benchmarking.charts.stress import Stress, progression
from hypothesis_helm.benchmarking.charts.structures import STRUCTURES
from hypothesis_helm.benchmarking.studies.error_surface import METHODS, METRICS, RATES
from hypothesis_helm.benchmarking.studies.matrix import STRATEGIES
from hypothesis_helm.charts import yamlio
from hypothesis_helm.schemas.contracts import configuration_key, mapping


@pytest.mark.integration
def test_refresh_repository_recipe(tmp_path: Path) -> None:
    """
    Verify fresh initialization, worker findings, aggregation, and missing-worker rejection.

    Args:
        tmp_path (Path): Isolated checkout, source repositories, and refresh outputs.

    Returns:
        None: Both repository reports retain findings and incomplete work cannot replace a report.
    """
    if shutil.which("helm") is None or shutil.which("parallel") is None:
        pytest.skip("Helm 4 and GNU Parallel are required")
    version = subprocess.check_output(["helm", "version", "--short"], text=True)
    if not version.startswith("v4."):
        pytest.skip("The full refresh requires Helm 4")
    project = Path(__file__).resolve().parents[3]
    (tmp_path / "pkg").symlink_to(project / "pkg", target_is_directory=True)
    for name in ("bitnami-charts", "prometheus-community-helm-charts"):
        source = tmp_path / "third_party" / name
        shutil.copytree(project / "examples/broken", source / "charts/broken")
        subprocess.run(["git", "init", str(source)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(source), "add", "."], check=True, capture_output=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(source),
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.org",
                "-c",
                "commit.gpgsign=false",
                "commit",
                "-m",
                "Fixture",
            ],
            check=True,
            capture_output=True,
        )
    environment = dict(os.environ, PYTHONPATH=str(project / "pkg"), PATH=f"{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}")
    run_root = Path(".cache/benchmarks/refresh-1234")
    initialized = subprocess.run(
        [sys.executable, str(project / "pkg/hypothesis_helm/benchmarking/refresh/recipes/initialize.py"), str(run_root)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    assert (tmp_path / ".cache/benchmarks/latest-refresh.txt").read_text().strip() == str(run_root)
    snapshot = tmp_path / run_root / "frozen-source"
    for name, expected in json.loads((tmp_path / run_root / "measured-source-hashes.json").read_text()).items():
        assert hashlib.sha256((snapshot / name).read_bytes()).hexdigest() == expected
    environment["PYTHONPATH"] = str(snapshot / "pkg")
    for name in ("bitnami", "prometheus"):
        run = Path(f"docs/reports/{name}-runs/{name}-charts_1234")
        result = subprocess.run(["bash", str(run / "run.sh"), str(run)], cwd=tmp_path, env=environment, capture_output=True, check=False)
        assert result.returncode == 1, result.stdout + result.stderr
        finalized = subprocess.run(
            [sys.executable, str(run / "finalize.py"), str(run), name],
            cwd=tmp_path,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert finalized.returncode == 0, finalized.stdout + finalized.stderr
        report = tmp_path / "docs/reports" / f"{name}.pdf"
        assert report.read_bytes().startswith(b"%PDF")
        verified = json.loads((tmp_path / run / "verification.json").read_text())
        assert verified["completed_jobs"] == verified["expected_charts"] == 1
        assert verified["attempts"] > 0
        original_pdf = report.read_bytes()
        (tmp_path / run / "jobs/1.json").unlink()
        incomplete = subprocess.run(
            [sys.executable, str(run / "finalize.py"), str(run), name],
            cwd=tmp_path,
            env=environment,
            capture_output=True,
            check=False,
        )
        assert incomplete.returncode != 0
        assert report.read_bytes() == original_pdf


@pytest.mark.parametrize(
    "damage",
    [
        None,
        "censored",
        "missing-step",
        "duplicate",
        "parameters",
        "recipe",
        "plot",
        "sampling-reference",
        "sampling-inventory",
        "sensitivity-incomplete",
        "sensitivity-pruning",
        "calibration-count",
        "calibration-trials",
        "calibration-reference",
        "calibration-duplicate",
        "error-surface-count",
        "error-surface-zero-recall",
        "error-surface-chart",
        "filtering-count",
        "filtering-duplicate",
        "filtering-timing",
        "matrix-missing-aggressive",
        "pca-missing-aggressive",
        "expansion-missing-aggressive",
        "nesting-missing-aggressive",
        "stress-missing-aggressive",
    ],
)
def test_refresh_requires_complete_stress_matrix(tmp_path: Path, damage: str | None) -> None:
    """
    Reject incomplete or inconsistent stress, calibration and runtime results before publication.

    Args:
        tmp_path (Path): Synthetic measurement ledgers for the publication gate.
        damage (str | None): One deliberate corruption, or an intact matrix.

    Returns:
        None: Only complete study matrices with consistent references, phases and counts pass verification.
    """
    project = Path(__file__).resolve().parents[3]
    (tmp_path / "provenance.json").write_text(json.dumps({"code_sha256": "test-source"}))
    studies = (
        "performance",
        "discovery",
        "bug-density",
        "sparsity",
        "structure-sparsity",
        "structural-sparsity",
        "matrix",
        "pca",
        "expansion",
        "structure-depth",
        "nesting",
        "stress",
        "sampling",
        "sensitivity",
        "calibration-variation",
        "filtering",
        "error-surface",
    )
    for study in studies:
        directory = tmp_path / "outputs" / study
        directory.mkdir(parents=True)
        (directory / "topology-stress.png").write_bytes(b"x" * 1001)
        (directory / "topology-stress.svg").write_bytes(b"x" * 1001)
        (directory / "README.md").write_text("Test measurement fixture\n")
        (directory / "results.csv").write_text("status\npassed\n")
        rows: list[dict[str, object]] = [{"status": "passed"}]
        if study == "stress":
            rows = []
            (directory / "cases").mkdir()
            for step, (name, settings) in enumerate(progression(Stress())):
                (directory / "cases" / f"{name}.yaml").write_text(yamlio.dump({"parameters": {"stress": asdict(settings)}}))
                for strategy in STRATEGIES:
                    rows.append(
                        {
                            "step": step,
                            "case": name,
                            "strategy": strategy,
                            "parameters": asdict(settings),
                            "status": "passed",
                            "error": None,
                            "completed": 4,
                            "selected": 4,
                            "remaining": 0,
                        }
                    )
            if damage == "missing-step":
                rows = rows[: -len(STRATEGIES)]
            elif damage == "duplicate":
                rows[-1] = rows[0]
            elif damage == "parameters":
                rows[0]["parameters"] = asdict(Stress(gate_depth=1))
            elif damage == "recipe":
                (directory / "cases/00-worst-case.yaml").unlink()
            elif damage == "plot":
                (directory / "topology-stress.svg").unlink()
            elif damage == "censored":
                for row in rows:
                    row.update(status="time-limit", completed=1, remaining=3)
        document: dict[str, object] = {
            "metadata": {
                "code_sha256": "test-source",
                "helm": "v4.3.0",
                "time_limit_seconds": 540,
                "time_limit_scope": "per strategy per step",
                "valid_inputs": 2,
            },
            "rows": rows,
        }
        if study == "sensitivity":
            document.update(
                status="time-limit" if damage == "sensitivity-incomplete" else "complete",
                pruning_authorized=damage == "sensitivity-pruning",
                mutations=[{"name": "change-message", "status": "rendered", "distance": 2}],
                interactions=[{"status": "rendered", "mixed_difference_l1": 0}],
                sequence=[{"status": "rendered", "cumulative_path_length": 2, "endpoint_displacement": 2}],
            )
            for filename in ("sensitivity.png", "sensitivity.svg", "mutations.json", "chart-inputs.json"):
                (directory / filename).write_bytes(b"x" * 1001)
        if study == "structural-sparsity":
            mapping(document["metadata"]).update(
                status="complete", breadths=[4], depths=[1], placements=["near"], methods=["default"], repeats=1
            )
            rows = [
                {
                    "breadth": 4,
                    "depth": 1,
                    "placement": "near",
                    "strategy": "default",
                    "repeat": 0,
                    "status": "passed",
                    "error": None,
                    "valid_domain": 16,
                    "erroneous_inputs_evaluated": 7,
                    "errors_missed": 0,
                    "value_nodes": 25,
                    "completed": 16,
                    "selected": 16,
                    "remaining": 0,
                }
            ]
            for suffix in ("runtime", "discovery", "analysis", "errors"):
                for extension in ("png", "svg"):
                    (directory / f"structural-sparsity-{suffix}.{extension}").write_bytes(b"x" * 1001)
        if study == "matrix":
            rows = [
                {"structure": structure, "strategy": strategy, "status": "passed"} for structure in STRUCTURES for strategy in STRATEGIES
            ]
        elif study == "pca":
            policies = ("before", "random", "topology", "combined", "filter", "filter-adaptive")
            rows = [
                {
                    "structure": structure,
                    "status": "complete",
                    "strategies": dict.fromkeys(policies, {}),
                    "selected_indices": dict.fromkeys(policies, [0]),
                }
                for structure in STRUCTURES
            ]
        elif study in {"expansion", "nesting"}:
            structures = (
                STRUCTURES
                if study == "expansion"
                else tuple(f"{family}-{profile}" for family in ("uniform", "supported") for profile in ("shallow", "deep", "random"))
            )
            rows = [
                {"structure": structure, "strategy": strategy, "expand_failures": expanded, "status": "complete"}
                for structure in structures
                for strategy in ("before", "random", "topology", "combined", "filter", "filter-adaptive")
                for expanded in (False, True)
            ]
        if damage == f"{study}-missing-aggressive":
            if study == "pca":
                mapping(rows[0]["strategies"]).pop("filter-adaptive")
            else:
                rows = [row for row in rows if row.get("strategy") != "filter-adaptive"]
        document["rows"] = rows
        if study == "sampling":
            document.update(
                status="complete",
                reference={"completed": 2, "remaining": int(damage == "sampling-reference"), "fault_masks": {"a": 0, "b": 1}},
                rows=[{"status": "complete", "sample_size": 1}],
            )
            if damage == "sampling-inventory":
                document["reference"] = {"completed": 2, "remaining": 0, "fault_masks": {"a": 0}}
            for filename in ("chart-parameters.yaml", "sampling-recall.png", "sampling-recall.svg"):
                (directory / filename).write_bytes(b"x" * 1001)
        if study == "calibration-variation":
            calibration_rows = [
                {"case": f"case-{index}", "strategy": strategy, "status": "complete", "trials": 100}
                for index in range(30)
                for strategy in ("filter", "exact", "nearby-0.1", "nearby-0.2", "nearby-0.35", "nearby-0.5")
            ]
            if damage == "calibration-count":
                calibration_rows.pop()
            elif damage == "calibration-trials":
                calibration_rows[0]["trials"] = 99
            elif damage == "calibration-duplicate":
                calibration_rows[-1] = calibration_rows[0]
            document["rows"] = calibration_rows
            (directory / "calibration.json").write_text(
                json.dumps(
                    {
                        "status": "complete",
                        "profiles": [
                            {
                                "case": f"case-{index}",
                                "reference": {"cases": [1]},
                                "evidence": {"reference_renders": 3 if damage == "calibration-reference" else 2},
                            }
                            for index in range(30)
                        ],
                    }
                )
            )
            for filename in ("matrix.csv", "matrix.json", "MATRIX.md", "matching-matrix.png", "profile-variation.png"):
                (directory / filename).write_bytes(b"x" * 1001)
        if study == "filtering":
            mapping(document["metadata"]).update(status="complete", repeats=2)
            load_rows = [
                {
                    "input_fields": fields,
                    "gate_depth": depth,
                    "repeat": repeat,
                    "strategy": method,
                    "status": "passed",
                    "valid_inputs": 2**fields,
                    "planned": 4,
                    "completed": 4,
                    "remaining": 0,
                    "wall_seconds": 3,
                    "planning_seconds": 1,
                    "execution_seconds": 2,
                    "complexity_seconds": 0.5,
                }
                for fields in (6, 7, 8, 9)
                for depth in (1, 3, 5)
                for repeat in range(2)
                for method in ("baseline", "sample-random", "filter", "filter-adaptive")
            ]
            if damage == "filtering-count":
                load_rows.pop()
            elif damage == "filtering-duplicate":
                load_rows[-1] = load_rows[0]
            elif damage == "filtering-timing":
                load_rows[0]["wall_seconds"] = 1
            document["rows"] = load_rows
            for name in ("filtering-runtime", "filtering-planning", "filtering-completed", "filtering-phases"):
                for extension in ("png", "svg"):
                    (directory / f"{name}.{extension}").write_bytes(b"x" * 1001)
        if study == "error-surface":
            axes: dict[str, list[int | float]] = {"depth": list(range(6)), "redundancy": list(range(8)), "clustering": [0, 0.5, 1]}
            mapping(document["metadata"]).update(
                status="complete", input_fields=8, repeats=3, axes=axes, error_rates=list(RATES), methods=list(METHODS)
            )
            surface_rows: list[dict[str, object]] = []
            populations = {}
            for axis, surface_settings in axes.items():
                for value in surface_settings:
                    for rate in RATES:
                        indices = list(range(256 * rate // 100))
                        identity = hashlib.sha256(configuration_key({"failed": indices}).encode()).hexdigest()
                        populations[identity] = indices
                        for repeat in range(3):
                            for method in METHODS:
                                surface_rows.append(
                                    {
                                        "axis": axis,
                                        "axis_value": value,
                                        "error_percent": rate,
                                        "repeat": repeat,
                                        "strategy": method,
                                        "status": "passed",
                                        "valid_domain": 256,
                                        "selected": 256,
                                        "completed": 256,
                                        "remaining": 0,
                                        "initial_selected": 256,
                                        "additional_executed": 0,
                                        "additional_scheduled": 0,
                                        "render_invocations": 256,
                                        "proved_equivalent": 0,
                                        "errors_detected": len(indices),
                                        "error_count": len(indices),
                                        "errors_missed": 0,
                                        "error_recall": 1 if indices else None,
                                        "actual_error_percent": 100 * len(indices) / 256,
                                        "total_seconds": 3,
                                        "execution_seconds": 2,
                                        "planning_seconds": 0.5,
                                        "analysis_seconds": 0.5,
                                        "population_sha256": identity,
                                        "chart_sha256": f"{axis}-{value}",
                                    }
                                )
            if damage == "error-surface-count":
                surface_rows.pop()
            elif damage == "error-surface-zero-recall":
                surface_rows[0]["error_recall"] = 0
            elif damage == "error-surface-chart":
                surface_rows[0]["chart_sha256"] = "modified"
            document.update(rows=surface_rows, populations=populations)
            (directory / "summary.csv").write_text("measured means and ranges")
            for axis in axes:
                for metric in METRICS:
                    for extension in ("png", "svg"):
                        (directory / f"{axis}-{metric.replace('_', '-')}.{extension}").write_bytes(b"x" * 1001)
        (directory / "results.json").write_text(json.dumps(document))
    result = subprocess.run(
        [sys.executable, str(project / "pkg/hypothesis_helm/benchmarking/refresh/recipes/verify-measurements.py"), str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    valid = damage in {None, "censored"}
    assert (result.returncode == 0) == valid, result.stdout + result.stderr
    assert (tmp_path / "measurement-verification.json").exists() == valid


def test_refresh_includes_every_stress_topology(tmp_path: Path) -> None:
    """
    Schedule topology exports from every retained stress recipe without chart copies.

    Args:
        tmp_path (Path): Refresh inventory and 22 retained parameter records.

    Returns:
        None: Each stress step has one distinct graph job pointing at its YAML recipe.
    """
    project = Path(__file__).resolve().parents[3]
    (tmp_path / "graph-source-ready.txt").touch()
    (tmp_path / "topology-inventory.json").write_text("[]")
    cases = tmp_path / "outputs/stress/cases"
    cases.mkdir(parents=True)
    for name, settings in progression(Stress()):
        (cases / f"{name}.yaml").write_text(yamlio.dump({"parameters": {"stress": asdict(settings)}}))
    subprocess.run(
        [sys.executable, str(project / "pkg/hypothesis_helm/benchmarking/refresh/recipes/prepare-fixtures.py"), str(tmp_path)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [sys.executable, str(project / "pkg/hypothesis_helm/benchmarking/refresh/recipes/prepare-topologies.py"), str(tmp_path)],
        check=True,
        capture_output=True,
    )
    records = json.loads((tmp_path / "topology-inventory.json").read_text())
    stress = [record for record in records if record["chart"].startswith("stress/")]
    assert len(stress) == 22
    assert len({record["output"] for record in stress}) == 22
    assert {Path(record["source"]).stem for record in stress} == {name for name, _ in progression(Stress())}
    assert all(Path(record["source"]).is_file() for record in records)
    assert not list(tmp_path.rglob("Chart.yaml"))


def test_publish_groups_studies(tmp_path: Path) -> None:
    """
    Publish performance alongside other studies and keep the benchmark root clear.

    Args:
        tmp_path (Path): Isolated completed refresh and publication destination.

    Returns:
        None: Published paths, retained recipes and checksums use the grouped layout.
    """
    project = Path(__file__).resolve().parents[3]
    recipes = project / "pkg/hypothesis_helm/benchmarking/refresh/recipes"
    run = tmp_path / "refresh"
    run.mkdir()
    for source in recipes.iterdir():
        if source.is_file():
            (run / source.name).write_text("{}\n")
    studies = (
        "performance",
        "discovery",
        "bug-density",
        "sparsity",
        "structure-sparsity",
        "structural-sparsity",
        "matrix",
        "pca",
        "expansion",
        "structure-depth",
        "nesting",
        "stress",
        "sampling",
        "sensitivity",
        "calibration-variation",
        "filtering",
        "error-surface",
    )
    (run / "status.tsv").write_text("".join(f"{name}\t0\n" for name in studies))
    (run / "started-epoch.txt").write_text("0")
    (run / "finished-epoch.txt").write_text("60")
    (run / "retained-fixture-sha256.json").write_text("{}")
    (run / "topology-finished-epoch.txt").write_text("60")
    (run / "topology-retry-finished-epoch.txt").write_text("60")
    (run / "logs").mkdir()
    (run / "logs/performance.log").write_text("complete\n")
    (run / "parameters").mkdir()
    (run / "parameters/standard.yaml").write_text("parameters: {}\n")
    for name in (*studies, "chart-topologies"):
        output = run / "outputs" / name
        output.mkdir(parents=True)
        (output / "results.json").write_text(json.dumps({"study": name}))
    (run / "outputs/chart-topologies/verification.json").write_text("{}")
    subprocess.run([sys.executable, str(recipes / "publish.py"), str(run)], cwd=tmp_path, check=True, capture_output=True)
    published = tmp_path / "pkg/hypothesis_helm/benchmarking/assets"
    assert not (published / "results.json").exists()
    assert not (published / "matrix").exists()
    assert not (published / "studies").exists()
    assert not (published / "parameters").exists()
    assert (published / "fixture/parameters/standard.yaml").read_text() == "parameters: {}\n"
    checksums = json.loads((run / "sha256.json").read_text())
    assert not (published / "refresh/sha256.json").exists()
    assert not (published / "refresh/logs").exists()
    assert not (tmp_path / "studies/chart-topologies/verification.json").exists()
    for name in (*studies, "chart-topologies"):
        path = tmp_path / "studies" / name / "results.json"
        assert json.loads(path.read_text()) == {"study": name}
        assert checksums[str(path.relative_to(tmp_path))] == hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("failure", [None, "verify-topologies.py", "bitnami/finalize.py"])
def test_refresh_scans_follow_published_diagrams(tmp_path: Path, failure: str | None) -> None:
    """
    Run the refresh coordinator with recorded stages and controlled failures.

    Args:
        tmp_path (Path): Fake completed measurements and stage executables.
        failure (str | None): Verification stage that must prevent later repository work.

    Returns:
        None: Diagram publication precedes Bitnami, which precedes Prometheus; failed gates stop the sequence.
    """
    from textwrap import dedent

    from workgraph import OperationQueue

    from hypothesis_helm.benchmarking.refresh.plan import Refresh
    from hypothesis_helm.execution.processes import Processes

    project = Path(__file__).resolve().parents[3]
    root = tmp_path / "refresh"
    (root / "logs").mkdir(parents=True)
    (root / "finished-epoch.txt").touch()
    binary = tmp_path / "bin"
    binary.mkdir()
    interpreter = binary / "python"
    interpreter.write_text(
        f"#!{sys.executable}\n"
        + dedent(
            """
            import os
            import sys
            from pathlib import Path
            source = Path(sys.argv[1])
            stage = f"{source.parent.name}/{source.name}" if source.name == "finalize.py" else source.name
            with Path(os.environ["STAGES"]).open("a") as output:
                output.write(stage + "\\n")
            sys.exit(3 if stage == os.environ.get("FAIL_STAGE") else 0)
            """
        )
    )
    interpreter.chmod(0o755)
    (root / "operations.sh").write_text((project / "pkg/hypothesis_helm/benchmarking/refresh/recipes/operations.sh").read_text())
    profiler = binary / "hypothesis-helm-benchmark"
    profiler.write_text("#!/usr/bin/env bash\nexit 0\n")
    profiler.chmod(0o755)
    for name in ("run-topologies.sh", "retry-topologies.sh"):
        (root / name).write_text(f"printf '%s\\n' {name} >>\"$STAGES\"\n")
    for name in ("bitnami", "prometheus"):
        directory = tmp_path / name
        directory.mkdir()
        (directory / "run.sh").write_text(f"printf '%s\\n' {name} >>\"$STAGES\"\nexit 1\n")
    (root / "repositories.tsv").write_text("".join(f"{name}\t{tmp_path / name}\n" for name in ("bitnami", "prometheus")))
    stages = tmp_path / "stages.txt"
    stages_plan = Refresh(root).operations()
    start = next(index for index, operation in enumerate(stages_plan) if operation.name == "verify-measurements")
    end = next(index for index, operation in enumerate(stages_plan) if operation.name == "update-documentation")
    selected = stages_plan[start:end]
    names = {operation.name for operation in selected}
    queue = OperationQueue(
        [replace(operation, requires=tuple(name for name in operation.requires if name in names)) for operation in selected],
        workers=3,
        owner_factory=Processes,
        directory=root,
        cwd=tmp_path,
        environment=dict(os.environ, PATH=f"{binary}:{os.environ['PATH']}", STAGES=str(stages), FAIL_STAGE=failure or ""),
    )
    if failure:
        with pytest.raises(RuntimeError, match="Operation"):
            queue.run()
    else:
        queue.run()
    visited = stages.read_text().splitlines()
    if failure == "verify-topologies.py":
        assert "publish.py" not in visited and "bitnami" not in visited
        assert not (root / "diagrams-finished-epoch.txt").exists()
    else:
        assert visited.index("verify-topologies.py") < visited.index("publish.py") < visited.index("update-documentation.py")
        assert visited.index("update-documentation.py") < visited.index("bitnami") < visited.index("bitnami/finalize.py")
        assert (root / "diagrams-finished-epoch.txt").exists()
        if failure:
            assert "prometheus" not in visited
        else:
            assert visited.index("bitnami/finalize.py") < visited.index("prometheus") < visited.index("prometheus/finalize.py")
    assert (root / "all-finished-epoch.txt").exists() == (failure is None)


def test_refresh_summaries_replace_numbers_and_preserve_prose(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Refresh marked text twice from changing evidence without depending on old wording.

    Args:
        tmp_path (Path): Publication workspace with synthetic verified ledgers.
        monkeypatch (pytest.MonkeyPatch): Isolate CLI arguments, working directory and PDF presentation.

    Returns:
        None: Counts, budgets, worker settings and links change; unrelated prose and repeatability are preserved.
    """
    import gzip
    import runpy

    project = Path(__file__).resolve().parents[3]
    script = project / "pkg/hypothesis_helm/benchmarking/refresh/recipes/update-documentation.py"
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "refresh"
    output = root / "outputs/performance"
    output.mkdir(parents=True)
    benchmark = tmp_path / "docs/benchmarking/README.md"
    benchmark.parent.mkdir(parents=True)
    benchmark.write_text("My introduction\n<!-- refresh:performance:start -->old wording<!-- refresh:performance:end -->\nKeep this.")
    readme = tmp_path / "README.md"
    readme.write_text(
        "Keep the examples.\n"
        + "\n".join(f"<!-- refresh:{name}:start -->arbitrary old prose<!-- refresh:{name}:end -->" for name in ("bitnami", "prometheus"))
    )
    performance = {
        "metadata": {"helm": "v4.3.0"},
        "points": [
            {
                "observation": "progressive-run",
                "repeat": 0,
                "pruning": enabled,
                "completed": 1000 if enabled else 40,
                "rendered": 20,
                "time_limit_seconds": 540,
            }
            for enabled in (False, True)
        ],
    }
    (output / "results.json").write_text(json.dumps(performance))
    monkeypatch.setattr(sys, "argv", [str(script), str(root), "--benchmarks-only"])
    runpy.run_path(str(script), run_name="__main__")
    assert "1,000 checks" in benchmark.read_text()
    assert "arbitrary old prose" in readme.read_text()
    scans = {name: f"docs/reports/{name}-runs/{name}-charts_1234" for name in ("bitnami", "prometheus")}
    (root / "provenance.json").write_text(json.dumps({"repository_scans": scans}))
    presented: list[str] = []
    monkeypatch.setattr("hypothesis_helm.reporting.repository.write_reports", lambda report, stem, **kwargs: presented.append(str(stem)))
    for directory in scans.values():
        run = Path(directory)
        run.mkdir(parents=True)
        (run / "verification.json").write_text(json.dumps({"all_workers_finished": True, "systemic_execution_failure": False}))
        report: dict[str, object] = {
            "charts": [{"attempts": 12}, {"attempts": 15}],
            "settings": {"filter": True, "workers": 6, "chart_timeout_seconds": 300},
        }
        (run / "scan.json.gz").write_bytes(gzip.compress(json.dumps(report).encode()))
    monkeypatch.setattr(sys, "argv", [str(script), str(root)])
    runpy.run_path(str(script), run_name="__main__")
    assert "**2 Bitnami charts**" in readme.read_text() and "**27 test attempts**" in readme.read_text()
    assert "**6 path workers" in readme.read_text() and "**5-minute budget" in readme.read_text()
    assert all(f"{directory}/README.md" in readme.read_text() for directory in scans.values())
    assert len(presented) == 2
    for directory in scans.values():
        run = Path(directory)
        report["charts"] = [{"attempts": 99}]
        report["settings"] = {"filter": False, "workers": 2, "chart_timeout_seconds": 600}
        (run / "scan.json.gz").write_bytes(gzip.compress(json.dumps(report).encode()))
    runpy.run_path(str(script), run_name="__main__")
    assert "**1 Bitnami chart**" in readme.read_text() and "**99 test attempts**" in readme.read_text()
    assert "no filtering" in readme.read_text() and "**10-minute budget" in readme.read_text()
    assert "Keep the examples." in readme.read_text() and "Keep this." in benchmark.read_text()
    previous = readme.read_text()
    runpy.run_path(str(script), run_name="__main__")
    assert readme.read_text() == previous
    readme.write_text(previous.replace("<!-- refresh:prometheus:end -->", ""))
    benchmark_before = benchmark.read_text()
    with pytest.raises(ValueError, match="summary markers"):
        runpy.run_path(str(script), run_name="__main__")
    assert benchmark.read_text() == benchmark_before


@pytest.mark.parametrize("symbolic", ["false", "true"])
def test_refresh_dispatches_all_studies(tmp_path: Path, symbolic: str) -> None:
    """
    Exercise every study recipe through the operation dispatcher without running measurements.

    Args:
        tmp_path (Path): Isolated recipes and recording executable.
        symbolic (str): Optional symbolic fitting switch.

    Returns:
        None: Every declared study uses an installed command and its own output directory.
    """
    from textwrap import dedent

    from hypothesis_helm.benchmarking.cli import COMMANDS
    from hypothesis_helm.benchmarking.refresh.plan import STUDIES

    project = Path(__file__).resolve().parents[3]
    root = tmp_path / "refresh"
    root.mkdir()
    shutil.copy2(project / "pkg/hypothesis_helm/benchmarking/refresh/recipes/studies.sh", root / "studies.sh")
    binary = tmp_path / "bin"
    binary.mkdir()
    recorder = binary / "hypothesis-helm-benchmark"
    recorder.write_text(
        f"#!{sys.executable}\n"
        + dedent(
            """
            import json
            import os
            import sys
            from pathlib import Path
            with Path(os.environ["RECORDED_COMMANDS"]).open("a") as output:
                output.write(json.dumps(sys.argv[1:]) + "\\n")
            """
        )
    )
    recorder.chmod(0o755)
    commands = tmp_path / "commands.jsonl"
    environment = {
        **os.environ,
        "PATH": f"{binary}{os.pathsep}{os.environ['PATH']}",
        "RECORDED_COMMANDS": str(commands),
        "BENCHMARK_SYMBOLIC_FIT": symbolic,
    }
    for study in STUDIES:
        subprocess.run(
            ["bash", str(project / "pkg/hypothesis_helm/benchmarking/refresh/recipes/operations.sh"), study, str(root)],
            env=environment,
            check=True,
            capture_output=True,
        )
    calls = [json.loads(line) for line in commands.read_text().splitlines()]
    assert len(calls) == len(STUDIES)
    for study, arguments in zip(STUDIES, calls, strict=True):
        command_index = 2 if arguments[0] == "--parameters" else 0
        assert arguments[command_index] in COMMANDS
        assert arguments[arguments.index("--output") + 1] == str(root / "outputs" / study)
    assert ("--symbolic-fit" in calls[-1]) == (symbolic == "true")
    assert (root / "status.tsv").read_text().splitlines() == [f"{study}\t0" for study in STUDIES]

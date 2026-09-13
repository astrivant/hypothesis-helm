"""
Exercise the retained full-refresh recipes with isolated repositories and native workers.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from attrs import asdict

from hypothesis_helm.benchmarking.benchmark_matrix import STRATEGIES
from hypothesis_helm.benchmarking.stress import Stress, progression
from hypothesis_helm.charts import yamlio


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
    run_root = Path("benchmarks/runs/refresh-1234")
    initialized = subprocess.run(
        [sys.executable, str(project / "benchmarks/refresh/initialize.py"), str(run_root)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    assert (tmp_path / "benchmarks/runs/latest-refresh.txt").read_text().strip() == str(run_root)
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
    "damage", [None, "censored", "missing-step", "duplicate", "parameters", "recipe", "plot", "sampling-reference", "sampling-inventory"]
)
def test_refresh_requires_complete_stress_matrix(tmp_path: Path, damage: str | None) -> None:
    """
    Reject incomplete or inconsistent stress results before the refresh publishes them.

    Args:
        tmp_path (Path): Synthetic measurement ledgers for the publication gate.
        damage (str | None): One deliberate corruption, or an intact matrix.

    Returns:
        None: Only the complete 22-step, five-strategy matrix passes verification.
    """
    project = Path(__file__).resolve().parents[3]
    (tmp_path / "provenance.json").write_text(json.dumps({"code_sha256": "test-source"}))
    studies = (
        "performance",
        "discovery",
        "bug-density",
        "sparsity",
        "topology-sparsity",
        "matrix",
        "pca",
        "expansion",
        "topology-depth",
        "nesting",
        "stress",
        "sampling",
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
        document = {
            "metadata": {
                "code_sha256": "test-source",
                "helm": "v4.3.0",
                "time_limit_seconds": 540,
                "time_limit_scope": "per strategy per step",
                "valid_inputs": 2,
            },
            "rows": rows,
        }
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
        (directory / "results.json").write_text(json.dumps(document))
    result = subprocess.run(
        [sys.executable, str(project / "benchmarks/refresh/verify-measurements.py"), str(tmp_path)],
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
        [sys.executable, str(project / "benchmarks/refresh/prepare-fixtures.py"), str(tmp_path)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [sys.executable, str(project / "benchmarks/refresh/prepare-topologies.py"), str(tmp_path)],
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

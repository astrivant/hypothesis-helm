"""
Keep completed refresh operations and measured source intact during recovery.
"""

import hashlib
import json
import subprocess
import sys
from importlib.resources import files
from pathlib import Path
from textwrap import dedent

import pytest
from hypothesis_helm_benchmarking.refresh.resume import remaining, resume


def test_resume_failed_checks_before_source_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Retry preparation against the repaired checkout before freezing measured code.

    Args:
        tmp_path (Path): Workspace with failed checks and no measurements.
        monkeypatch (pytest.MonkeyPatch): Use an isolated checkout for resumed commands.

    Returns:
        None: Repeated failures preserve journals; successful recovery reaches initialization without overwriting artifacts.
    """
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "refresh-1"
    root.mkdir()
    check = tmp_path / "check.py"
    check.write_text(
        dedent(
            """
            import os
            from pathlib import Path
            assert os.environ['PYTHONPATH'] == str(Path.cwd() / 'pkg')
            assert Path('fixed').exists()
            """
        )
    )
    initialize = tmp_path / "initialize.py"
    initialize.write_text(
        dedent(
            """
            from pathlib import Path
            root = Path('refresh-1')
            assert {path.name for path in root.iterdir()} == {'operations.json', 'logs'}
            (root / 'frozen-source/pkg').mkdir(parents=True)
            (root / 'measured-source-hashes.json').write_text('{}')
            """
        )
    )
    records = [
        {
            "name": "dependency-docs",
            "command": [sys.executable, "-c", "raise RuntimeError('completed stage must not repeat')"],
            "requires": [],
            "status": "completed",
            "exit_code": 0,
        },
        {"name": "checks", "command": [sys.executable, str(check)], "requires": ["dependency-docs"], "status": "failed", "exit_code": 1},
        {
            "name": "initialize",
            "command": [sys.executable, str(initialize)],
            "requires": ["checks"],
            "status": "blocked",
            "exit_code": None,
        },
    ]
    journal = root / "operations.json"
    journal.write_text(json.dumps({"operations": records}))
    original = journal.read_bytes()
    resume(journal, 2, dry_run=True)
    assert not (root / "logs").exists()
    with pytest.raises(RuntimeError, match="checks exited"):
        resume(journal, 2)
    retry = next(root.glob("logs/resumed-*/operations.json"))
    retry_contents = retry.read_bytes()
    (tmp_path / "fixed").touch()
    resume(retry, 2)
    assert journal.read_bytes() == original and retry.read_bytes() == retry_contents
    assert (root / "measured-source-hashes.json").is_file()
    assert len(list(root.glob("logs/resumed-*/operations.json"))) == 2
    assert not (root.parent / "full-refresh.lock").exists()


@pytest.mark.parametrize("stage,status", [("initialize", "failed"), ("initialize", "completed"), ("performance", "completed")])
def test_missing_snapshot_cannot_resume_started_measurements(tmp_path: Path, stage: str, status: str) -> None:
    """
    Refuse checkout-based recovery once initialization or a measurement has begun.

    Args:
        tmp_path (Path): Inconsistent workspace with a missing source snapshot.
        stage (str): Stage whose execution makes the measured source mandatory.
        status (str): Recorded stage outcome.

    Returns:
        None: A missing snapshot never silently changes the code used for previous measurements.
    """
    records = [
        {"name": name, "command": [sys.executable, "-c", "pass"], "requires": [], "status": status if name == stage else "blocked"}
        for name in ("initialize", "performance")
    ]
    journal = tmp_path / "operations.json"
    journal.write_text(json.dumps({"operations": records}))
    with pytest.raises(ValueError, match="measured source snapshot"):
        resume(journal, 2, dry_run=True)


def test_resume_retries_only_unfinished_operations(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """
    Continue a failed publication without repeating already completed chart scans.

    Args:
        tmp_path (Path): Saved refresh workspace.
        capsys (pytest.CaptureFixture[str]): Capture the preview inventory.

    Returns:
        None: A fresh continuation journal owns the retried stages and preserves the old one.
    """
    root = tmp_path / "refresh-1"
    source = root / "frozen-source/pkg/example.py"
    source.parent.mkdir(parents=True)
    source.write_text("# measured implementation\n")
    (root / "measured-source-hashes.json").write_text(json.dumps({"pkg/example.py": hashlib.sha256(source.read_bytes()).hexdigest()}))
    journal = root / "operations.json"
    records = [
        {
            "name": "scan",
            "command": [sys.executable, "-c", "raise RuntimeError('must not repeat')"],
            "requires": [],
            "status": "completed",
            "exit_code": 1,
            "allow_failure": True,
        },
        {
            "name": "verify-publication",
            "command": [sys.executable, "-c", "print('verified')"],
            "requires": ["scan"],
            "status": "failed",
            "exit_code": 1,
        },
        {
            "name": "publication-finished",
            "command": [sys.executable, "-c", "print('finished')"],
            "requires": ["verify-publication"],
            "status": "blocked",
            "exit_code": None,
        },
    ]
    journal.write_text(json.dumps({"operations": records}))
    before = journal.read_bytes()
    operations = remaining(journal)
    assert [item.name for item in operations] == ["verify-publication", "publication-finished"]
    assert operations[0].requires == ()
    assert operations[1].requires == ("verify-publication",)
    resume(journal, 2, dry_run=True)
    assert "verify-publication, publication-finished" in capsys.readouterr().out
    assert not list(root.glob("resumed-*"))
    resume(journal, 2)
    assert journal.read_bytes() == before
    resumed = json.loads(next(root.glob("resumed-*/operations.json")).read_text())
    assert all(item["status"] == "completed" for item in resumed["operations"])
    assert not (root.parent / "full-refresh.lock").exists()
    source.write_text("# changed implementation\n")
    with pytest.raises(ValueError, match="Frozen measured source changed"):
        resume(journal, 2)


@pytest.mark.parametrize(
    "stage,outputs", [("matrix", ["outputs/matrix"]), ("profile", ["profiles", "profile-run"]), ("flamegraphs", ["outputs/flamegraphs"])]
)
def test_resume_preserves_partial_attempts_before_retry(tmp_path: Path, stage: str, outputs: list[str]) -> None:
    """
    Restart interrupted measurements without deleting evidence or colliding with stale output.

    Args:
        tmp_path (Path): Saved refresh with partial and successful measurements.
        stage (str): Failed study, profiling, or profile publication operation.
        outputs (list[str]): Directories owned by the failed operation.

    Returns:
        None: Retry sees fresh destinations; successful data and failed-attempt data both survive.
    """
    root = tmp_path / "refresh-1"
    (root / "frozen-source/pkg").mkdir(parents=True)
    (root / "measured-source-hashes.json").write_text("{}")
    completed = root / "outputs/discovery/results.json"
    completed.parent.mkdir(parents=True)
    completed.write_text("completed evidence")
    for relative in outputs:
        path = root / relative / "partial.json"
        path.parent.mkdir(parents=True)
        path.write_text("unfinished evidence")
    script = tmp_path / "retry.py"
    script.write_text(
        "from pathlib import Path\n"
        f"root = Path({str(root)!r})\n"
        f"for relative in {outputs!r}:\n"
        "    target = root / relative\n"
        "    target.mkdir(parents=True, exist_ok=False)\n"
        "    (target / 'complete.json').write_text('new evidence')\n"
    )
    records = [
        {
            "name": "discovery",
            "command": [sys.executable, "-c", "raise Exception()"],
            "requires": [],
            "status": "completed",
            "exit_code": 0,
        },
        {"name": stage, "command": [sys.executable, str(script)], "requires": ["discovery"], "status": "failed", "exit_code": 1},
    ]
    journal = root / "operations.json"
    journal.write_text(json.dumps({"operations": records}))
    resume(journal, 1, dry_run=True)
    assert all((root / relative / "partial.json").exists() for relative in outputs)
    resume(journal, 1)
    archive = next(root.glob("resumed-*/prior-attempts"))
    assert completed.read_text() == "completed evidence"
    for relative in outputs:
        assert (archive / relative / "partial.json").read_text() == "unfinished evidence"
        assert (root / relative / "complete.json").read_text() == "new evidence"


def test_publication_distinguishes_readme_edits_from_changed_measurements(tmp_path: Path) -> None:
    """
    Keep measured files immutable while recording later edits to published study explanations.

    Args:
        tmp_path (Path): Minimal repository and saved refresh evidence.

    Returns:
        None: Editorial changes pass only with the original retained evidence; data changes fail.
    """
    root = tmp_path / "refresh"
    root.mkdir()
    for name in ("README.md", "docs/reports/bitnami.md", "docs/reports/prometheus.md", "docs/benchmarking/README.md"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Documentation\n")
    study = tmp_path / "studies/pca"
    study.mkdir(parents=True)
    (study / "README.md").write_text("Original measured summary\n")
    (study / "plot.png").write_text('{"measured": 42}\n')
    checksums = {str(path.relative_to(tmp_path)): hashlib.sha256(path.read_bytes()).hexdigest() for path in study.iterdir()}
    measured = root / "outputs/pca/README.md"
    measured.parent.mkdir(parents=True)
    measured.write_bytes((study / "README.md").read_bytes())
    (study / "README.md").write_text("Improved explanation linking to [measurements](plot.png)\n")
    (root / "sha256.json").write_text(json.dumps(checksums))
    for name in ("retained-fixture-sha256.json", "measured-source-hashes.json"):
        (root / name).write_text("{}")
    (root / "previous-artifact-inventory.json").write_text("[]")
    (root / "measurement-sha256.json").write_text("{}")
    (root / "provenance.json").write_text('{"repository_scans": {}}')
    flamegraphs = tmp_path / "studies/flamegraphs"
    flamegraphs.mkdir()
    captures = root / "outputs/flamegraphs"
    captures.mkdir(parents=True)
    (captures / "captures.tar.gz").touch()
    figures = [{"name": name, "png": f"{name}.png", "svg": f"{name}.svg"} for name in ("workers-combined", "coordinator-main")]
    for figure in figures:
        for extension in ("png", "svg"):
            (flamegraphs / figure[extension]).touch()
    (captures / "index.json").write_text(json.dumps({"worker_processes": 1, "incomplete_captures": 0, "figures": figures, "captures": 2}))
    recipe = files("hypothesis_helm_benchmarking.refresh").joinpath("recipes/verify-publication.py")
    command = [sys.executable, str(recipe), str(root)]
    subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, check=True)
    report = json.loads((root / "publication-verification.json").read_text())
    assert report["verified_benchmark_artifacts"] == 1
    assert "studies/pca/README.md" in report["editorially_updated_readmes"]
    (study / "plot.png").write_text('{"measured": 999}\n')
    failed = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True)
    assert failed.returncode != 0 and "plot.png" in failed.stderr
    (study / "plot.png").write_text('{"measured": 42}\n')
    measured.write_text("Changed retained measurement summary\n")
    failed = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True)
    assert failed.returncode != 0 and "README.md" in failed.stderr

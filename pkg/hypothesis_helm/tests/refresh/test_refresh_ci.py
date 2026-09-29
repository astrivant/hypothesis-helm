"""
Verify distributed refresh barriers, isolated study logs and complete artifact aggregation.
"""

import json
import os
import sys
from pathlib import Path
from textwrap import dedent

import pytest
from hypothesis_helm_benchmarking.refresh.ci import merge_statuses, phase_operations, run_phase
from hypothesis_helm_benchmarking.refresh.operations import Operation
from hypothesis_helm_benchmarking.refresh.plan import STUDIES, Refresh

from hypothesis_helm.environment import refresh_env
from hypothesis_helm.tests import PROJECT_ROOT


def test_ci_phases_partition_refresh() -> None:
    """
    Cover the full inventory exactly once, keeping study jobs independent and publication ordered.

    Returns:
        None: Matrix jobs have no dependencies on each other, while finalization retains its barriers.
    """
    root = Path(".cache/refresh/refresh-1")
    prepare = phase_operations(root, "prepare")
    studies = [phase_operations(root, "study", name)[0] for name in STUDIES]
    finish = phase_operations(root, "finish")
    assert [item.name for item in (*prepare, *studies, *finish)] == [item.name for item in Refresh(root).operations()]
    assert [item.name for item in prepare] == [
        "compiler-builtins",
        "schema-catalog",
        "native-renderer",
        "dependency-docs",
        "checks",
        "dependencies",
        "initialize",
        "prepare-fixtures",
    ]
    assert all(not item.requires for item in studies)
    assert finish[0].name == "measurements-finished"
    assert not finish[0].requires
    assert next(item for item in finish if item.name == "bitnami").requires == ("diagrams-finished",)
    assert next(item for item in finish if item.name == "prometheus").requires == ("bitnami-finalize",)


def test_pr_graph_phase_verifies_publication_without_repository_scans() -> None:
    """
    Preserve study, topology and publication checks while excluding fresh external repository scans.

    Returns:
        None: PR publication ends with checksum and link verification after summaries are updated.
    """
    operations = phase_operations(Path(".cache/refresh/refresh-1"), "graphs")
    names = {item.name for item in operations}
    assert {"verify-measurements", "verify-topologies", "publish", "update-benchmarks", "flamegraphs"} <= names
    assert not {"bitnami", "prometheus", "bitnami-finalize", "prometheus-finalize"} & names
    assert operations[-1].name == "verify-benchmark-publication"
    assert operations[-1].requires == ("diagrams-finished",)
    assert operations[-1].command[-1] == "--benchmarks-only"
    assert all(set(item.requires) <= names for item in operations)


def test_split_preparation_preserves_all_operations() -> None:
    """
    Split source generation from initialization at the externally sharded check barrier.

    Returns:
        None: CI preserves the local preparation order and runs every operation exactly once.
    """
    root = Path(".cache/refresh/refresh-1")
    full = phase_operations(root, "prepare")
    inputs = phase_operations(root, "prepare-inputs")
    finalize = phase_operations(root, "prepare-finalize")
    assert [item.name for item in inputs] == ["compiler-builtins", "schema-catalog", "native-renderer", "dependency-docs"]
    assert [item.name for item in finalize] == ["dependencies", "initialize", "prepare-fixtures"]
    assert [item.name for item in full] == [*[item.name for item in inputs], "checks", *[item.name for item in finalize]]
    for operations in (inputs, finalize):
        assert not operations[0].requires
        assert all(set(item.requires) <= {operation.name for operation in operations} for item in operations)


def test_split_preparation_retains_journals(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Preserve both preparation journals while keeping initialization's workspace guard intact.

    Args:
        tmp_path (Path): Isolated checkout and generated inputs artifact.
        monkeypatch (pytest.MonkeyPatch): Replace expensive recipes with a native initialization probe.

    Returns:
        None: Finalization requires restored input evidence and publishes study outputs afterward.
    """
    root = Path(".cache/refresh/refresh-1")
    probe = tmp_path / "probe.py"
    probe.write_text(
        "import sys\nfrom pathlib import Path\n"
        "root = Path(sys.argv[1])\n"
        "assert {path.name for path in root.iterdir()} <= {'logs'}\n"
        "if sys.argv[2] == 'prepare-finalize':\n"
        "    (root / 'provenance.json').write_text('{}')\n"
    )

    def operations(directory: Path, phase: str, study: str | None = None) -> tuple[Operation, ...]:
        """
        Run a small native command at each real phase boundary.

        Args:
            directory (Path): Shared refresh root.
            phase (str): Preparation phase under test.
            study (str | None): Unused study selector.

        Returns:
            tuple[Operation, ...]: One probe preserving real queue and artifact behavior.
        """
        return (Operation(phase, (sys.executable, str(probe), str(directory), phase)),)

    monkeypatch.chdir(tmp_path)
    output = tmp_path / "github-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    refresh_env()
    monkeypatch.setattr("hypothesis_helm_benchmarking.refresh.ci.phase_operations", operations)
    with pytest.raises(ValueError, match="generated inputs artifact"):
        run_phase(root, "prepare-finalize", None, 1)
    run_phase(root, "prepare-inputs", None, 1)
    journal = root / "logs/prepare-inputs/operations.json"
    previous = journal.read_bytes()
    assert not (root / "provenance.json").exists()
    assert f"root={root}\n" in output.read_text()
    run_phase(root, "prepare-finalize", None, 1)
    assert journal.read_bytes() == previous
    assert (root / "logs/prepare-finalize/operations.json").is_file()
    assert "ci_run_id" in json.loads((root / "provenance.json").read_text())


def test_preparation_excludes_sharded_studies_from_serial_matrix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Schedule dedicated sharded studies only through their own workflow jobs.

    Args:
        tmp_path (Path): Prepared workspace and GitHub output file.
        monkeypatch (pytest.MonkeyPatch): Skip preparation work while exercising real matrix publication.

    Returns:
        None: Every study runs through exactly one serial or sharded workflow path.
    """
    root = Path(".cache/refresh/refresh-1")
    (tmp_path / root).mkdir(parents=True)
    (tmp_path / root / "provenance.json").write_text("{}")
    output = tmp_path / "github-output"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    refresh_env()
    monkeypatch.setattr("hypothesis_helm_benchmarking.refresh.ci.OperationQueue.run", lambda self: None)
    run_phase(root, "prepare", None, 1)
    values = dict(line.split("=", 1) for line in output.read_text().splitlines())
    assert values["root"] == str(root)
    assert json.loads(values["matrix"])["study"] == [
        name for name in STUDIES if name not in {"error-surface", "stress", "structural-sparsity"}
    ]


@pytest.mark.parametrize("damage", [None, "missing", "failed", "duplicate", "unexpected", "mislabeled"])
def test_merge_ci_statuses(tmp_path: Path, damage: str | None) -> None:
    """
    Reject incomplete or ambiguous matrix results before creating a publication ledger.

    Args:
        tmp_path (Path): Downloaded study status directory.
        damage (str | None): Status corruption, or None for a successful matrix.

    Returns:
        None: Only a complete successful matrix yields the combined ledger.
    """
    directory = tmp_path / "statuses"
    directory.mkdir()
    for name in STUDIES:
        (directory / f"{name}.tsv").write_text(f"{name}\t0\n")
    first = directory / f"{STUDIES[0]}.tsv"
    if damage == "missing":
        first.unlink()
    elif damage == "failed":
        first.write_text(f"{STUDIES[0]}\t1\n")
    elif damage == "duplicate":
        first.write_text(first.read_text() * 2)
    elif damage == "unexpected":
        (directory / "unknown.tsv").write_text("unknown\t0\n")
    elif damage == "mislabeled":
        first.write_text("different-study\t0\n")
    if damage:
        with pytest.raises(ValueError):
            merge_statuses(tmp_path)
        assert not (tmp_path / "status.tsv").exists()
    else:
        merge_statuses(tmp_path)
        assert (tmp_path / "status.tsv").read_text() == "".join(f"{name}\t0\n" for name in STUDIES)


@pytest.mark.parametrize("exit_code", [0, 3])
def test_ci_study_retains_status_and_logs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exit_code: int, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    Retain matrix diagnostics on success and failure using a native owned process.

    Args:
        tmp_path (Path): Runner checkout with a restored preparation snapshot.
        monkeypatch (pytest.MonkeyPatch): Isolate working directory and executable lookup.
        exit_code (int): Native study outcome.
        capsys (pytest.CaptureFixture[str]): Coordinator stdout and stderr capture.

    Returns:
        None: The coordinator copies study status and logs to artifact locations even on failure.
    """
    project = PROJECT_ROOT
    root = Path(".cache/refresh/refresh-1")
    restored = tmp_path / root
    (restored / "logs").mkdir(parents=True)
    (restored / "provenance.json").write_text("{}")
    (restored / "verify-measurements.py").write_text("# This test isolates status transport and live logs.\n")
    for name in ("operations.sh", "studies.sh"):
        (restored / name).write_text((project / "pkg/hypothesis_helm_benchmarking/refresh/recipes" / name).read_text())
    binary = tmp_path / "bin"
    binary.mkdir()
    executable = binary / "hypothesis-helm-benchmark"
    executable.write_text(
        dedent(
            f"""
            #!/usr/bin/env bash
            echo 'native study diagnostic'
            exit {exit_code}
            """
        ).lstrip()
    )
    executable.chmod(0o755)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", f"{binary}{os.pathsep}{os.environ['PATH']}")
    refresh_env()
    if exit_code:
        with pytest.raises(RuntimeError):
            run_phase(root, "study", "performance", 1)
    else:
        run_phase(root, "study", "performance", 1)
    assert (restored / "statuses/performance.tsv").read_text() == f"performance\t{exit_code}\n"
    assert "native study diagnostic" in (restored / "logs/performance.log").read_text()
    assert "[performance] native study diagnostic" in capsys.readouterr().err
    assert json.loads((restored / "ci-jobs/performance/operations.json").read_text())

"""
Verify distributed refresh barriers, isolated study logs and complete artifact aggregation.
"""

import json
import os
from pathlib import Path
from textwrap import dedent

import pytest
from hypothesis_helm_benchmarking.refresh.ci import merge_statuses, phase_operations, run_phase
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

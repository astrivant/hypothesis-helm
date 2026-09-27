"""Check branch reports, main-only commits and invalid-evidence handling."""

import os
import subprocess
from pathlib import Path
from textwrap import dedent

import pytest

from hypothesis_helm.tests import PROJECT_ROOT
from hypothesis_helm.tests.integrations.test_pr_benchmarks import git


@pytest.mark.parametrize("ref", ["refs/heads/main", "refs/heads/feature"])
@pytest.mark.parametrize("repository", ["bitnami", "prometheus"])
@pytest.mark.parametrize("status", [0, 1, 2])
def test_repository_publication_keeps_raw_data_local(tmp_path: Path, status: int, repository: str, ref: str) -> None:
    """
    Publish final reports to a local remote only after acceptable aggregation.

    Args:
        tmp_path (Path): Isolated Git repository and fake Poetry executable.
        status (int): Aggregate success, chart findings or invalid evidence.
        repository (str): Requested chart source and report directory.
        ref (str): Main or a PR head branch selected for manual execution.

    Returns:
        None: Main-only publication commits reports and excludes raw observations.
    """
    remote, project, binaries = (tmp_path / name for name in ("remote", "project", "bin"))
    for path in (remote, project, binaries):
        path.mkdir()
    git(remote, "init", "--bare", "--initial-branch=main")
    git(project, "init", "--initial-branch=main")
    (project / "README.md").write_text("Initial reports\n")
    git(project, "add", "README.md")
    git(project, "commit", "-m", "initial")
    git(project, "remote", "add", "origin", str(remote))
    git(project, "push", "origin", "main")
    original = git(project, "rev-parse", "HEAD")
    poetry = binaries / "poetry"
    poetry.write_text(
        dedent(f"""
        #!/usr/bin/env bash
        set -eu
        if [[ "$2" == hypothesis-helm ]]; then
            printf '%s\\n' "$@" >aggregate-args.txt
            exit {status}
        fi
        mkdir -p docs/reports/{repository}
        printf 'Final report\\n' >docs/reports/{repository}/report.md
        printf 'Raw data\\n' >docs/reports/{repository}/raw.json
        printf 'Docs\\n' >docs/README.md
        """).lstrip()
    )
    poetry.chmod(0o755)
    environment = {
        **os.environ,
        "PATH": f"{binaries}:{os.environ['PATH']}",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": ref,
        "SCAN_RUN_ID": "test-run",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
    }
    script = str(PROJECT_ROOT / ".github/repository-report.sh")
    result = subprocess.run(["bash", script, repository], cwd=project, env=environment, capture_output=True, text=True, timeout=20)
    assert result.returncode == (2 if status == 2 else 0), result.stderr
    arguments = (project / "aggregate-args.txt").read_text().splitlines()
    assert arguments[arguments.index("--shards") + 1] == "40"
    if status == 2:
        assert git(project, "rev-parse", "HEAD") == original
    elif ref != "refs/heads/main":
        assert git(project, "rev-parse", "HEAD") == original
        assert (project / f"docs/reports/{repository}/report.md").is_file()
        assert "report commits are restricted to main" in result.stdout
    else:
        assert f"docs/reports/{repository}/report.md" in git(project, "ls-files")
        assert "raw.json" not in git(project, "ls-files")
        assert git(remote, "rev-parse", "main") == git(project, "rev-parse", "HEAD")
    rejected = subprocess.run(
        ["bash", script, repository], cwd=project, env={**environment, "GITHUB_REF": "refs/pull/1/merge"}, capture_output=True, timeout=20
    )
    assert rejected.returncode == 2

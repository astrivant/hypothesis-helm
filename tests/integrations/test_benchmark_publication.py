"""
Exercise benchmark publication against moving synthetic Git branches.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml


def git(root: Path, environment: dict[str, str], *arguments: str) -> str:
    """
    Run one Git operation in an isolated synthetic repository.

    Args:
        root (Path): Temporary repository or directory.
        environment (dict[str, str]): Isolated test-only environment.
        *arguments (str): Git arguments in command order.

    Returns:
        str: Stripped command output.
    """
    result = subprocess.run(["git", *arguments], cwd=root, env=environment, capture_output=True, text=True, check=True, timeout=30)
    return result.stdout.strip()


@pytest.fixture
def benchmark_repository(tmp_path: Path) -> tuple[Path, Path, Path, str, dict[str, str]]:
    """
    Prepare an immutable source checkout and a separate writer for its remote branch.

    Args:
        tmp_path (Path): Disposable fixture directory.

    Returns:
        tuple[Path, Path, Path, str, dict[str, str]]: Measured checkout, writer, bare remote, source SHA, and environment.
    """
    project = Path(__file__).resolve().parents[2]
    binary = tmp_path / "bin"
    binary.mkdir()
    (binary / "gh").symlink_to(project / "tests/integrations/fixtures/benchmark-gh")
    environment = {
        "PATH": f"{binary}:{os.environ['PATH']}",
        "HOME": str(tmp_path),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "Fixture Author",
        "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_NAME": "Fixture Author",
        "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        "GIT_TERMINAL_PROMPT": "0",
        "GITHUB_REPOSITORY": "example/example",
        "GITHUB_REF": "refs/heads/feature",
        "GITHUB_RUN_ID": "123",
        "GITHUB_SERVER_URL": "https://example.invalid",
        "GITHUB_OUTPUT": str(tmp_path / "outputs"),
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary"),
        "BENCHMARK_GH_METADATA": str(tmp_path / "metadata.json"),
        "PR_NUMBER": "15",
        "DEFAULT_BRANCH": "main",
    }
    remote = tmp_path / "remote.git"
    checkout = tmp_path / "measured"
    writer = tmp_path / "writer"
    checkout.mkdir()
    git(tmp_path, environment, "init", "--bare", str(remote))
    git(checkout, environment, "init", "-b", "main")
    (checkout / "pkg").mkdir()
    (checkout / "pkg/component.py").write_text("value = 1\n")
    (checkout / "docs/benchmarking").mkdir(parents=True)
    (checkout / "README.md").write_text("# Project\n\nOriginal introduction.\n")
    (checkout / "studies").mkdir()
    (checkout / "studies/report.md").write_text("Original report.\n")
    git(checkout, environment, "add", ".")
    git(checkout, environment, "commit", "-m", "Synthetic source")
    source = git(checkout, environment, "rev-parse", "HEAD")
    git(checkout, environment, "branch", "feature")
    git(checkout, environment, "remote", "add", "origin", str(remote))
    git(checkout, environment, "push", "origin", "main", "feature")
    git(tmp_path, environment, "clone", "--quiet", "--branch", "feature", str(remote), str(writer))
    git(checkout, environment, "checkout", "--detach", source)
    environment["GITHUB_SHA"] = source
    return checkout, writer, remote, source, environment


def publication(
    checkout: Path, writer: Path, environment: dict[str, str], changed_path: str, changed_text: str
) -> subprocess.CompletedProcess[str]:
    """
    Advance a synthetic PR branch and run the current benchmark publication script.

    Args:
        checkout (Path): Original measured checkout.
        writer (Path): Independent branch writer.
        environment (dict[str, str]): Synthetic provider and Git environment.
        changed_path (str): Branch file to change after measurement.
        changed_text (str): New complete file content.

    Returns:
        subprocess.CompletedProcess[str]: Bounded process output and exit status.
    """
    project = Path(__file__).resolve().parents[2]
    (writer / changed_path).write_text(changed_text)
    git(writer, environment, "add", changed_path)
    git(writer, environment, "commit", "-m", "Advance the branch")
    git(writer, environment, "push", "origin", "feature")
    advanced = git(writer, environment, "rev-parse", "HEAD")
    metadata = {
        "state": "open",
        "draft": False,
        "head": {"sha": advanced, "ref": "feature", "repo": {"full_name": "example/example"}},
        "base": {"sha": "0" * 40, "ref": "main", "repo": {"full_name": "example/example"}},
    }
    Path(environment["BENCHMARK_GH_METADATA"]).write_text(json.dumps(metadata))
    (checkout / "studies/report.md").write_text("Measured report.\n")
    return subprocess.run(
        ["bash", str(project / ".github/pr-benchmarks.sh"), "commit"],
        cwd=checkout,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def test_documentation_only_advance_preserves_newer_work(
    benchmark_repository: tuple[Path, Path, Path, str, dict[str, str]],
) -> None:
    """
    Publish original measurements on a later branch without discarding its independent documentation.

    Args:
        benchmark_repository (tuple[Path, Path, Path, str, dict[str, str]]): Isolated Git and provider fixture.

    Returns:
        None: The pushed commit retains both changes and identifies the measured source.
    """
    checkout, writer, remote, source, environment = benchmark_repository
    result = publication(checkout, writer, environment, "README.md", "# Project\n\nNewer introduction.\n")
    assert result.returncode == 0, result.stdout + result.stderr
    output = Path(environment["GITHUB_OUTPUT"]).read_text()
    assert "publication=branch\n" in output
    pushed = git(remote, environment, "rev-parse", "refs/heads/feature")
    assert f"sha={pushed}\n" in output
    assert git(remote, environment, "show", f"{pushed}:README.md") == "# Project\n\nNewer introduction."
    assert git(remote, environment, "show", f"{pushed}:studies/report.md") == "Measured report."
    assert source in git(remote, environment, "show", f"{pushed}:docs/benchmarking/benchmark-source.md")
    git(remote, environment, "merge-base", "--is-ancestor", git(writer, environment, "rev-parse", "HEAD"), pushed)


@pytest.mark.parametrize(
    ("changed_path", "changed_text", "reason"),
    [
        ("pkg/component.py", "value = 2\n", "Measured inputs changed"),
        ("studies/report.md", "Concurrent report.\n", "Generated outputs conflict"),
    ],
)
def test_incompatible_advance_retains_measured_artifacts(
    benchmark_repository: tuple[Path, Path, Path, str, dict[str, str]], changed_path: str, changed_text: str, reason: str
) -> None:
    """
    Preserve the newer branch and report the original source when safe publication is impossible.

    Args:
        benchmark_repository (tuple[Path, Path, Path, str, dict[str, str]]): Isolated Git and provider fixture.
        changed_path (str): Concurrently changed file.
        changed_text (str): New branch content.
        reason (str): Expected bounded fallback diagnostic.

    Returns:
        None: The branch is unchanged and the measured output remains in the runner checkout.
    """
    checkout, writer, remote, source, environment = benchmark_repository
    result = publication(checkout, writer, environment, changed_path, changed_text)
    assert result.returncode == 0, result.stdout + result.stderr
    assert reason in result.stdout
    assert f"sha={source}\npublication=artifacts\n" in Path(environment["GITHUB_OUTPUT"]).read_text()
    assert git(remote, environment, "rev-parse", "refs/heads/feature") == git(writer, environment, "rev-parse", "HEAD")
    assert (checkout / "studies/report.md").read_text() == "Measured report.\n"


def test_every_refresh_checkout_uses_the_immutable_event_commit() -> None:
    """
    Bind every benchmark job to the same event commit without changing the dependency graph.

    Returns:
        None: All refresh checkouts select the event SHA and publication has complete Git history.
    """
    project = Path(__file__).resolve().parents[2]
    workflow = yaml.safe_load((project / ".github/workflows/stage-measure.yml").read_text())
    jobs = workflow["jobs"]
    refresh = [job for name, job in jobs.items() if name.startswith("refresh-")]
    checkouts = [step for job in refresh for step in job.get("steps", []) if step.get("uses", "").startswith("actions/checkout@")]
    assert len(checkouts) == 12
    assert all(step["with"]["ref"] == "${{ github.sha }}" for step in checkouts)
    finish = jobs["refresh-finish"]
    checkout = next(step for step in finish["steps"] if step.get("uses", "").startswith("actions/checkout@"))
    assert checkout["with"]["fetch-depth"] == 0

"""
Exercise PR benchmark validation and graph commits against isolated Git repositories.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

from hypothesis_helm.tests import PROJECT_ROOT

SCRIPT = PROJECT_ROOT / ".github/pr-benchmarks.sh"


def git(directory: Path, *arguments: str) -> str:
    """
    Run Git without inheriting signing, hooks or repository-specific user configuration.

    Args:
        directory (Path): Isolated checkout or bare repository.
        *arguments (str): Git operation and explicit arguments.

    Returns:
        str: Standard output from a successful Git operation.
    """
    return subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", *arguments],
        cwd=directory,
        env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"},
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def checkout(tmp_path: Path) -> tuple[Path, Path, dict[str, str]]:
    """
    Create an unpublished PR checkout and stub only GitHub's network calls.

    Args:
        tmp_path (Path): Isolated repository, remote, metadata and executable directory.

    Returns:
        tuple[Path, Path, dict[str, str]]: Checkout, bare remote and script environment.
    """
    work, remote, binary = (tmp_path / name for name in ("work", "remote.git", "bin"))
    for path in (work, remote, binary):
        path.mkdir()
    git(remote, "init", "--bare")
    git(work, "init", "-b", "feature")
    (work / "studies/demo").mkdir(parents=True)
    (work / "README.md").write_text("Original summary\n")
    (work / "studies/demo/plot.png").write_bytes(b"old graph")
    (work / "studies/demo/data.json").write_text("{}")
    git(work, "add", ".")
    git(work, "commit", "-m", "Initial source")
    git(work, "remote", "add", "origin", str(remote))
    git(work, "push", "origin", "feature")
    sha = git(work, "rev-parse", "HEAD")
    metadata = {
        "state": "open",
        "draft": False,
        "head": {"repo": {"full_name": "owner/project"}, "sha": sha, "ref": "feature"},
        "base": {"repo": {"full_name": "owner/project"}, "sha": "b" * 40, "ref": "main"},
    }
    (work / "pr.json").write_text(json.dumps(metadata))
    executable = binary / "gh"
    executable.write_text(
        dedent(f"""
            #!{sys.executable}
            import json
            import sys
            from pathlib import Path
            with Path('gh-calls.jsonl').open('a') as output:
                output.write(json.dumps(sys.argv[1:]) + '\\n')
            if sys.argv[1:3] == ['api', 'repos/owner/project/pulls/123']:
                print(Path('pr.json').read_text())
            """).lstrip()
    )
    executable.chmod(0o755)
    environment = {
        **os.environ,
        "PATH": f"{binary}{os.pathsep}{os.environ['PATH']}",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GITHUB_REPOSITORY": "owner/project",
        "GITHUB_SHA": sha,
        "GITHUB_REF": "refs/heads/feature",
        "GITHUB_SERVER_URL": "https://github.com",
        "GITHUB_RUN_ID": "42",
        "GITHUB_OUTPUT": str(work / "outputs"),
        "PR_NUMBER": "123",
        "DEFAULT_BRANCH": "main",
    }
    return work, remote, environment


@pytest.mark.parametrize("damage", [None, "head", "base", "fork", "closed", "draft", "main", "number"])
def test_request_rejects_stale_or_ineligible_prs(checkout: tuple[Path, Path, dict[str, str]], damage: str | None) -> None:
    """
    Bind permission to an open PR's exact head and, when supplied, its original base.

    Args:
        checkout (tuple[Path, Path, dict[str, str]]): Isolated Git and GitHub fixtures.
        damage (str | None): Ineligible request variant, or None for a valid manual run.

    Returns:
        None: Invalid requests cannot emit a pending benchmark status or usable outputs.
    """
    work, _, environment = checkout
    metadata = json.loads((work / "pr.json").read_text())
    if damage == "head":
        metadata["head"]["sha"] = "c" * 40
    elif damage == "base":
        environment["EXPECTED_BASE_SHA"] = "c" * 40
    elif damage == "fork":
        metadata["head"]["repo"]["full_name"] = "other/fork"
    elif damage == "closed":
        metadata["state"] = "closed"
    elif damage == "draft":
        metadata["draft"] = True
    elif damage == "main":
        environment["GITHUB_REF"] = "refs/heads/main"
    elif damage == "number":
        environment["PR_NUMBER"] = ""
    (work / "pr.json").write_text(json.dumps(metadata))
    result = subprocess.run(["bash", str(SCRIPT), "validate"], cwd=work, env=environment, capture_output=True, text=True)
    if damage:
        assert result.returncode != 0
        assert not (work / "outputs").exists()
        if (work / "gh-calls.jsonl").exists():
            assert "statuses/" not in (work / "gh-calls.jsonl").read_text()
    else:
        assert result.returncode == 0, result.stderr
        assert f"sha={environment['GITHUB_SHA']}" in (work / "outputs").read_text()
        assert "state=pending" in (work / "gh-calls.jsonl").read_text()


@pytest.mark.parametrize("changed", [False, True])
def test_publication_commits_only_final_outputs_and_rechecks_ci(checkout: tuple[Path, Path, dict[str, str]], changed: bool) -> None:
    """
    Keep raw data and unrelated files local while committing graphs to the measured branch.

    Args:
        checkout (tuple[Path, Path, dict[str, str]]): Isolated Git and GitHub fixtures.
        changed (bool): Whether the benchmark produced different final publications.

    Returns:
        None: Changed graphs start fresh CI; unchanged outputs preserve the tested commit without an empty commit.
    """
    work, remote, environment = checkout
    if changed:
        (work / "studies/demo/plot.png").unlink()
        (work / "studies/demo/new.svg").write_text("<svg />")
        (work / "README.md").write_text("Updated measured summary\n")
    (work / "studies/demo/data.json").write_text('{"fresh": true}')
    (work / "unrelated.txt").write_text("Do not publish")
    result = subprocess.run(["bash", str(SCRIPT), "commit"], cwd=work, env=environment, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    sha = git(remote, "rev-parse", "refs/heads/feature")
    assert (sha != environment["GITHUB_SHA"]) is changed
    assert (work / "outputs").read_text() == f"sha={sha}\n"
    assert ('"workflow", "run", "ci.yml"' in (work / "gh-calls.jsonl").read_text()) is changed
    assert git(remote, "show", f"{sha}:studies/demo/data.json") == "{}"
    if changed:
        assert set(git(work, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").splitlines()) == {
            "README.md",
            "studies/demo/new.svg",
            "studies/demo/plot.png",
        }


def test_graph_push_does_not_overwrite_a_concurrent_commit(checkout: tuple[Path, Path, dict[str, str]]) -> None:
    """
    Reject a push even when GitHub metadata has not yet reflected a concurrent branch update.

    Args:
        checkout (tuple[Path, Path, dict[str, str]]): Isolated Git and GitHub fixtures.

    Returns:
        None: The newer remote commit survives and no successful result or follow-up CI is emitted.
    """
    work, remote, environment = checkout
    git(work, "commit", "--allow-empty", "-m", "Concurrent edit")
    newer = git(work, "rev-parse", "HEAD")
    git(work, "push", "origin", "feature")
    git(work, "reset", "--hard", environment["GITHUB_SHA"])
    (work / "studies/demo/plot.png").write_bytes(b"new graph")
    result = subprocess.run(["bash", str(SCRIPT), "commit"], cwd=work, env=environment, capture_output=True, text=True)
    assert result.returncode != 0
    assert git(remote, "rev-parse", "refs/heads/feature") == newer
    assert not (work / "outputs").exists()
    assert '"workflow", "run"' not in (work / "gh-calls.jsonl").read_text()

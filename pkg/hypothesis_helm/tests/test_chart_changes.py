"""
Verify Git comparison windows and conservative completed-chart reuse.
"""

import argparse
import importlib
import json
import os
import time
from pathlib import Path

import pytest

from hypothesis_helm.charts.cache import RETENTION_SECONDS, ChartCache
from hypothesis_helm.charts.changes import MINIMAL_TRAILER, chart_changed, comparison, git
from hypothesis_helm.cli import main


def commit(root: Path, filename: str, content: str, message: str = "Source update") -> str:
    """
    Commit a single fixture file without relying on global Git identity.

    Args:
        root (Path): Fixture repository.
        filename (str): Relative file path.
        content (str): New file contents.
        message (str): Commit message including optional trailer.

    Returns:
        str: New commit SHA.
    """
    target = root / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    git(root, "add", "--", filename)
    git(root, "commit", "-m", message)
    return git(root, "rev-parse", "HEAD").strip()


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Create two charts and a later unrelated trunk commit.

    Args:
        tmp_path (Path): Isolated checkout parent.
        monkeypatch (pytest.MonkeyPatch): Remove inherited CI settings affecting this fixture.

    Returns:
        Path: Repository whose current source charts match its parent.
    """
    for name in tuple(os.environ):
        if name.startswith(("GITHUB_", "CI_", "CIRCLE_", "HYPOTHESIS_HELM_")):
            monkeypatch.delenv(name)
    root = tmp_path / "repository"
    root.mkdir()
    git(root, "init", "-b", "main")
    git(root, "config", "user.name", "Fixture")
    git(root, "config", "user.email", "fixture@example.invalid")
    git(root, "config", "commit.gpgsign", "false")
    for name in ("a", "b"):
        commit(root, f"{name}/Chart.yaml", f"apiVersion: v2\nname: {name}\nversion: 1.0.0\n")
        commit(root, f"{name}/values.yaml", "enabled: true\n")
    commit(root, "README.md", "Documentation")
    return root


def test_trunk_skips_generated_tip_only(repository: Path) -> None:
    """
    Keep the source change visible across a generated minimal-values commit.

    Args:
        repository (Path): Trunk fixture with two charts.

    Returns:
        None: Automatic windows are one or two parents and explicit overrides win.
    """
    before = git(repository, "rev-parse", "HEAD").strip()
    commit(repository, "a/values.yaml", "enabled: false\n")
    ordinary = comparison(repository, environment={"HH_COMMIT_MINIMAL_VALUES": "true"})
    assert ordinary["base_ref"] == "HEAD^"
    assert ordinary["base_commit"] == before
    commit(repository, "a/values-minimal.yaml", "enabled: false\n", f"Generated values\n\n{MINIMAL_TRAILER}")
    report = comparison(repository, environment={})
    assert report["base_ref"] == "HEAD~2"
    assert report["base_commit"] == before
    assert chart_changed(repository / "a", report)
    assert not chart_changed(repository / "b", report)
    paths = report["changed_files"]
    assert isinstance(paths, list)
    assert set(paths) == {"a/values.yaml", "a/values-minimal.yaml"}
    assert comparison(repository, "HEAD^", environment={})["base_ref"] == "HEAD^"
    assert comparison(repository, environment={"HYPOTHESIS_HELM_BASE_REF": "HEAD~3"})["base_ref"] == "HEAD~3"
    commit(repository, "README.md", "Another change")
    assert comparison(repository, environment={})["base_ref"] == "HEAD^"


@pytest.mark.parametrize("provider", ["github", "gitlab", "circle"])
def test_ci_branch_selection(repository: Path, provider: str) -> None:
    """
    Use provider branch metadata in detached checkouts and PR target merge bases.

    Args:
        repository (Path): Git fixture.
        provider (str): CI provider whose variables are supplied.

    Returns:
        None: Trunk uses its parent; feature comparisons exclude target-only changes.
    """
    baseline = git(repository, "rev-parse", "HEAD").strip()
    git(repository, "checkout", "-b", "feature")
    commit(repository, "a/values.yaml", "enabled: false\n")
    git(repository, "checkout", "main")
    commit(repository, "b/values.yaml", "enabled: false\n")
    git(repository, "checkout", "--detach", "feature")
    environment = {
        "github": {"GITHUB_HEAD_REF": "feature", "GITHUB_BASE_REF": "main", "GITHUB_WORKSPACE": str(repository)},
        "gitlab": {"CI_MERGE_REQUEST_TARGET_BRANCH_NAME": "main", "CI_MERGE_REQUEST_DIFF_BASE_SHA": baseline},
        "circle": {"CIRCLE_BRANCH": "feature", "HYPOTHESIS_HELM_BASE_REF": "main"},
    }[provider]
    report = comparison(repository, environment=environment)
    assert report["base_commit"] == baseline
    assert report["changed_files"] == ["a/values.yaml"]
    branch_variable = {"github": "GITHUB_REF_NAME", "gitlab": "CI_COMMIT_BRANCH", "circle": "CIRCLE_BRANCH"}[provider]
    report = comparison(repository, environment={branch_variable: "trunk", "CI_COMMIT_BEFORE_SHA": "unusable"})
    assert report["base_ref"] == "HEAD^"
    assert report["status"] == "resolved"


def test_git_fallbacks_and_worktree_changes(repository: Path, tmp_path: Path) -> None:
    """
    Retain missing-history, deleted, staged, untracked and ancestor gitlink changes.

    Args:
        repository (Path): Git fixture.
        tmp_path (Path): Unrelated CI project location.

    Returns:
        None: Missing comparisons never suppress tests and worktree edits remain visible.
    """
    missing = comparison(repository, "missing-ref", environment={})
    assert missing["status"] == "unavailable"
    assert chart_changed(repository / "a", missing)
    report = comparison(repository, environment={"GITHUB_WORKSPACE": str(tmp_path), "GITHUB_BASE_REF": "missing-ref"})
    assert report["base_ref"] == "HEAD^"
    (repository / "a/values.yaml").unlink()
    (repository / "a/new.yaml").write_text("new: true")
    (repository / "b/values.yaml").write_text("staged: true")
    git(repository, "add", "b/values.yaml")
    report = comparison(repository, environment={})
    paths = report["changed_files"]
    assert isinstance(paths, list)
    assert {"a/new.yaml", "a/values.yaml", "b/values.yaml"} <= set(paths)
    assert chart_changed(repository / "a/nested", {**report, "changed_files": ["a"]})
    assert chart_changed(tmp_path / "elsewhere", report)
    git(repository, "checkout", "--orphan", "new-main")
    git(repository, "commit", "-m", MINIMAL_TRAILER)
    report = comparison(repository, environment={"CI_COMMIT_BRANCH": "main"})
    assert report["base_ref"] == "HEAD~2"
    assert report["status"] == "unavailable"


def test_chart_cache_validates_contents_and_completion(repository: Path, tmp_path: Path) -> None:
    """
    Exercise cold, warm, incomplete, expired and changed-input cache decisions.

    Args:
        repository (Path): Unchanged chart fixture.
        tmp_path (Path): Cache storage outside the chart.

    Returns:
        None: Only matching completed successes can be reused.
    """
    chart = repository / "a"
    args = argparse.Namespace(seed=0, helm="/usr/bin/true", cache_dir=tmp_path / "cache", max_examples=10)
    changes = comparison(repository, environment={})
    first = ChartCache.prepare(chart, chart, args, changes)
    assert not first.reusable
    first.publish({"status": "passed"})
    warm = ChartCache.prepare(chart, chart, args, changes)
    assert warm.reusable
    assert not ChartCache.prepare(chart, chart, args, {**changes, "status": "unavailable"}).reusable
    assert not ChartCache.prepare(chart, chart, args, {**changes, "changed_files": ["a/templates/new.yaml"]}).reusable
    for status in ("failed", "time-limit", "error", "interrupted"):
        warm.publish({"status": status})
        assert not ChartCache.prepare(chart, chart, args, changes).reusable
        warm = ChartCache.prepare(chart, chart, args, changes)
        warm.publish({"status": "passed"})
        warm = ChartCache.prepare(chart, chart, args, changes)
        assert warm.reusable
    warm.publish({"status": "passed", "traversal": {"remaining_paths": 1}})
    assert not ChartCache.prepare(chart, chart, args, changes).reusable
    warm = ChartCache.prepare(chart, chart, args, changes)
    warm.publish({"status": "passed", "traversal": {"selected_paths": 7, "completed_paths": 7, "sampled_out_paths": 3}})
    assert ChartCache.prepare(chart, chart, args, changes).reusable
    args.seed = 1
    assert not ChartCache.prepare(chart, chart, args, changes).reusable
    args.seed = 0
    args.max_examples = 11
    assert not ChartCache.prepare(chart, chart, args, changes).reusable
    args.max_examples = 10
    dependency = chart / "charts/common.tgz"
    dependency.parent.mkdir()
    dependency.write_bytes(b"changed dependency")
    assert not ChartCache.prepare(chart, chart, args, changes).reusable
    dependency.unlink()
    assert warm.path is not None
    expired = time.time() - RETENTION_SECONDS - 1
    os.utime(warm.path, (expired, expired))
    assert not ChartCache.prepare(chart, chart, args, changes).reusable
    warm.path.write_text("corrupt JSON")
    assert not ChartCache.prepare(chart, chart, args, changes).reusable
    first_writer = ChartCache.prepare(chart, chart, args, changes)
    second_writer = ChartCache.prepare(chart, chart, args, changes)
    first_writer.publish({"status": "failed"})
    second_writer.publish({"status": "passed"})
    assert not ChartCache.prepare(chart, chart, args, changes).reusable


def test_recursive_cli_reuses_only_unchanged_completed_charts(
    repository: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    Verify real CLI discovery, report statuses and invalidation after a source commit.

    Args:
        repository (Path): Local two-chart repository.
        tmp_path (Path): Artifact and cache parent.
        monkeypatch (pytest.MonkeyPatch): Replace expensive execution with a completed test result.
        capsys (pytest.CaptureFixture[str]): Read CLI JSON reports.

    Returns:
        None: Cold runs test both charts, warm runs reuse both, changed runs retest one.
    """
    visited: list[str] = []

    def exercise(path: Path, args: argparse.Namespace, artifacts: Path) -> dict[str, object]:
        """
        Record chart execution without invoking Helm.

        Args:
            path (Path): Prepared chart.
            args (argparse.Namespace): Effective CLI settings.
            artifacts (Path): Report directory.

        Returns:
            dict[str, object]: Completed passing result.
        """
        visited.append((path / "values.yaml").read_text())
        return {"status": "passed", "attempts": 10}

    monkeypatch.setattr(importlib.import_module("hypothesis_helm.charts.scan"), "exercise_chart", exercise)
    arguments = [
        "test",
        str(repository),
        "--jobs",
        "1",
        "--helm",
        "/usr/bin/true",
        "--no-build-dependencies",
        "--cache-dir",
        str(tmp_path / "cache"),
        "--artifact-dir",
        str(tmp_path / "reports"),
    ]
    assert main(arguments) == 0
    assert len(visited) == 2
    capsys.readouterr()
    assert main(arguments) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["counts"] == {"cached-pass": 2}
    assert len(visited) == 2
    commit(repository, "a/values.yaml", "enabled: false\n")
    commit(repository, "a/values-minimal.yaml", "enabled: false\n", MINIMAL_TRAILER)
    assert main(arguments) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["git_comparison"]["base_ref"] == "HEAD~2"
    assert report["counts"] == {"passed": 1, "cached-pass": 1}
    assert len(visited) == 3
    assert main([*arguments, "--no-cache"]) == 0
    assert len(visited) == 5

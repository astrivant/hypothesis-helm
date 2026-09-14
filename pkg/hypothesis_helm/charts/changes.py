"""
Resolve CI comparison revisions and retain conservative, repository-relative Git diffs.
"""

import json
import os
import subprocess
from collections.abc import Mapping
from pathlib import Path

from hypothesis_helm.execution.processes import Processes

MINIMAL_TRAILER = "Hypothesis-Helm-Minimal-Values: true"


def git(root: Path, *arguments: str) -> str:
    """
    Read local Git state without fetching or changing the checkout.

    Args:
        root (Path): Directory inside the repository being tested.
        *arguments (str): Separate Git arguments.

    Returns:
        str: Standard output, or a ValueError for unavailable repository information.
    """
    result = Processes().run(["git", "-C", str(root), *arguments], capture_output=True, timeout=10)
    if result.returncode:
        raise ValueError(result.stderr.strip() or "Git comparison unavailable")
    return result.stdout


def optional_git(root: Path, *arguments: str) -> str:
    """
    Read optional Git metadata without turning its absence into a chart failure.

    Args:
        root (Path): Repository directory.
        *arguments (str): Separate Git arguments.

    Returns:
        str: Stripped output or an empty string when unavailable.
    """
    try:
        return git(root, *arguments).strip()
    except (ValueError, OSError, subprocess.TimeoutExpired):
        return ""


def comparison(root: Path, base_ref: str | None = None, *, environment: Mapping[str, str] | None = None) -> dict[str, object]:
    """
    Compare trunk with its parent and feature branches with their target merge base.

    Args:
        root (Path): Source checkout, not the isolated prepared chart.
        base_ref (str | None): Explicit comparison reference, taking precedence over automatic detection.
        environment (Mapping[str, str] | None): Provider variables; current environment by default.

    Returns:
        dict[str, object]: Resolved base, changed paths and an explicit conservative fallback.
    """
    env = os.environ if environment is None else environment
    report: dict[str, object] = {"status": "unavailable", "base_ref": base_ref, "changed_files": []}
    try:
        repository = Path(git(root, "rev-parse", "--show-toplevel").strip()).resolve()
        report["repository"] = str(repository)
        event: dict[str, object] = {}
        # The surrounding CI project may be scanning a different remote repository.
        ci_root = env.get("GITHUB_WORKSPACE") or env.get("CI_PROJECT_DIR") or env.get("CIRCLE_WORKING_DIRECTORY")
        provider = env if ci_root is None or Path(ci_root).expanduser().resolve() == repository else {}
        if provider.get("GITHUB_EVENT_PATH"):
            try:
                loaded = json.loads(Path(provider["GITHUB_EVENT_PATH"]).read_text())
                if isinstance(loaded, dict):
                    event = loaded
            except (OSError, ValueError):
                pass
        remote_default = optional_git(repository, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
        metadata = event.get("repository", {})
        default_branch = (
            provider.get("CI_DEFAULT_BRANCH")
            or (str(metadata.get("default_branch", "")) if isinstance(metadata, dict) else "")
            or remote_default.removeprefix("origin/")
            or "main"
        )
        branch = (
            provider.get("GITHUB_HEAD_REF")
            or provider.get("GITHUB_REF_NAME")
            or provider.get("CI_COMMIT_BRANCH")
            or provider.get("CIRCLE_BRANCH")
            or optional_git(repository, "symbolic-ref", "--short", "HEAD")
        )
        explicit = base_ref or env.get("HYPOTHESIS_HELM_BASE_REF")
        target = provider.get("GITHUB_BASE_REF") or provider.get("CI_MERGE_REQUEST_TARGET_BRANCH_NAME")
        merge_base = True
        if explicit:
            reference, reason = explicit, "explicit override"
        elif target or provider.get("CI_MERGE_REQUEST_DIFF_BASE_SHA"):
            reference = provider.get("CI_MERGE_REQUEST_DIFF_BASE_SHA") or str(target)
            reason = "pull/merge request target"
        elif branch in {default_branch, "main", "master", "trunk"}:
            message = git(repository, "log", "-1", "--format=%B")
            minimal_commit = MINIMAL_TRAILER in message.splitlines()
            reference = "HEAD~2" if minimal_commit else "HEAD^"
            reason = "trunk after minimal-values commit" if minimal_commit else "previous trunk commit"
            merge_base = False
        else:
            reference, reason = remote_default or default_branch, "default branch merge base"
        report.update(base_ref=reference, selection=reason, branch=branch, default_branch=default_branch)
        resolved = optional_git(repository, "rev-parse", "--verify", "--end-of-options", f"{reference}^{{commit}}")
        if not resolved and not reference.startswith(("refs/", "origin/", "HEAD")):
            resolved = optional_git(repository, "rev-parse", "--verify", "--end-of-options", f"origin/{reference}^{{commit}}")
        if not resolved:
            raise ValueError(f"Comparison ref {reference!r} is unavailable; fetch its history or provide --base-ref")
        base = git(repository, "merge-base", resolved, "HEAD").strip() if merge_base else resolved
        tracked = git(repository, "diff", "--name-only", "--no-renames", "-z", base, "--")
        untracked = git(repository, "ls-files", "--others", "--exclude-standard", "-z")
        report.update(status="resolved", base_commit=base, changed_files=sorted(set(filter(None, (tracked + untracked).split("\0")))))
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        report["reason"] = str(exc)
    return report


def chart_changed(path: Path, report: dict[str, object]) -> bool:
    """
    Conservatively retain a chart when its files differ or the comparison is unavailable.

    Args:
        path (Path): Original chart directory.
        report (dict[str, object]): Resolved Git comparison.

    Returns:
        bool: Whether the chart must be tested rather than reused from a matching cache.
    """
    if report["status"] != "resolved":
        return True
    repository = Path(str(report["repository"]))
    if not path.resolve().is_relative_to(repository):
        return True
    relative = path.resolve().relative_to(repository).as_posix()
    paths = report["changed_files"]
    assert isinstance(paths, list)
    return (
        relative == "."
        and bool(paths)
        or any(str(item) == relative or str(item).startswith(relative + "/") or relative.startswith(str(item) + "/") for item in paths)
    )

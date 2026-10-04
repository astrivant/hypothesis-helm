"""
Check report commits to the selected branch and invalid-evidence handling.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
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
        ref (str): Branch selected for manual execution and report publication.

    Returns:
        None: Publication commits every human-readable report to the selected branch and excludes raw observations.
    """
    remote, project, binaries = (tmp_path / name for name in ("remote", "project", "bin"))
    for path in (remote, project, binaries):
        path.mkdir()
    git(remote, "init", "--bare", "--initial-branch=main")
    git(project, "init", "--initial-branch=main")
    initial_readme = (
        "Keep this introduction.\n<!-- refresh:bitnami:start -->Old Bitnami data<!-- refresh:bitnami:end -->\n"
        "<!-- refresh:prometheus:start -->\n<!--\nOld Prometheus data\n-->\n<!-- refresh:prometheus:end -->\nKeep this ending.\n"
    )
    (project / "README.md").write_text(initial_readme)
    (project / "docs").mkdir()
    (project / "docs/README.md").write_text(f"[Scan](reports/{repository}.md) [PDF](reports/{repository}.pdf)\n")
    report = project / f".cache/{repository}-final/report.json"
    report.parent.mkdir(parents=True)
    revision = "a" * 40
    report.write_text(
        json.dumps(
            {
                "charts": [{"attempts": 1234}, {"attempts": 5678}],
                "settings": {"filter": True, "jobs": 4, "shards": 80, "chart_timeout_seconds": 300},
                "source": {"kind": "git", "url": "https://github.com/bitnami/charts.git", "revision": revision},
            }
        )
    )
    (project / ".gitattributes").write_text((PROJECT_ROOT / ".gitattributes").read_text())
    git(project, "add", "README.md", "docs/README.md", ".gitattributes")
    git(project, "commit", "-m", "initial")
    git(project, "remote", "add", "origin", str(remote))
    git(project, "push", "origin", "main")
    original = git(project, "rev-parse", "HEAD")
    branch = ref.removeprefix("refs/heads/")
    if branch != "main":
        git(project, "checkout", "-b", branch)
        git(project, "push", "origin", branch)
    poetry = binaries / "poetry"
    poetry.write_text(
        dedent(f"""
        #!/usr/bin/env bash
        set -eu
        if [[ "$2" == hypothesis-helm ]]; then
            printf '%s\\n' "$@" >aggregate-args.txt
            exit {status}
        fi
        shift 2
        exec "$TEST_PYTHON" "$REPORT_WRITER_STUB" "$@"
        """).lstrip()
    )
    poetry.chmod(0o755)
    writer = binaries / "writer.py"
    writer.write_text(
        dedent("""
        import sys
        from pathlib import Path
        from hypothesis_helm.reporting.reports import repository

        def write_reports(report, stem):
            stem.parent.mkdir(parents=True, exist_ok=True)
            for extension in ('md', 'pdf', 'png', 'svg'):
                stem.with_suffix('.' + extension).write_text('Final report\\n')
            data = stem.parent / 'report-data'
            data.mkdir(exist_ok=True)
            (data / '0001.audit.json.gz').write_text('Audit findings\\n')
            (stem.parent / 'raw.json').write_text('Raw data\\n')

        repository.write_reports = write_reports
        sys.argv = sys.argv[1:]
        exec(compile(sys.stdin.read(), '<publication>', 'exec'))
        """)
    )
    gh = binaries / "gh"
    gh.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$@" >>gh-args.txt\n')
    gh.chmod(0o755)
    environment = {
        **os.environ,
        "PATH": f"{binaries}:{os.environ['PATH']}",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": ref,
        "GITHUB_REPOSITORY": "owner/project",
        "DEFAULT_BRANCH": "main",
        "SCAN_SOURCE_SHA": revision,
        "TEST_PYTHON": sys.executable,
        "REPORT_WRITER_STUB": str(writer),
        "SCAN_RUN_ID": "test-run",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
    }
    script = str(PROJECT_ROOT / ".github/repository-report.sh")
    result = subprocess.run(["bash", script, repository], cwd=project, env=environment, capture_output=True, text=True, timeout=20)
    assert result.returncode == (2 if status == 2 else 0), result.stderr
    arguments = (project / "aggregate-args.txt").read_text().splitlines()
    assert arguments[arguments.index("--shards") + 1] == "80"
    if status == 2:
        assert git(project, "rev-parse", "HEAD") == original
        assert git(remote, "rev-parse", branch) == original
        assert not (project / "gh-args.txt").exists()
        assert (project / "README.md").read_text() == initial_readme
    else:
        summary = git(project, "show", "HEAD:README.md")
        title = "Bitnami" if repository == "bitnami" else "Prometheus Community"
        assert f"**2 {title} charts**" in summary and "**6,912 test attempts**" in summary
        assert "**80 shards**" in summary and "**4 path workers per shard**" in summary and "**5-minute budget" in summary
        assert f"https://github.com/bitnami/charts/commit/{revision}" in summary
        assert f"docs/reports/{repository}/report.md" in summary and f"docs/reports/{repository}/report.pdf" in summary
        assert "Keep this introduction." in summary and "Keep this ending." in summary
        if repository == "bitnami":
            assert "<!--\nOld Prometheus data\n-->" in summary
        else:
            assert "Old Bitnami data" in summary and "<!--\nWe scanned" in summary
        assert f"reports/{repository}/report.md" in git(project, "show", "HEAD:docs/README.md")
        for extension in ("md", "pdf", "png", "svg"):
            assert f"docs/reports/{repository}/report.{extension}" in git(project, "ls-files")
        attachment = f"docs/reports/{repository}/report-data/0001.audit.json.gz"
        assert attachment in git(project, "ls-files")
        assert git(project, "check-attr", "filter", "--", attachment) == f"{attachment}: filter: unspecified"
        assert git(project, "show", f"HEAD:{attachment}") == "Audit findings"
        assert "raw.json" not in git(project, "ls-files")
        assert git(remote, "rev-parse", branch) == git(project, "rev-parse", "HEAD") != original
        if branch != "main":
            assert git(remote, "rev-parse", "main") == original
            assert (project / "gh-args.txt").read_text().splitlines() == [
                "workflow",
                "run",
                "ci.yml",
                "--repo",
                "owner/project",
                "--ref",
                branch,
            ]
        else:
            assert not (project / "gh-args.txt").exists()
        # Unchanged reports must not create another commit or dispatch another CI run.
        published = git(project, "rev-parse", "HEAD")
        repeated = subprocess.run(["bash", script, repository], cwd=project, env=environment, capture_output=True, text=True, timeout=20)
        assert repeated.returncode == 0 and "reports are unchanged" in repeated.stdout, repeated.stderr
        assert git(project, "rev-parse", "HEAD") == published
        if branch != "main":
            assert (project / "gh-args.txt").read_text().splitlines().count("ci.yml") == 1
    rejected = subprocess.run(
        ["bash", script, repository], cwd=project, env={**environment, "GITHUB_REF": "refs/pull/1/merge"}, capture_output=True, timeout=20
    )
    assert rejected.returncode == 2


@pytest.mark.parametrize("damage", ["source", "shard-source", "markers"])
def test_repository_summary_rejects_unverified_updates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, damage: str) -> None:
    """
    Reject inconsistent source evidence or missing summary markers before rewriting publications.

    Args:
        tmp_path (Path): Aggregate evidence and an existing README.
        monkeypatch (pytest.MonkeyPatch): Isolate publication paths, arguments and expected source revision.
        damage (str): Invalid aggregate source, individual shard source or README markers.

    Returns:
        None: Invalid evidence leaves the README unchanged and writes no final reports.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["-", "bitnami"])
    revision = "a" * 40
    monkeypatch.setenv("SCAN_SOURCE_SHA", revision)
    readme = tmp_path / "README.md"
    previous = "<!-- refresh:bitnami:start -->old data<!-- refresh:bitnami:end -->"
    if damage == "markers":
        previous = previous.replace("<!-- refresh:bitnami:end -->", "")
    readme.write_text(previous)
    report = tmp_path / ".cache/bitnami-final/report.json"
    report.parent.mkdir(parents=True)
    report.write_text(
        json.dumps(
            {
                "charts": [{"attempts": 12}],
                "settings": {"jobs": 4, "shards": 80, "filter": True, "chart_timeout_seconds": 300},
                "source": {"revision": "b" * 40 if damage == "source" else revision},
                "shards": [{"source": {"revision": "b" * 40 if damage == "shard-source" else revision}}],
            }
        )
    )
    script = (PROJECT_ROOT / ".github/repository-report.sh").read_text()
    publication = script.split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
    with pytest.raises(ValueError, match="summary markers" if damage == "markers" else "requested commit"):
        exec(compile(publication, ".github/repository-report.sh", "exec"), {"__name__": "__main__"})
    assert readme.read_text() == previous
    assert not (tmp_path / "docs/reports").exists()

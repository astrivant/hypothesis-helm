"""Verify sparse schema caching and per-render conformity failures."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from hypothesis_helm.execution.cache import fingerprint
from hypothesis_helm.schemas import conformity


def test_sparse_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Resolve latest stable schemas, retain immutable snapshots, and reuse them offline.

    Args:
        tmp_path (Path): Temporary upstream and cache directories.
        monkeypatch (pytest.MonkeyPatch): Substitute a local schema upstream.

    Returns:
        None: Only the selected release is checked out and cached content stays stable.
    """
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    conformity.git(upstream, "init", "-b", "master")
    for version in ("1.30.0", "1.31.0", "1.32.0-alpha.1"):
        folder = upstream / f"v{version}-standalone-strict"
        folder.mkdir()
        (folder / "configmap-v1.json").write_text('{"type":"object"}')
    conformity.git(upstream, "add", ".")
    conformity.git(
        upstream,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.org",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-m",
        "schemas",
    )
    monkeypatch.setattr(conformity, "REPOSITORY", str(upstream))
    cache = tmp_path / "cache"
    configuration = json.loads(conformity.prepare(cache, "latest", "/usr/bin/true"))
    assert configuration["version"] == "1.31.0"
    assert (cache / "repository/v1.31.0-standalone-strict/configmap-v1.json").is_file()
    assert not (cache / "repository/v1.30.0-standalone-strict").exists()
    assert json.loads(conformity.prepare(cache, "latest", "/usr/bin/true", True)) == configuration
    old = json.loads(conformity.prepare(cache, "1.30.0", "/usr/bin/true"))
    assert Path(configuration["schemas"]).is_dir()
    assert Path(old["schemas"]).is_dir()
    files_before = {p: p.read_bytes() for p in cache.rglob("*") if p.is_file()}
    inspected = json.loads(conformity.prepare(cache, "1.30.0", "/usr/bin/true", read_only=True))
    assert inspected == old
    assert files_before == {p: p.read_bytes() for p in cache.rglob("*") if p.is_file()}
    newer = upstream / "v1.32.0-standalone-strict"
    newer.mkdir()
    (newer / "configmap-v1.json").write_text('{"type":"object","title":"new"}')
    conformity.git(upstream, "add", ".")
    conformity.git(
        upstream,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.org",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-m",
        "new release",
    )
    refreshed = json.loads(conformity.prepare(cache, "latest", "/usr/bin/true"))
    assert refreshed["version"] == "1.32.0"
    assert Path(configuration["schemas"]).is_dir()
    restored_cache = tmp_path / "restored"
    shutil.copytree(cache, restored_cache)
    restored = json.loads(conformity.prepare(restored_cache, "latest", "/usr/bin/true", True))
    assert restored["identity"] == refreshed["identity"]
    assert Path(restored["schemas"]).is_relative_to(restored_cache)
    with pytest.raises(ValueError, match="no published"):
        conformity.prepare(cache, "9.9.9", "/usr/bin/true", True)
    with pytest.raises(ValueError, match="exact version"):
        conformity.prepare(cache, "../escape", "/usr/bin/true")
    with pytest.raises(ValueError, match="cache is empty"):
        conformity.prepare(tmp_path / "empty", "latest", "/usr/bin/true", True)


def test_validator_boundary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Feed manifests through stdin and invalidate outcomes when conformity is enabled.

    Args:
        tmp_path (Path): Isolated suite directory.
        monkeypatch (pytest.MonkeyPatch): Replace the validator process boundary.

    Returns:
        None: Strict local-only validation errors fail the property.
    """
    monkeypatch.delenv(conformity.ENVIRONMENT, raising=False)
    before = fingerprint(tmp_path, 0, None, "none")
    conformity.validate("ignored", 1)
    monkeypatch.setenv(
        conformity.ENVIRONMENT,
        json.dumps(
            {
                "version": "1.31.0",
                "schemas": str(tmp_path),
                "executable": "kubeconform",
            }
        ),
    )
    assert fingerprint(tmp_path, 0, None, "none") != before

    def execute(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        """
        Check validator arguments and simulate an API schema rejection.

        Args:
            command (list[str]): Validator arguments.
            **kwargs (object): Process options including manifest stdin.

        Returns:
            subprocess.CompletedProcess[str]: Failed validation result.
        """
        assert "-strict" in command and "-ignore-missing-schemas" not in command
        assert command[command.index("-schema-location") + 1].startswith(str(tmp_path))
        assert kwargs["input"] == "kind: ConfigMap"
        return subprocess.CompletedProcess(command, 1, "invalid resource", "")

    monkeypatch.setattr(subprocess, "run", execute)
    with pytest.raises(AssertionError, match="invalid resource"):
        conformity.validate("kind: ConfigMap", 1)


def test_cli_validation_scope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Propagate validator configuration only during an explicitly enabled Helm command.

    Args:
        tmp_path (Path): Saved suite location.
        monkeypatch (pytest.MonkeyPatch): Replace preparation and suite execution.

    Returns:
        None: Collection avoids downloads and configuration does not leak across runs.
    """
    import os

    from hypothesis_helm import cli

    prepared: list[str] = []

    def prepare(cache: Path, version: str, executable: str, offline: bool = False) -> str:
        """
        Record schema preparation without downloading artifacts.

        Args:
            cache (Path): Schema cache directory.
            version (str): Requested schema version.
            executable (str): Validator binary.
            offline (bool): Whether network access is disabled.

        Returns:
            str: Test configuration.
        """
        prepared.append(version)
        return '{"version":"1.31.0"}'

    def run(directory: Path, **kwargs: object) -> int:
        """
        Observe the configuration inherited by the saved-suite runner.

        Args:
            directory (Path): Suite location.
            **kwargs (object): Runner options.

        Returns:
            int: Successful test status.
        """
        assert (conformity.ENVIRONMENT in os.environ) == (not kwargs["collect_only"])
        return 0

    monkeypatch.setattr(cli, "prepare", prepare)
    monkeypatch.setattr(cli, "run_suite", run)
    monkeypatch.delenv(conformity.ENVIRONMENT, raising=False)
    arguments = ["run", str(tmp_path), "--kubeconform", "--schema-version", "1.31.0"]
    assert cli.main(arguments) == 0
    assert conformity.ENVIRONMENT not in os.environ
    assert cli.main([*arguments, "--collect-only"]) == 0
    assert prepared == ["1.31.0"]
    assert cli.main(["schemas", "--schema-cache-dir", str(tmp_path)]) == 0
    assert prepared == ["1.31.0", "latest"]


def test_memory_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Verify atomic memory staging, reuse, mount checks, and capacity failures.

    Args:
        tmp_path (Path): Isolated snapshot and simulated mount.
        monkeypatch (pytest.MonkeyPatch): Replace Linux mount detection for portability.

    Returns:
        None: Only complete snapshots are reused and unsuitable mounts are rejected.
    """
    snapshot = tmp_path / "disk" / "identity" / "v1.35.0-standalone-strict"
    snapshot.mkdir(parents=True)
    (snapshot / "pod.json").write_text('{"type":"object"}')
    monkeypatch.delenv("HYPOTHESIS_HELM_SCHEMA_MEMORY_DIR", raising=False)
    assert conformity.memory_snapshot(snapshot) == snapshot
    root = tmp_path / "memory"
    monkeypatch.setenv("HYPOTHESIS_HELM_SCHEMA_MEMORY_DIR", str(root))
    monkeypatch.setattr(
        subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "ext4\n")
    )
    with pytest.raises(ValueError, match="Linux tmpfs"):
        conformity.memory_snapshot(snapshot)
    assert not root.exists()
    monkeypatch.setattr(
        subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "tmpfs\n")
    )
    staged = conformity.memory_snapshot(snapshot)
    assert staged == root / snapshot.parent.name / snapshot.name
    assert (staged / "pod.json").read_bytes() == (snapshot / "pod.json").read_bytes()
    timestamp = (staged / "pod.json").stat().st_mtime_ns
    assert conformity.memory_snapshot(snapshot) == staged
    assert (staged / "pod.json").stat().st_mtime_ns == timestamp
    monkeypatch.setenv("HYPOTHESIS_HELM_SCHEMA_MEMORY_DIR", str(tmp_path / "full"))
    usage = shutil.disk_usage(tmp_path)
    monkeypatch.setattr(shutil, "disk_usage", lambda _: usage._replace(free=0))
    with pytest.raises(ValueError, match="free bytes"):
        conformity.memory_snapshot(snapshot)
    assert not (tmp_path / "full" / snapshot.parent.name).exists()

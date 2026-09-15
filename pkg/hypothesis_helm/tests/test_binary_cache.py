"""
Exercise the published CI installers with local release archives and no network access.
"""

import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest
from ruamel.yaml import YAML

from hypothesis_helm.schemas.contracts import mapping, sequence


def installer_commands(root: Path, provider: str) -> list[str]:
    """
    Read the actual installer shell blocks from each shipped integration.

    Args:
        root (Path): Repository root.
        provider (str): Integration or project workflow being exercised.

    Returns:
        list[str]: Shell commands that download and install binaries.
    """
    filename = {
        "github": "action.yml",
        "gitlab": "ci/gitlab.yml",
        "circleci": "ci/circleci.yml",
        "github-benchmark": ".github/workflows/benchmarks.yml",
        "github-project": ".github/workflows/ci.yml",
        "circleci-project": ".circleci/config.yml",
    }[provider]
    document = mapping(YAML(typ="safe").load((root / filename).read_text()))
    if provider == "gitlab":
        return [str(command) for command in sequence(mapping(document["helm-properties"])["before_script"]) if "curl -fsSL" in str(command)]
    if provider == "github":
        steps = sequence(mapping(document["runs"])["steps"])
        return [
            str(mapping(step)["run"])
            for step in steps
            if mapping(step).get("name") in {"Install Helm", "Install kubeconform", "Install Kubesec"}
        ]
    job = {"circleci": "test-chart", "github-benchmark": "smoke", "circleci-project": "test-python", "github-project": "test-python"}[
        provider
    ]
    steps = sequence(mapping(mapping(document["jobs"])[job])["steps"])
    commands = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        run = mapping(step).get("run")
        if isinstance(run, dict):
            run = run.get("command")
        if isinstance(run, str) and "curl -fsSL" in run:
            commands.append(run)
    return commands


@pytest.mark.parametrize(
    ("provider", "platform", "architecture"),
    [
        ("github", "Linux", "X64"),
        ("github", "macOS", "ARM64"),
        ("gitlab", "Linux", "X64"),
        ("circleci", "Linux", "X64"),
        ("github-benchmark", "Linux", "X64"),
        ("circleci-project", "Linux", "X64"),
        ("github-project", "Linux", "X64"),
    ],
)
def test_binary_installers_reuse_exact_versions(tmp_path: Path, provider: str, platform: str, architecture: str) -> None:
    """
    Verify cold installs, warm reuse, version changes, bypass, and failed downloads.

    Args:
        tmp_path (Path): Isolated downloads, caches and simulated installation directory.
        provider (str): Installer whose published shell is executed.
        platform (str): GitHub operating-system label.
        architecture (str): GitHub architecture label.

    Returns:
        None: Only missing requested releases download, and partial installs are never reused.
    """
    root = Path(__file__).resolve().parents[3]
    commands = installer_commands(root, provider)
    assert commands
    binaries = tmp_path / "bin"
    binaries.mkdir()
    mock = binaries / "curl"
    mock.write_text(
        f"#!{sys.executable}\n"
        + dedent(
            """
            import io, os, sys, tarfile
            from pathlib import Path
            url = next(arg for arg in sys.argv if arg.startswith('https://'))
            with Path(os.environ['DOWNLOAD_LOG']).open('a') as log:
                log.write(url + '\\n')
            if os.environ.get('DOWNLOAD_FAIL') == 'true':
                sys.exit(22)
            tool = 'kubesec' if '/controlplaneio/' in url else 'kubeconform' if '/yannh/' in url else 'helm'
            member = tool
            if tool == 'helm':
                system, arch = url.removesuffix('.tar.gz').rsplit('-', 2)[-2:]
                member = f'{system}-{arch}/helm'
            payload = ('#!/bin/sh\\n# ' + url + '\\nexit 0\\n').encode()
            destination = sys.argv[sys.argv.index('-o') + 1]
            with tarfile.open(destination, 'w:gz') as archive:
                info = tarfile.TarInfo(member)
                info.size = len(payload)
                info.mode = 0o755
                archive.addfile(info, io.BytesIO(payload))
            """
        ).lstrip()
    )
    mock.chmod(0o755)
    for name, body in (("sudo", 'exec "$@"'), ("apt-get", "exit 0")):
        path = binaries / name
        path.write_text(f"#!/bin/sh\n{body}\n")
        path.chmod(0o755)
    installed = tmp_path / "installed"
    installed.mkdir()
    log = tmp_path / "downloads.txt"
    environment = {
        **os.environ,
        "PATH": str(binaries) + os.pathsep + os.environ["PATH"],
        "RUNNER_TEMP": str(tmp_path),
        "RUNNER_OS": platform,
        "RUNNER_ARCH": architecture,
        "GITHUB_PATH": str(tmp_path / "github-path"),
        "BINARY_CACHE": "true",
        "HH_BINARY_CACHE": "true",
        "KUBESEC_ENABLED": "true",
        "HH_KUBESEC": "true",
        "DOWNLOAD_LOG": str(log),
        "TMPDIR": str(tmp_path),
    }
    for name, value in (("HELM_VERSION", "v4.3.0"), ("KUBECONFORM_VERSION", "v0.7.0"), ("KUBESEC_VERSION", "v2.14.2")):
        environment[name] = environment[f"HH_{name}"] = value

    def execute() -> subprocess.CompletedProcess[str]:
        """
        Execute published download commands, redirecting privileged installation into the fixture.

        Returns:
            subprocess.CompletedProcess[str]: Installer status and captured diagnostics.
        """
        script = "\n".join(commands).replace("/usr/local/bin/", str(installed) + "/")
        return subprocess.run(["bash", "-euo", "pipefail", "-c", script], cwd=tmp_path, env=environment, text=True, capture_output=True)

    count = 1 if provider.endswith(("benchmark", "project")) else 3
    first = execute()
    assert first.returncode == 0, first.stderr
    assert len(log.read_text().splitlines()) == count
    cached = [path for path in tmp_path.rglob("helm") if any(part in {"binaries", "hypothesis-helm-binaries"} for part in path.parts)]
    assert len(cached) == 1 and os.access(cached[0], os.X_OK)
    second = execute()
    assert second.returncode == 0, second.stderr
    assert len(log.read_text().splitlines()) == count
    environment["HELM_VERSION"] = environment["HH_HELM_VERSION"] = "v4.3.1"
    updated = execute()
    assert updated.returncode == 0, updated.stderr
    assert len(log.read_text().splitlines()) == count + 1
    assert "helm-v4.3.1" in log.read_text().splitlines()[-1]
    if provider != "gitlab":
        environment["BINARY_CACHE"] = environment["HH_BINARY_CACHE"] = "false"
        bypassed = execute()
        assert bypassed.returncode == 0, bypassed.stderr
        assert len(log.read_text().splitlines()) == 2 * count + 1
    environment["BINARY_CACHE"] = environment["HH_BINARY_CACHE"] = "true"
    environment["HELM_VERSION"] = environment["HH_HELM_VERSION"] = "v4.3.2"
    environment["DOWNLOAD_FAIL"] = "true"
    failed = execute()
    assert failed.returncode == 22
    assert not any("v4.3.2" in str(path) for path in tmp_path.rglob("helm"))
    environment.pop("DOWNLOAD_FAIL")
    recovered = execute()
    assert recovered.returncode == 0, recovered.stderr
    assert "helm-v4.3.2" in log.read_text().splitlines()[-1]


@pytest.mark.parametrize("provider", ["github", "gitlab", "circleci"])
def test_binary_cache_keys_are_release_specific(provider: str) -> None:
    """
    Ensure restore and publication address the same versioned binary directories.

    Args:
        provider (str): Reusable CI definition whose cache metadata is checked.

    Returns:
        None: Every binary has a separate exact-version key and matching restore/save paths.
    """
    root = Path(__file__).resolve().parents[3]
    filename = "action.yml" if provider == "github" else f"ci/{provider}.yml"
    document = mapping(YAML(typ="safe").load((root / filename).read_text()))
    if provider == "github":
        assert mapping(mapping(document["inputs"])["binary-cache"])["default"] == "true"
        steps = [mapping(step) for step in sequence(mapping(document["runs"])["steps"])]
        for tool in ("helm", "kubeconform", "kubesec"):
            restore = next(step for step in steps if step.get("id") == f"{tool}-cache")
            metadata = mapping(restore["with"])
            key = str(metadata["key"])
            assert all(marker in key for marker in (f"inputs.{tool}-version", "runner.os", "runner.arch"))
            assert "restore-keys" not in metadata
            save = next(step for step in steps if step.get("uses") == "actions/cache/save@v5" and mapping(step["with"]).get("key") == key)
            assert save["with"] == restore["with"]
            assert "inputs.binary-cache == 'true'" in str(restore["if"]) and "inputs.binary-cache == 'true'" in str(save["if"])
        return
    if provider == "gitlab":
        caches = [mapping(cache) for cache in sequence(mapping(document["helm-properties"])["cache"])]
        assert len(caches) == 4  # GitLab permits four entries, including the schema cache.
        for tool in ("helm", "kubeconform", "kubesec"):
            cache = next(cache for cache in caches if f"-{tool}-" in str(cache["key"]))
            version = "${" + tool.upper() + "_VERSION}"
            assert version in str(cache["key"]) and "linux-amd64" in str(cache["key"])
            assert version in str(cache["paths"]) and cache["when"] == "always"
        return
    job = mapping(mapping(document["jobs"])["test-chart"])
    assert mapping(mapping(job["parameters"])["binary-cache"])["default"] is True
    conditions = [mapping(mapping(step)["when"]) for step in sequence(job["steps"]) if isinstance(step, dict) and "when" in step]
    assert len(conditions) == 2 and all(condition["condition"] == "<< parameters.binary-cache >>" for condition in conditions)
    restores = [mapping(mapping(step)["restore_cache"]) for step in sequence(conditions[0]["steps"])]
    saves: list[dict[str, object]] = []
    for step in sequence(conditions[1]["steps"]):
        fields = mapping(step)
        if "when" in fields:
            saves.extend(mapping(mapping(nested)["save_cache"]) for nested in sequence(mapping(fields["when"])["steps"]))
        else:
            saves.append(mapping(fields["save_cache"]))
    for tool in ("helm", "kubeconform", "kubesec"):
        restore = next(cache for cache in restores if f"-{tool}-" in str(cache["keys"]))
        key = str(sequence(restore["keys"])[0])
        assert len(sequence(restore["keys"])) == 1
        assert str(key).endswith("-exact") and "linux-amd64" in str(key)
        assert f"parameters.{tool}-version" in str(key)
        save = next(cache for cache in saves if cache["key"] == key)
        assert f"parameters.{tool}-version" in str(save["paths"])

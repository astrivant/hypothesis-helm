"""
Exercise installed benchmark entry points without exposing the repository's scripts directory.
"""

import json
import os
import shutil
import subprocess
import sys
import tarfile
import tomllib
from email.parser import Parser
from pathlib import Path
from zipfile import ZipFile

import pytest
from packaging.requirements import Requirement

import hypothesis_helm
from hypothesis_helm.tests import PROJECT_ROOT


def test_benchmark_dependency_accepts_current_core_release() -> None:
    """
    Reject stale addon constraints before they can stall or fail installation of the benchmarking extra.

    Returns:
        None: Source metadata and the lock agree on a core requirement that accepts this release.
    """
    root = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text())
    addon = tomllib.loads((PROJECT_ROOT / "pkg/hypothesis_helm_benchmarking/pyproject.toml").read_text())
    requirements = [Requirement(value) for value in addon["project"]["dependencies"]]
    core = next(requirement for requirement in requirements if requirement.name == "hypothesis-helm")
    assert core.specifier.contains(root["tool"]["poetry"]["version"], prereleases=True)
    lock = tomllib.loads((PROJECT_ROOT / "poetry.lock").read_text())
    package = next(package for package in lock["package"] if package["name"] == "hypothesis-helm-benchmarking")
    assert Requirement(f"hypothesis-helm{package['dependencies']['hypothesis-helm']}").specifier == core.specifier
    extra = Requirement(root["project"]["optional-dependencies"]["benchmarking"][0])
    assert extra.specifier.contains(addon["project"]["version"], prereleases=True)


@pytest.mark.integration
def test_benchmark_wheel(tmp_path: Path) -> None:
    """
    Build a wheel and execute packaged commands from an isolated directory.

    Args:
        tmp_path (Path): Wheel build, extraction and working directories.

    Returns:
        None: The distributable contains all benchmark modules and declares optional dependencies.
    """
    poetry = shutil.which("poetry")
    if poetry is None:
        pytest.skip("Poetry is required to build the distribution")
    root = PROJECT_ROOT
    environment = {
        key: value for key, value in os.environ.items() if key not in {"VIRTUAL_ENV", "PYENV_VERSION", "PYENV_VIRTUAL_ENV", "PYTHONPATH"}
    }
    environment["VIRTUAL_ENV"] = str(Path(sys.executable).parent.parent)
    subprocess.run(
        [poetry, "build", "--format", "wheel", "--output", str(tmp_path / "dist")],
        cwd=root,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    wheel = next((tmp_path / "dist").glob("*.whl"))
    with ZipFile(wheel) as archive:
        metadata_name = next(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
        entry_points = archive.read(metadata_name.replace("METADATA", "entry_points.txt")).decode()
        for declaration in (
            "hypothesis-helm-path-worker=hypothesis_helm.execution.workers.path_queue:main",
            "hypothesis-helm-complexity=hypothesis_helm.compiler.passes.complexity:main",
            "hypothesis-helm-kubesec=hypothesis_helm.integrations.kubesec:main",
            "hypothesis-helm-github-action=hypothesis_helm.integrations.github_action:main",
            "hypothesis-helm-ci-policy=hypothesis_helm.integrations.incremental:main",
        ):
            assert declaration in entry_points.replace(" ", "")
        metadata = Parser().parsestr(archive.read(metadata_name).decode())
        core_version = str(metadata["Version"])
        assert "benchmarking" in metadata.get_all("Provides-Extra", [])
        requirements = metadata.get_all("Requires-Dist", [])
        assert any(Requirement(line).name == "lupa" for line in requirements)
        assert "hypothesis_helm/compiler/lua/bounds.lua" in archive.namelist()
        assert "hypothesis_helm/compiler/assets/builtin_inventory.json" in archive.namelist()
        for filename in ("main.go", "go.mod", "go.sum"):
            assert f"hypothesis_helm/compiler/assets/renderer/{filename}" in archive.namelist()
        calibration = json.loads(archive.read("hypothesis_helm/execution/planning/data/calibration.json"))
        assert calibration["version"] == "aggressive-calibration-v1"
        assert calibration["profiles"]
        for name in ("main.go", "helm.go", "kubernetes.go", "go.mod", "go.sum"):
            assert f"hypothesis_helm_catalog/upstream/{name}" in archive.namelist()
        assert not any(name.startswith("hypothesis_helm_catalog/upstream/builtins/") for name in archive.namelist())
        assert any(line.startswith("hypothesis-helm-benchmarking ") and 'extra == "benchmarking"' in line for line in requirements)
        assert not any("file://" in line for line in requirements)
        assert not any(name.startswith("hypothesis_helm_benchmarking/") for name in archive.namelist())
        archive.extractall(tmp_path / "installed")
    build_addon = "import sys; from setuptools.build_meta import build_wheel; build_wheel(sys.argv[1])"
    addon_source = tmp_path / "addon-source"
    shutil.copytree(
        root / "pkg/hypothesis_helm_benchmarking",
        addon_source,
        ignore=shutil.ignore_patterns("build", "dist", "*.egg-info", "__pycache__"),
    )
    subprocess.run(
        [sys.executable, "-c", build_addon, str(tmp_path / "addon")],
        cwd=addon_source,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    with ZipFile(next((tmp_path / "addon").glob("*.whl"))) as archive:
        metadata_name = next(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
        metadata = Parser().parsestr(archive.read(metadata_name).decode())
        requirements = metadata.get_all("Requires-Dist", [])
        assert {"hypothesis-helm", "matplotlib", "numpy"} <= {Requirement(line).name for line in requirements}
        core = next(Requirement(line) for line in requirements if Requirement(line).name == "hypothesis-helm")
        assert core.specifier.contains(core_version, prereleases=True)
        entry_points = archive.read(metadata_name.replace("METADATA", "entry_points.txt")).decode()
        assert "hypothesis-helm-benchmark=hypothesis_helm_benchmarking.cli:main" in entry_points.replace(" ", "")
        assert not any(name.startswith("hypothesis_helm/") for name in archive.namelist())
        archive.extractall(tmp_path / "installed")
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from setuptools.build_meta import build_sdist; build_sdist(sys.argv[1])",
            str(tmp_path / "addon"),
        ],
        cwd=addon_source,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    with tarfile.open(next((tmp_path / "addon").glob("*.tar.gz"))) as archive:
        archive.extractall(tmp_path / "source", filter="data")
    subprocess.run(
        [sys.executable, "-c", build_addon, str(tmp_path / "rebuilt")],
        cwd=next((tmp_path / "source").iterdir()),
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    with ZipFile(next((tmp_path / "addon").glob("*.whl"))) as original, ZipFile(next((tmp_path / "rebuilt").glob("*.whl"))) as rebuilt:
        expected = {name for name in original.namelist() if name.startswith("hypothesis_helm_benchmarking/")}
        assert expected == {name for name in rebuilt.namelist() if name.startswith("hypothesis_helm_benchmarking/")}
        assert all(original.read(name) == rebuilt.read(name) for name in expected)
    bootstrap = "import sys; sys.path.insert(0,sys.argv.pop(1)); from hypothesis_helm_benchmarking.cli import main; sys.exit(main())"
    command = [sys.executable, "-I", "-c", bootstrap, str(tmp_path / "installed")]
    for name in (
        "generate",
        "run",
        "discovery",
        "sparsity",
        "matrix",
        "pca",
        "expansion",
        "structure-depth",
        "nesting",
        "stress",
        "sampling",
        "calibration",
        "filtering",
        "error-surface",
        "topology",
        "flamegraph",
    ):
        result = subprocess.run(
            [*command, name, "--help"],
            cwd=tmp_path,
            env=environment,
            capture_output=True,
            text=True,
            check=True,
        )
        assert "usage:" in result.stdout
    result = subprocess.run(
        [*command, "generate", "--output", "chart", "--input-complexity", "8"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout)["input_complexity"] == 8
    assert (tmp_path / "chart/Chart.yaml").exists()


def test_source_fingerprint_covers_application_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Keep application code in the fingerprint after nesting the benchmark modules.

    Args:
        tmp_path (Path): Synthetic installed package with the new directory layout.
        monkeypatch (pytest.MonkeyPatch): Locate fingerprinting in the synthetic package.

    Returns:
        None: Application and benchmark changes invalidate measurements; tests do not.
    """
    from hypothesis_helm_benchmarking.execution import provenance

    package = tmp_path / "hypothesis_helm"
    source = tmp_path / "hypothesis_helm_benchmarking/execution/provenance.py"
    package.mkdir()
    (package / "__init__.py").touch()
    monkeypatch.setattr(hypothesis_helm, "__file__", str(package / "__init__.py"))
    source.parent.mkdir(parents=True)
    source.write_text("# source fingerprint implementation\n")
    application = package / "cli.py"
    application.write_text("VERSION = 1\n")
    monkeypatch.setattr(provenance, "__file__", str(source))
    original = provenance.code_digest()
    application.write_text("VERSION = 2\n")
    changed = provenance.code_digest()
    assert changed != original
    tests = package / "tests"
    tests.mkdir()
    (tests / "test_cli.py").write_text("def test_cli(): pass\n")
    assert provenance.code_digest() == changed
    source.write_text("# changed benchmark implementation\n")
    assert provenance.code_digest() != changed

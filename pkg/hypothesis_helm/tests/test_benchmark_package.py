"""
Exercise installed benchmark entry points without exposing the repository's scripts directory.
"""

import json
import os
import shutil
import subprocess
import sys
from email.parser import Parser
from pathlib import Path
from zipfile import ZipFile

import pytest


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
    root = Path(__file__).resolve().parents[3]
    environment = {
        key: value for key, value in os.environ.items() if key not in {"VIRTUAL_ENV", "PYENV_VERSION", "PYENV_VIRTUAL_ENV", "PYTHONPATH"}
    }
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
            "hypothesis-helm-benchmark=hypothesis_helm.benchmarking.cli:main",
            "hypothesis-helm-path-worker=hypothesis_helm.execution.path_queue:main",
            "hypothesis-helm-complexity=hypothesis_helm.compiler.passes.complexity:main",
            "hypothesis-helm-kubesec=hypothesis_helm.integrations.kubesec:main",
            "hypothesis-helm-github-action=hypothesis_helm.integrations.github_action:main",
        ):
            assert declaration in entry_points.replace(" ", "")
        metadata = Parser().parsestr(archive.read(metadata_name).decode())
        assert "benchmarking" in metadata.get_all("Provides-Extra", [])
        requirements = metadata.get_all("Requires-Dist", [])
        for dependency in ("matplotlib", "numpy"):
            assert any(line.startswith(dependency + " ") and 'extra == "benchmarking"' in line for line in requirements)
        assert not any(name.startswith("scripts/") for name in archive.namelist())
        archive.extractall(tmp_path / "installed")
    bootstrap = "import sys; sys.path.insert(0,sys.argv.pop(1)); from hypothesis_helm.benchmarking.cli import main; sys.exit(main())"
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
    from hypothesis_helm.benchmarking.execution import provenance

    package = tmp_path / "hypothesis_helm"
    source = package / "benchmarking/execution/provenance.py"
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

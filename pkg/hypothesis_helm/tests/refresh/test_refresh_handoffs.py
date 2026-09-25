"""
Exercise refresh artifact handoffs with small real charts and interrupted attempts.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest
from hypothesis_helm_benchmarking.refresh.resume import latest_journal
from hypothesis_helm_benchmarking.reporting.publication import publish_study

from hypothesis_helm.tests import PROJECT_ROOT


def test_latest_resume_selects_continuation(tmp_path: Path) -> None:
    """
    Select the latest journal without accidentally reading journals from child workloads.

    Args:
        tmp_path (Path): Workspace containing original and repeated continuation attempts.

    Returns:
        None: Automatic recovery follows the newest saved continuation.
    """
    root = tmp_path / "refresh-1"
    root.mkdir()
    (tmp_path / "latest-refresh.txt").write_text(str(root))
    paths = [root / "operations.json", root / "logs/resumed-2/operations.json", root / "resumed-3/operations.json"]
    for index, path in enumerate(paths, 1):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}")
        os.utime(path, ns=(index, index))
        assert latest_journal(tmp_path) == path
    unrelated = root / "outputs/example/operations.json"
    unrelated.parent.mkdir(parents=True)
    unrelated.write_text("{}")
    assert latest_journal(tmp_path) == paths[-1]


def test_study_requires_verified_measurements(tmp_path: Path) -> None:
    """
    Reject a successful command that leaves no usable measurements before starting another study.

    Args:
        tmp_path (Path): Isolated recipe with a producer that exits successfully without output.

    Returns:
        None: The status ledger records verification failure rather than a false successful handoff.
    """
    recipes = PROJECT_ROOT / "pkg/hypothesis_helm_benchmarking/refresh/recipes"
    shutil.copy2(recipes / "verify-measurements.py", tmp_path / "verify-measurements.py")
    (tmp_path / "provenance.json").write_text('{"code_sha256": "fixture"}')
    binary = tmp_path / "hypothesis-helm-benchmark"
    binary.write_text("#!/usr/bin/env bash\nexit 0\n")
    binary.chmod(0o755)
    result = subprocess.run(
        ["bash", str(recipes / "studies.sh"), "matrix", str(tmp_path)],
        env={**os.environ, "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}"},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0
    assert "results.json" in result.stderr
    assert (tmp_path / "status.tsv").read_text() == f"matrix\t{result.returncode}\n"


@pytest.mark.integration
def test_native_topology_publication_and_retry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Export real compiler graphs, draw them, verify their ledgers, and publish final figures.

    Args:
        tmp_path (Path): Small chart, replay recipe, and isolated publication root.
        monkeypatch (pytest.MonkeyPatch): Keep generated study pages away from the working repository.

    Returns:
        None: Native chart and recipe exports survive repeated cataloguing and retain their plotted invariants.
    """
    if shutil.which("helm") is None:
        pytest.skip("Helm is required for graph export")
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "refresh-1"
    root.mkdir()
    recipes = PROJECT_ROOT / "pkg/hypothesis_helm_benchmarking/refresh/recipes"
    chart = tmp_path / "chart"
    (chart / "templates").mkdir(parents=True)
    (chart / "Chart.yaml").write_text("apiVersion: v2\nname: app\nversion: 0.1.0\n")
    (chart / "values.yaml").write_text("message: hello\n")
    (chart / "templates/configmap.yaml").write_text(
        dedent(
            """
            apiVersion: v1
            kind: ConfigMap
            metadata:
              name: app
            data:
              message: {{ .Values.message | quote }}
            """
        )
    )
    recipe = tmp_path / "parameters.yaml"
    recipe.write_text("parameters:\n  input_complexity: 2\n  output_bins: 4\n")
    (root / "helm/plugins").mkdir(parents=True)
    (root / "helm/repositories.yaml").write_text("apiVersion: v1\nrepositories: []\n")
    (root / "provenance.json").write_text('{"source_revisions": {}}')
    inventory = []
    for source, name in ((chart, "chart"), (recipe, "recipe")):
        output = root / "outputs/chart-topologies/synthetic" / name
        inventory.append({"repository": "synthetic", "chart": name, "source": str(source), "output": str(output)})
        result = subprocess.run(
            ["bash", str(recipes / "chart-topology.sh"), str(source), str(output), str(root)],
            capture_output=True,
            text=True,
            timeout=90,
        )
        assert result.returncode == 0, result.stderr + "\n".join(path.read_text() for path in output.glob("*.err"))
    (root / "topology-inventory.json").write_text(json.dumps(inventory))
    for name in (
        "plan-topology-retries.py",
        "catalog-topologies.py",
        "verify-topologies.py",
        "catalog-topologies.py",
        "verify-topologies.py",
    ):
        subprocess.run([sys.executable, str(recipes / name), str(root)], capture_output=True, text=True, check=True, timeout=60)
    assert (root / "topology-retry-charts.tsv").read_text() == ""
    assert (root / "topology-retry-plots.tsv").read_text() == ""
    output = root / "outputs/chart-topologies"
    verified = json.loads((output / "verification.json").read_text())
    assert verified["charts"] == 2 and verified["statuses"] == {"rendered": 2}
    publish_study(output, Path("studies/chart-topologies"))
    assert Path("studies/chart-topologies/graph-invariants.png").is_file()
    for item in inventory:
        assert (output / "synthetic" / item["chart"] / "graph.json.gz").is_file()
        published = Path("studies/chart-topologies/synthetic") / item["chart"]
        assert (published / "topology.png").is_file()
        assert not (published / "graph.json.gz").exists()
        assert "local run data" in (published / "README.md").read_text()

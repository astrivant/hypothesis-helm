"""
Verify runner.
"""

import json
import os
import shutil
from pathlib import Path

import pytest
from hypothesis import given, settings
from jsonschema import validate

from hypothesis_helm import Chart, check_chart
from hypothesis_helm.charts.runner import RenderFailure, audit, merge_values, validate_resources
from hypothesis_helm.cli import main
from hypothesis_helm.schemas.contracts import mapping, number, sequence, text

ROOT = Path(__file__).resolve().parents[3]


def test_strategy_is_schema_valid() -> None:
    """
    Verify strategy is schema valid.

    Returns:
        None: None. The operation completes through its documented side effects.
    """
    chart = Chart.load(ROOT / "examples/workload")

    @settings(max_examples=20)
    @given(chart.strategy())
    def valid(values: dict[str, object]) -> None:
        """
        Assert that generated values satisfy the test contract.

        Args:
            values (dict[str, object]): Values document used as the rendering baseline.

        Returns:
            None: None. The operation completes through its documented side effects.
        """
        validate(values, chart.schema)

    valid()


def test_audit_hidden_defaults_and_types() -> None:
    """
    Verify audit hidden defaults and types.

    Returns:
        None: None. The operation completes through its documented side effects.
    """
    report = audit(Chart.load(ROOT / "examples/hidden-levers"))
    assert {tuple(sequence(mapping(f)["path"])) for f in sequence(report["findings"]) if mapping(f)["issue"] == "undocumented"} == {
        ("secretSwitch",),
        ("other-switch",),
    }
    assert any(mapping(r)["fallback"] for r in sequence(report["references"]))
    assert not audit(Chart.load(ROOT / "examples/workload"))["findings"]


def test_merge() -> None:
    """
    Verify merge.

    Returns:
        None: None. The operation completes through its documented side effects.
    """
    assert merge_values({"a": {"x": 1, "y": 2}, "b": [1]}, {"a": {"x": None}, "b": []}) == {
        "a": {"y": 2},
        "b": [],
    }


@pytest.mark.parametrize(
    "resource",
    [
        None,
        {},
        {"apiVersion": "v1", "kind": "ConfigMap"},
        {"apiVersion": "v1", "kind": "List", "items": None},
    ],
)
def test_bad_resources(resource: object) -> None:
    """
    Verify bad resources.

    Args:
        resource (object): Resource envelope under test.

    Returns:
        None: None. The operation completes through its documented side effects.
    """
    with pytest.raises(RenderFailure):
        validate_resources([resource])


def test_cli_error(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    """
    Verify cli error.

    Args:
        capsys (pytest.CaptureFixture[str]): Pytest fixture for inspecting captured command output.
        tmp_path (Path): Temporary directory supplied by pytest.

    Returns:
        None: None. The operation completes through its documented side effects.
    """
    assert main(["test", str(tmp_path / "missing")]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "error"


@pytest.mark.integration
@pytest.mark.skipif(not shutil.which("helm"), reason="Helm is required")
@pytest.mark.parametrize("name", ["configmap", "workload"])
def test_real_helm(name: str) -> None:
    """
    Verify real helm.

    Args:
        name (str): Example chart name to test.

    Returns:
        None: None. The operation completes through its documented side effects.
    """
    report = check_chart(ROOT / "examples" / name, max_examples=12)
    assert report["status"] == "passed", report


@pytest.mark.integration
@pytest.mark.skipif(not shutil.which("helm"), reason="Helm is required")
def test_shrinks_and_saves_counterexample(tmp_path: Path) -> None:
    """
    Verify shrinks and saves counterexample.

    Args:
        tmp_path (Path): Temporary directory supplied by pytest.

    Returns:
        None: None. The operation completes through its documented side effects.
    """
    report = check_chart(ROOT / "examples/broken", max_examples=20, artifact_dir=tmp_path)
    assert report["status"] == "failed"
    assert report["values"] == {"replicas": 0}
    assert json.loads((tmp_path / "values.json").read_text()) == report["values"]


@pytest.mark.integration
@pytest.mark.skipif(not shutil.which("helm"), reason="Helm is required")
def test_custom_property() -> None:
    """
    Verify custom property.

    Returns:
        None: None. The operation completes through its documented side effects.
    """

    def property(resources: list[dict[str, object]]) -> None:
        """
        Require a Deployment resource for this custom-property regression.

        Args:
            resources (list[dict[str, object]]): Rendered Kubernetes resource documents.

        Returns:
            None: None. The operation completes through its documented side effects.
        """
        assert resources[0]["kind"] == "Deployment", "expected Deployment"

    report = check_chart(ROOT / "examples/configmap", properties=(property,))
    assert report["status"] == "failed"
    assert "expected Deployment" in text(report["error"])


@pytest.mark.astrivant
def test_neighbor_astrivant_audit() -> None:
    """
    Verify neighbor astrivant audit.

    Returns:
        None: None. The operation completes through its documented side effects.
    """
    path = Path(os.environ.get("ASTRIVANT_CHART", ROOT.parent / "astrivant/helm/astrivant"))
    if not path.exists():
        pytest.skip("neighboring Astrivant checkout unavailable")
    report = audit(Chart.load(path))
    assert any(mapping(r)["path"] == ("networkPolicy", "dns", "namespace") for r in sequence(report["references"]))
    assert report["findings"]  # This real-world schema currently has documentation gaps.


@pytest.mark.astrivant
@pytest.mark.integration
def test_neighbor_astrivant_render() -> None:
    """
    Verify neighbor astrivant render.

    Returns:
        None: None. The operation completes through its documented side effects.
    """
    path = os.environ.get("ASTRIVANT_CHART")
    if not path or not shutil.which("helm"):
        pytest.skip("set ASTRIVANT_CHART to opt into the full dependency-backed run")
    report = check_chart(path, max_examples=5)
    assert report["status"] == "passed", report


def test_timeout_is_a_counterexample(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """
    Verify timeout is a counterexample.

    Args:
        monkeypatch (pytest.MonkeyPatch): Pytest fixture for restoring patched dependencies.
        tmp_path (Path): Temporary directory supplied by pytest.

    Returns:
        None: None. The operation completes through its documented side effects.
    """
    import subprocess

    def timeout(*args: object, **kwargs: object) -> None:
        """
        Check timeout.

        Args:
            *args (object): Positional arguments supplied to the mocked subprocess.
            **kwargs (object): Keyword arguments supplied to the mocked subprocess.

        Returns:
            None: None. The operation completes through its documented side effects.
        """
        raise subprocess.TimeoutExpired(str(args[0]), number(kwargs["timeout"]))

    monkeypatch.setattr("hypothesis_helm.charts.rendering.Processes.run", lambda self, *args, **kwargs: timeout(*args, **kwargs))
    report = check_chart(ROOT / "examples/configmap", timeout=0.1, artifact_dir=tmp_path)
    assert report["status"] == "failed"
    assert "exceeded 0.1s" in text(report["error"])
    assert report["values"] == {}


def test_duplicate_resource_identity() -> None:
    """
    Verify duplicate resource identity.

    Returns:
        None: None. The operation completes through its documented side effects.
    """
    resource = {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "duplicate"}}
    with pytest.raises(RenderFailure, match="duplicate"):
        validate_resources([resource, resource])


@pytest.mark.integration
@pytest.mark.skipif(not shutil.which("helm"), reason="Helm is required")
def test_exhaustive_render() -> None:
    """
    Verify exhaustive render.

    Returns:
        None: None. The operation completes through its documented side effects.
    """
    report = check_chart(ROOT / "examples/workload", exhaustive=True)
    assert report["status"] == "passed", report
    assert report["domain_size"] == 24
    assert report["attempts"] == 24

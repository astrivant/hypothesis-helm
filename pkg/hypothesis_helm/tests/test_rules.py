"""
Verify explicit rule opt-outs preserve other checks, cache isolation and honest coverage.
"""

import json
from pathlib import Path

import pytest
from hypothesis import strategies as st

from hypothesis_helm.charts.audit import audit
from hypothesis_helm.charts.model import Chart
from hypothesis_helm.charts.rendering import RenderFailure, render, validate_resources
from hypothesis_helm.charts.runner import check_chart
from hypothesis_helm.cli import main
from hypothesis_helm.execution.cache import fingerprint
from hypothesis_helm.execution.render_hashes import RenderHashes
from hypothesis_helm.rules import ENVIRONMENT, RULES, load_ignored

ROOT = Path(__file__).resolve().parents[3]


def test_commented_catalog_and_explicit_policy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Keep the checked-in template complete, inert and usable with uncommented entries.

    Args:
        tmp_path (Path): Isolated caller configuration.
        monkeypatch (pytest.MonkeyPatch): Select the caller working directory.

    Returns:
        None: Every catalog entry is documented without disabling checks by default.
    """
    template = ROOT / ".hypothesis-helm.yaml"
    content = template.read_text()
    assert {line.split()[2] for line in content.splitlines() if line.startswith("  # - ")} == set(RULES)
    assert load_ignored(template, []) == []
    monkeypatch.chdir(tmp_path)
    config = tmp_path / ".hypothesis-helm.yaml"
    config.write_text("ignored:\n  - HH1008\n")
    assert load_ignored(None, ["HH2003", "HH1008"]) == ["HH1008", "HH2003"]
    assert main(["rules"]) == 0


@pytest.mark.parametrize("content", ["ignored: HH1008", "ignored: [HH9999]", "ignored: [1]", "ignore: [HH1008]", "- HH1008"])
def test_invalid_policy_fails_closed(tmp_path: Path, content: str) -> None:
    """
    Reject typos and malformed policies instead of silently disabling or enabling checks.

    Args:
        tmp_path (Path): Policy directory.
        content (str): Malformed YAML policy.

    Returns:
        None: Every malformed policy raises a useful error.
    """
    config = tmp_path / "rules.yaml"
    config.write_text(content)
    with pytest.raises(ValueError):
        load_ignored(config, [])


def test_ignored_check_does_not_hide_other_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Continue independent resource checks after disabling a duplicate or envelope rule.

    Args:
        monkeypatch (pytest.MonkeyPatch): Inherited worker policy.

    Returns:
        None: Disabled duplicates do not suppress an unrelated missing resource name.
    """
    resource = {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "same"}}
    with pytest.raises(RenderFailure, match="HH1008"):
        validate_resources([resource, resource])
    monkeypatch.setenv(ENVIRONMENT, '["HH1008"]')
    validate_resources([resource, resource])
    with pytest.raises(RenderFailure, match="HH1007"):
        validate_resources([resource, resource, {"apiVersion": "v1", "kind": "ConfigMap"}])
    monkeypatch.setenv(ENVIRONMENT, '["HH1005"]')
    with pytest.raises(RenderFailure, match="HH1007"):
        validate_resources([{}])


def test_reenabled_check_cannot_reuse_ignored_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Separate manifest and persistent cache identities when an ignored check is re-enabled.

    Args:
        tmp_path (Path): Minimal chart and fingerprint input.
        monkeypatch (pytest.MonkeyPatch): Change policy within one process and hash index.

    Returns:
        None: A cached reduced-contract success cannot hide the duplicate on the next run.
    """
    chart = Chart(tmp_path, {"type": "object"}, {})
    output = "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: repeated\n"
    output += "---\n" + output
    hashes = RenderHashes()
    monkeypatch.setenv(ENVIRONMENT, '["HH1008"]')
    before = fingerprint(tmp_path, 0, None, "none")
    render(chart, {}, rendered_output=output, hashes=hashes, stream=False)
    monkeypatch.setenv(ENVIRONMENT, "[]")
    assert before != fingerprint(tmp_path, 0, None, "none")
    with pytest.raises(RenderFailure, match="HH1008"):
        render(chart, {}, rendered_output=output, hashes=hashes, stream=False)
    assert hashes.cache_hits == 0
    assert len(hashes.validated) == 1


@pytest.mark.parametrize("exhaustive", [False, True])
def test_blocking_ignored_failure_is_not_a_witness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exhaustive: bool) -> None:
    """
    Consume ignored failures without Hypothesis rejection loops or false validation witnesses.

    Args:
        tmp_path (Path): Chart source directory.
        monkeypatch (pytest.MonkeyPatch): Deterministic renderer and policy.
        exhaustive (bool): Exercise finite and sampled runners.

    Returns:
        None: Ignored cases remain explicit and never enter successful render caches.
    """
    from hypothesis_helm.charts import runner

    chart = Chart(tmp_path, {"type": "object", "properties": {"flag": {"type": "boolean"}}, "additionalProperties": False}, {"flag": False})

    def fail(chart: Chart, values: dict[str, object], **kwargs: object) -> list[dict[str, object]]:
        """
        Simulate Helm rejecting each input before output is available.

        Args:
            chart (Chart): Unused chart identity.
            values (dict[str, object]): Input that cannot render.
            **kwargs (object): Fixed render settings.

        Returns:
            list[dict[str, object]]: Never returns output.
        """
        raise RenderFailure("deliberate template failure", "HH1001")

    monkeypatch.setattr(runner, "render", fail)
    monkeypatch.setenv(ENVIRONMENT, '["HH1001"]')
    result = check_chart(chart, max_examples=3, exhaustive=exhaustive, input_strategy=None if exhaustive else st.just({}), time_limit=10)
    assert result["status"] == "ignored"
    assert result["coverage_complete"] is False
    assert result["ignored_failures"]
    hashes = result["render_hashes"]
    assert isinstance(hashes, dict)
    assert hashes["validated_entries"] == 0
    assert result.get("failure_type") not in {"Unsatisfiable", "FailedHealthCheck"}


def test_audit_keeps_ignored_findings(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Exclude only the selected audit rule while retaining its evidence separately.

    Args:
        monkeypatch (pytest.MonkeyPatch): Disable the undocumented-values rule.

    Returns:
        None: Other audit findings remain enabled.
    """
    chart = Chart.load(ROOT / "examples/hidden-levers")
    before = audit(chart)
    monkeypatch.setenv(ENVIRONMENT, '["HH2001"]')
    after = audit(chart)
    assert before["findings"] != after["findings"]
    assert after["ignored_findings"]
    suppressed = after["ignored_findings"]
    assert isinstance(suppressed, list)
    assert all(item["code"] == "HH2001" for item in suppressed if isinstance(item, dict))


def test_cli_restores_policy_after_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """
    Reject unknown codes before work and restore the caller's environment on every exit.

    Args:
        tmp_path (Path): Missing chart location.
        monkeypatch (pytest.MonkeyPatch): Existing caller policy.
        capsys (pytest.CaptureFixture[str]): Structured CLI diagnostic capture.

    Returns:
        None: Configuration failures cannot leak policy into later invocations.
    """
    import os

    monkeypatch.setenv(ENVIRONMENT, '["HH1008"]')
    assert main(["test", str(tmp_path), "--ignore", "HH9999"]) == 2
    assert "Unknown rule codes" in json.loads(capsys.readouterr().out)["error"]
    assert os.environ[ENVIRONMENT] == '["HH1008"]'


@pytest.mark.parametrize("exhaustive", [False, True])
def test_native_workers_inherit_config(tmp_path: Path, capsys: pytest.CaptureFixture[str], exhaustive: bool) -> None:
    """
    Apply one local policy to real Helm renders in path and exhaustive worker execution.

    Args:
        tmp_path (Path): Native chart, config and output directories.
        capsys (pytest.CaptureFixture[str]): CLI reports.
        exhaustive (bool): Choose exhaustive render workers or path-property subprocesses.

    Returns:
        None: Enabled duplicates fail and disabled duplicates pass under the recorded policy.
    """
    import shutil
    from textwrap import dedent

    if shutil.which("helm") is None:
        pytest.skip("Helm is required")
    chart = tmp_path / "charts" / "chart"
    (chart / "templates").mkdir(parents=True)
    (chart / "Chart.yaml").write_text("apiVersion: v2\nname: rule-check\nversion: 1.0.0\n")
    (chart / "values.yaml").write_text("setting: false\n" if exhaustive else "setting: value\n")
    (chart / "values.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {"setting": {"type": "boolean" if exhaustive else "string"}},
                "additionalProperties": False,
            }
        )
    )
    manifest = dedent("""
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: duplicate
        data:
          setting: {{ .Values.setting | quote }}
    """)
    (chart / "templates" / "configmap.yaml").write_text(manifest + "\n---\n" + manifest)
    policy = tmp_path / "rules.yaml"
    policy.write_text("ignored: [HH1008]\n")
    args = [
        "test",
        str(chart if exhaustive else chart.parent),
        "--no-cache",
        "--jobs",
        "2",
        "--max-examples",
        "2",
        "--artifact-dir",
        str(tmp_path / "reports"),
    ]
    if exhaustive:
        args.append("--exhaustive")
    assert main(args) == 1
    before = json.loads(capsys.readouterr().out)
    assert (before if exhaustive else before["charts"][0])["status"] == "failed"
    assert main([*args, "--config", str(policy), "--ignore", "HH1010", "--kubeconform", "--kubeconform-binary", "missing-kubeconform"]) == 0
    after = json.loads(capsys.readouterr().out)
    assert after["ignored_rules"] == ["HH1008", "HH1010"]
    assert (after if exhaustive else after["charts"][0])["status"] == "passed"

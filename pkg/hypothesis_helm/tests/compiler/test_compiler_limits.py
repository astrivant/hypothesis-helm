"""
Keep helper analysis configurable, conservative at its boundary, and consistent across workers.
"""

import json
import shutil
from pathlib import Path
from textwrap import dedent

import pytest

from hypothesis_helm.charts.model import Chart
from hypothesis_helm.charts.testing.rendering import render
from hypothesis_helm.charts.values import yamlio
from hypothesis_helm.cli import argument_parser, main
from hypothesis_helm.compiler.asts.contracts import Contracts
from hypothesis_helm.compiler.limits import DEFAULT_LIMITS
from hypothesis_helm.compiler.passes.domains import project
from hypothesis_helm.compiler.passes.rejections import matches_rejection
from hypothesis_helm.environment import refresh_env
from hypothesis_helm.exceptions.rendering import RenderFailure
from hypothesis_helm.execution.state.cache import fingerprint
from hypothesis_helm.schemas.configuration.policy import ENVIRONMENT, load_policy
from hypothesis_helm.tests.fixtures.cli import result_text


def helper_chart(directory: Path, depth: int) -> Chart:
    """
    Build independent rejection and direct-output chains of exactly the requested depth.

    Args:
        directory (Path): Temporary chart directory.
        depth (int): Number of nested helper invocations, including the first call.

    Returns:
        Chart: Chart exercising both analyses without external dependencies.
    """
    (directory / "templates").mkdir()
    (directory / "Chart.yaml").write_text(yamlio.dump({"apiVersion": "v2", "name": "helpers", "version": "1.0.0"}))
    (directory / "values.yaml").write_text(yamlio.dump({"name": "example", "enabled": True}))
    (directory / "values.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {"name": {"type": "string"}, "enabled": {"type": "boolean"}},
            }
        )
    )
    helpers = []
    for kind, terminal in (
        ("output", "{{ .Values.name }}"),
        ("reject", '{{ if eq .Values.name "reject" }}{{ fail "rejected name" }}{{ end }}'),
    ):
        for index in range(depth):
            body = terminal if index == depth - 1 else '{{ include "' + kind + str(index + 1) + '" . }}'
            helpers.append('{{ define "' + kind + str(index) + '" }}' + body + "{{ end }}")
    (directory / "templates/_helpers.tpl").write_text("\n".join(helpers))
    (directory / "templates/NOTES.txt").write_text('{{ include "reject0" . }}')
    (directory / "templates/config.yaml").write_text(
        dedent("""
        apiVersion: v1
        kind: Pod
        metadata:
          name: helpers
          annotations:
            enabled: {{ .Values.enabled | quote }}
        spec:
          containers:
            - name: app
              image: example
          volumes:
            - name: credentials
              secret:
                secretName: {{ include "output0" . | quote }}
        """)
    )
    return Chart.load(directory)


@pytest.mark.parametrize(("depth", "limit", "supported"), [(16, None, True), (17, None, False), (20, 32, True), (2, 1, False)])
def test_analysis_depth_boundary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, depth: int, limit: int | None, supported: bool) -> None:
    """
    Apply one budget to rejection prediction and destination projection without dropping unknown cases.

    Args:
        tmp_path (Path): Chart directory.
        monkeypatch (pytest.MonkeyPatch): Isolate the inherited compiler policy.
        depth (int): Actual helper chain depth.
        limit (int | None): Requested override or the default budget.
        supported (bool): Whether the complete chain fits within that budget.

    Returns:
        None: Both analyses agree at the exact boundary, with native Helm confirming rejections.
    """
    monkeypatch.setenv(ENVIRONMENT, json.dumps({"compiler": {} if limit is None else {"max_call_depth": limit}}))
    refresh_env()
    chart = helper_chart(tmp_path, depth)
    model = Contracts.build(chart.path)
    rejection = model.predict({**chart.defaults, "name": "reject"})
    assert (rejection is not None) is supported
    assert model.predict(chart.defaults) is None
    rules, diagnostics = project(chart.path, chart.schema)
    assert any(rule["path"] == ["name"] for rule in rules) is supported
    if not supported:
        assert f"helper call depth exceeds compiler limit {limit or 16}" in str(diagnostics)
    if shutil.which("helm") is not None:
        render(chart, {})
        with pytest.raises(RenderFailure) as failure:
            render(chart, {"name": "reject"})
        if rejection is not None:
            assert matches_rejection(str(failure.value), rejection)


def test_recursive_helpers_remain_unresolved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Keep cycle safety and unrelated limits when raising the helper budget.

    Args:
        tmp_path (Path): Chart directory.
        monkeypatch (pytest.MonkeyPatch): Raise the analysis depth.

    Returns:
        None: An infinite call cycle cannot establish a constraint or rejection.
    """
    monkeypatch.setenv(ENVIRONMENT, json.dumps({"compiler": {"max_call_depth": 64}}))
    refresh_env()
    chart = helper_chart(tmp_path, 1)
    (chart.path / "templates/_helpers.tpl").write_text(
        dedent("""
        {{ define "output0" }}{{ include "output0" . }}{{ end }}
        {{ define "reject0" }}{{ include "reject0" . }}{{ fail "unreachable" }}{{ end }}
        """)
    )
    assert Contracts.build(chart.path).predict(chart.defaults) is None
    rules, diagnostics = project(chart.path, chart.schema)
    assert rules == []
    assert "recursive" in str(diagnostics)


@pytest.mark.parametrize(
    "compiler",
    [
        None,
        [],
        32,
        {"typo": 32},
        {"max_call_depth": 0},
        {"max_call_depth": -1},
        {"max_call_depth": True},
        {"max_call_depth": 1.5},
        {"max_call_depth": "32"},
    ],
)
def test_invalid_compiler_configuration(tmp_path: Path, compiler: object) -> None:
    """
    Reject malformed or unbounded compiler settings before any chart work starts.

    Args:
        tmp_path (Path): Config directory.
        compiler (object): Unsupported settings or invalid depth.

    Returns:
        None: Invalid policy raises an actionable configuration error.
    """
    config = tmp_path / "policy.yaml"
    config.write_text(yamlio.dump({"compiler": compiler}))
    with pytest.raises(ValueError, match="compiler"):
        load_policy(config)


@pytest.mark.parametrize("command", ["audit", "generate", "test", "scan", "run"])
def test_compiler_option_removed(command: str) -> None:
    """
    Require compiler settings in configuration instead of command-line overrides.

    Args:
        command (str): Command performing or scheduling compiler analysis.

    Returns:
        None: Every entry point rejects the removed compiler option.
    """
    with pytest.raises(SystemExit) as error:
        argument_parser().parse_args([command, "example", "--compiler-call-depth", "32"])
    assert error.value.code == 2


def test_policy_configuration_and_cache_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Freeze each chart's budget and prevent cache reuse after a configuration change.

    Args:
        tmp_path (Path): Config and chart directory.
        monkeypatch (pytest.MonkeyPatch): Apply resolved policies as the coordinator does.

    Returns:
        None: Old models retain their budget, and newly built models use the updated configuration.
    """
    config = tmp_path.parent / f"{tmp_path.name}-policy.yaml"
    config.write_text(yamlio.dump({"compiler": {"max_call_depth": 24}}))
    chart = helper_chart(tmp_path, 20)
    monkeypatch.setenv(ENVIRONMENT, json.dumps(load_policy(config)))
    refresh_env()
    original = Contracts.build(chart.path)
    previous = fingerprint(tmp_path, 0, None, "none")
    config.write_text(yamlio.dump({"compiler": {"max_call_depth": 32}}))
    monkeypatch.setenv(ENVIRONMENT, json.dumps(load_policy(config)))
    refresh_env()
    assert original.max_call_depth == 24
    assert Contracts.build(chart.path).max_call_depth == 32
    assert fingerprint(tmp_path, 0, None, "none") != previous


@pytest.mark.skipif(shutil.which("helm") is None, reason="requires Helm")
@pytest.mark.parametrize("scoped", [False, True])
def test_parallel_workers_inherit_compiler_configuration(tmp_path: Path, capfd: pytest.CaptureFixture[str], scoped: bool) -> None:
    """
    Exercise the real CLI, inherited policy, and path-worker interpreters together.

    Args:
        tmp_path (Path): Chart and artifact directories.
        capfd (pytest.CaptureFixture[str]): Capture the saved report location from the CLI summary.
        scoped (bool): Configure depth globally or only for a matching chart/source selector.

    Returns:
        None: Worker rejection reports retain the configured budgets instead of their own defaults.
    """
    source = tmp_path / "charts"
    source.mkdir()
    directory = source / "first"
    directory.mkdir()
    helper_chart(directory, 20)
    if scoped:
        second = source / "second"
        second.mkdir()
        helper_chart(second, 20)
        (second / "Chart.yaml").write_text(yamlio.dump({"apiVersion": "v2", "name": "ordinary", "version": "1.0.0"}))
    config = tmp_path / "policy.yaml"
    configured: dict[str, object] = {"compiler": {"max_call_depth": 1 if scoped else 32, "max_files": 4321, "max_steps": 23456}}
    if scoped:
        configured["input_constraints"] = [
            {
                "charts": [{"sources": [str(source)], "names": ["helpers"]}],
                "path": "$",
                "compiler": {"max_call_depth": 32},
            }
        ]
    config.write_text(yamlio.dump(configured))
    assert (
        main(
            [
                "test",
                str(source),
                "--filter",
                "--config",
                str(config),
                "--jobs",
                "2",
                "--max-examples",
                "2",
                "--chart-timeout",
                "30s",
                "--no-cache",
                "--artifact-dir",
                str(tmp_path / "results"),
                "--log-file",
                "/dev/stderr",
            ]
        )
        == 0
    )
    report = json.loads(result_text(capfd.readouterr().out))
    expected = {**DEFAULT_LIMITS, "max_call_depth": 32, "max_files": 4321, "max_steps": 23456}
    assert report["settings"]["input_policy"]["compiler"] == {**expected, "max_call_depth": 1 if scoped else 32}
    assert report["charts"][0]["compiler_limits"] == expected
    assert report["charts"][0]["audit"]["compiler_limits"] == expected
    phases = [phase for phase in report["charts"][0]["phases"] if "worker_pid" in phase]
    assert len(phases) == 2
    assert all(phase["configuration_rejections"]["max_call_depth"] == 32 for phase in phases)
    assert all(phase["configuration_rejections"]["compiler_limits"] == expected for phase in phases)
    if scoped:
        other = report["charts"][1]
        assert other["compiler_limits"] == {**expected, "max_call_depth": 1}
        other_phases = [phase for phase in other["phases"] if "worker_pid" in phase]
        assert len(other_phases) == 2
        assert all(phase["configuration_rejections"]["max_call_depth"] == 1 for phase in other_phases)

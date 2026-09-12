"""
Verify CI index normalization, explicit overrides, and action invocation boundaries.
"""

import json
import subprocess
from pathlib import Path
from typing import TextIO

import pytest

from hypothesis_helm.cli import main
from hypothesis_helm.execution.processes import Processes
from hypothesis_helm.integrations import github_action
from hypothesis_helm.integrations.sharding import Shard, resolve_shard


@pytest.mark.parametrize(
    ("environment", "expected"),
    [
        ({}, None),
        ({"GITHUB_ACTIONS": "true", "GITHUB_JOB": "tests"}, None),
        ({"CIRCLE_NODE_INDEX": "0", "CIRCLE_NODE_TOTAL": "4"}, Shard(1, 4)),
        ({"CIRCLE_NODE_INDEX": "3", "CIRCLE_NODE_TOTAL": "4"}, Shard(4, 4)),
        ({"CI_NODE_INDEX": "1", "CI_NODE_TOTAL": "4"}, Shard(1, 4)),
        ({"CI_NODE_INDEX": "4", "CI_NODE_TOTAL": "4"}, Shard(4, 4)),
        ({"CI_NODE_TOTAL": "1"}, None),
        ({"CI_NODE_INDEX": "1", "CI_NODE_TOTAL": "1"}, None),
        ({"CIRCLE_NODE_INDEX": "0", "CIRCLE_NODE_TOTAL": "1"}, None),
        ({"HYPOTHESIS_HELM_JOB_INDEX": "0", "HYPOTHESIS_HELM_JOB_TOTAL": "4"}, Shard(1, 4)),
        ({"HYPOTHESIS_HELM_JOB_INDEX": "3", "HYPOTHESIS_HELM_JOB_TOTAL": "4"}, Shard(4, 4)),
    ],
)
def test_ci_coordinates(environment: dict[str, str], expected: Shard | None) -> None:
    """
    Normalize provider conventions without guessing GitHub matrix position.

    Args:
        environment (dict[str, str]): Simulated CI variables.
        expected (Shard | None): Expected one-based partition.

    Returns:
        None: Known coordinates normalize correctly and nonparallel jobs remain unsharded.
    """
    assert resolve_shard("auto", environment)[0] == expected


@pytest.mark.parametrize(
    "environment",
    [
        {"CIRCLE_NODE_INDEX": "1"},
        {"CI_NODE_TOTAL": "4"},
        {"CI_NODE_INDEX": "0", "CI_NODE_TOTAL": "4"},
        {"CIRCLE_NODE_INDEX": "4", "CIRCLE_NODE_TOTAL": "4"},
        {"HYPOTHESIS_HELM_JOB_INDEX": "x", "HYPOTHESIS_HELM_JOB_TOTAL": "4"},
        {
            "CIRCLE_NODE_INDEX": "0",
            "CIRCLE_NODE_TOTAL": "2",
            "CI_NODE_INDEX": "1",
            "CI_NODE_TOTAL": "2",
        },
    ],
)
def test_ci_rejects_ambiguous_or_invalid_coordinates(environment: dict[str, str]) -> None:
    """
    Refuse incomplete or conflicting auto-detection while permitting explicit overrides.

    Args:
        environment (dict[str, str]): Invalid or ambiguous CI coordinates.

    Returns:
        None: Auto fails and explicit or disabled modes take precedence.
    """
    with pytest.raises(ValueError):
        resolve_shard("auto", environment)
    assert resolve_shard(Shard(2, 3), environment) == (Shard(2, 3), "explicit")
    assert resolve_shard("none", environment) == (None, "disabled")


def test_cli_defaults_to_ci_detection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Apply automatic partitioning at the Helm command boundary.

    Args:
        tmp_path (Path): Directory receiving generated suites.
        monkeypatch (pytest.MonkeyPatch): Fixture restoring simulated CI variables.

    Returns:
        None: Auto uses the CI partition and none disables it.
    """
    monkeypatch.setenv("CIRCLE_NODE_INDEX", "0")
    monkeypatch.setenv("CIRCLE_NODE_TOTAL", "2")
    args = ["test", "examples/workload", "--collect-only", "--artifact-dir", str(tmp_path)]
    assert main(args) == 0
    report = json.loads((tmp_path / "shards/1-of-2/report.json").read_text())
    assert report["shard"]["index"] == 1
    assert main([*args, "--shard", "none"]) == 0
    assert json.loads((tmp_path / "report.json").read_text())["shard"] is None


@pytest.mark.parametrize("exit_code", [0, 1])
@pytest.mark.parametrize("security", [False, True])
def test_action_preserves_arguments_outputs_and_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exit_code: int, security: bool
) -> None:
    """
    Pass untrusted-looking input literally and export artifacts even on test failure.

    Args:
        tmp_path (Path): Workspace containing action output files.
        monkeypatch (pytest.MonkeyPatch): Fixture replacing the Helm process boundary.
        exit_code (int): Simulated successful or failed Helm result.
        security (bool): Whether the optional scanner reports a security failure.

    Returns:
        None: The action uses an argument vector, preserves status, and exports shard paths.
    """
    output = tmp_path / "outputs"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setenv("HH_ARTIFACT_DIR", str(tmp_path / "reports"))
    monkeypatch.setenv("HH_CHART", "$(touch unexpected); chart")
    monkeypatch.setenv("HH_MATCH", "replicas or image")
    monkeypatch.setenv("HH_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("HH_RERUN", "failed")
    monkeypatch.setenv("HH_DISABLE_SCHEMA_CACHING", "true")
    monkeypatch.setenv("HH_CACHE", "false")
    monkeypatch.setenv("HH_KUBECONFORM", "true")
    monkeypatch.setenv("HH_SCHEMA_VERSION", "1.35.0")
    monkeypatch.setenv("HH_SCHEMA_OFFLINE", "true")
    monkeypatch.setenv("HYPOTHESIS_HELM_JOB_INDEX", "1")
    monkeypatch.setenv("HYPOTHESIS_HELM_JOB_TOTAL", "3")
    calls: list[list[str]] = []

    def execute(
        self: Processes, command: list[str], *, stdout: TextIO, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        """
        Capture a Helm invocation and emulate streaming a manifest.

        Args:
            self (Processes): Process owner replaced by this test.
            command (list[str]): Helm argument vector.
            stdout (TextIO): Open JSON manifest destination.
            **kwargs (object): Remaining subprocess options.

        Returns:
            subprocess.CompletedProcess[str]: Simulated Helm result.
        """
        calls.append(command)
        stdout.write('{"kind":"ConfigMap"}\n')
        return subprocess.CompletedProcess(command, exit_code)

    monkeypatch.setattr(Processes, "run", execute)
    monkeypatch.setenv("HH_KUBESEC", str(security).lower())
    monkeypatch.setattr(github_action, "prepare", lambda *args, **kwargs: "{}")
    scan_calls: list[dict[str, object]] = []

    def scan(*args: object, **kwargs: object) -> int:
        """
        Record scanner ownership and simulate a security failure.

        Args:
            *args (object): Input manifest and schema configuration.
            **kwargs (object): Shard and worker options.

        Returns:
            int: A nonzero security scan result.
        """
        scan_calls.append(kwargs)
        return 1

    monkeypatch.setattr(github_action, "scan", scan)
    expected_status = exit_code or int(security)
    assert github_action.main() == expected_status
    if security:
        assert scan_calls[0]["pre_sharded"] is True
        assert scan_calls[0]["validate_rest"] is True
        assert scan_calls[0]["shard"] == Shard(2, 3)
    command = calls[0]
    assert command[:3] == ["helm", "hypothesis", "test"]
    assert "$(touch unexpected); chart" in command[3]
    assert command[command.index("--shard") + 1] == "2/3"
    assert command[command.index("--match") + 1] == "replicas or image"
    assert command[command.index("--cache-dir") + 1] == str(tmp_path / "cache")
    assert command[command.index("--rerun") + 1] == ("all" if security else "failed")
    assert "--disable-schema-caching" in command
    assert "--no-cache" in command
    assert ("--kubeconform" in command) is (not security)
    if not security:
        assert "--schema-offline" in command
        assert command[command.index("--schema-version") + 1] == "1.35.0"
    assert (tmp_path / "reports/shards/2-of-3/manifests.jsonl").is_file()
    values = output.read_text()
    assert "exit-code<<" in values
    assert f"\n{expected_status}\n" in values
    assert "shard<<" in values
    assert "\n2/3\n" in values
    assert "report-dir<<" in values

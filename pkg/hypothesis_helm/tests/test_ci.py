"""
Verify CI index normalization, explicit overrides, and action invocation boundaries.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from textwrap import dedent
from typing import TextIO

import pytest

from hypothesis_helm.cli import main
from hypothesis_helm.execution.processes import Processes
from hypothesis_helm.integrations import github_action
from hypothesis_helm.integrations.sharding import Shard, resolve_shard
from hypothesis_helm.schemas.contracts import mapping


@pytest.mark.integration
@pytest.mark.parametrize("working_entrypoint", [True, False])
def test_action_plugin_installation(tmp_path: Path, working_entrypoint: bool) -> None:
    """
    Verify Helm 4 registers the action plugin where following steps look for it.

    Args:
        tmp_path (Path): Isolated action checkout and runner directories.
        working_entrypoint (bool): Whether the installed command can start successfully.

    Returns:
        None: Subsequent steps resolve the plugin, or installation fails before publishing paths.
    """
    from ruamel.yaml import YAML

    from hypothesis_helm.schemas.contracts import sequence

    helm = shutil.which("helm")
    if helm is None:
        pytest.skip("Helm 4 is required")
    version = subprocess.run([helm, "version", "--short"], capture_output=True, text=True, check=True).stdout
    if not version.startswith("v4."):
        pytest.skip("The action requires Helm 4")
    root = Path(__file__).resolve().parents[3]
    document = mapping(YAML(typ="safe").load((root / "action.yml").read_text()))
    steps = [mapping(step) for step in sequence(mapping(document["runs"])["steps"])]
    install = next(step for step in steps if step.get("id") == "install")
    prepare_schemas = next(step for step in steps if step.get("name") == "Prepare local Kubernetes schemas")
    source = tmp_path / "main"
    scripts = source / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy2(root / "plugin.yaml", source / "plugin.yaml")
    (scripts / "install.sh").write_text(
        dedent(
            """
            #!/bin/sh
            exit 0
            """
        ).lstrip()
    )
    (scripts / "run.sh").write_text(
        dedent(
            f"""
            #!/bin/sh
            printf '%s\\n' "$@"
            exit {0 if working_entrypoint else 7}
            """
        ).lstrip()
    )
    for script in scripts.iterdir():
        script.chmod(0o755)
    output = tmp_path / "github-output"
    environment = dict(
        os.environ,
        ACTION_PATH=str(source),
        RUNNER_TEMP=str(tmp_path),
        GITHUB_OUTPUT=str(output),
        HELM_DATA_HOME=str(tmp_path / "unrelated-data"),
        HELM_PLUGINS=str(tmp_path / "unrelated-plugins"),
    )
    result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", str(install["run"])],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == (0 if working_entrypoint else 7), result.stdout + result.stderr
    assert not (tmp_path / "unrelated-data").exists()
    assert not (tmp_path / "unrelated-plugins").exists()
    if not working_entrypoint:
        assert not output.exists()
        return
    outputs = dict(line.split("=", 1) for line in output.read_text().splitlines())
    assert Path(outputs["plugins"]) == Path(outputs["data"]) / "plugins"
    for name in ("Prepare local Kubernetes schemas", "Test chart values", "Export minimal example values"):
        step = next(step for step in steps if step.get("name") == name)
        assert mapping(step["env"])["HELM_DATA_HOME"] == "${{ steps.install.outputs.data }}"
        assert mapping(step["env"])["HELM_PLUGINS"] == "${{ steps.install.outputs.plugins }}"
    for offline in ("false", "true"):
        result = subprocess.run(
            ["bash", "-euo", "pipefail", "-c", str(prepare_schemas["run"])],
            env=dict(
                environment,
                HELM_DATA_HOME=outputs["data"],
                HELM_PLUGINS=outputs["plugins"],
                SCHEMA_OFFLINE=offline,
                SCHEMA_VERSION="1.35.0",
                SCHEMA_CACHE_DIR=str(tmp_path / "schemas"),
                KUBECONFORM_BINARY="kubeconform",
            ),
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.splitlines()[0] == "schemas"
        assert ("--schema-offline" in result.stdout.splitlines()) == (offline == "true")


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
@pytest.mark.parametrize("keyword", ["", "replicas or image"])
def test_action_preserves_arguments_outputs_and_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exit_code: int, security: bool, keyword: str
) -> None:
    """
    Pass untrusted-looking input literally and export artifacts even on test failure.

    Args:
        tmp_path (Path): Workspace containing action output files.
        monkeypatch (pytest.MonkeyPatch): Fixture replacing the Helm process boundary.
        exit_code (int): Simulated successful or failed Helm result.
        security (bool): Whether the optional scanner reports a security failure.
        keyword (str): Optional pytest selection, omitted entirely when empty.

    Returns:
        None: The Bash invocation preserves literal values, status and shard artifact paths.
    """
    output = tmp_path / "outputs"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setenv("HH_ARTIFACT_DIR", str(tmp_path / "reports"))
    monkeypatch.setenv("HH_CHART", "$(touch unexpected); chart")
    monkeypatch.setenv("HH_MATCH", keyword)
    monkeypatch.setenv("HH_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("HH_RERUN", "failed")
    monkeypatch.setenv("HH_DISABLE_SCHEMA_CACHING", "true")
    monkeypatch.setenv("HH_CACHE", "false")
    monkeypatch.setenv("HH_KUBECONFORM", "true")
    monkeypatch.setenv("HH_SCHEMA_VERSION", "1.35.0")
    monkeypatch.setenv("HH_SCHEMA_OFFLINE", "true")
    monkeypatch.setenv("HYPOTHESIS_HELM_JOB_INDEX", "1")
    monkeypatch.setenv("HYPOTHESIS_HELM_JOB_TOTAL", "3")
    binary = tmp_path / "helm"
    capture = tmp_path / "arguments.json"
    binary.write_text(
        dedent(
            f"""
            #!{sys.executable}
            import json, os, sys
            from pathlib import Path
            Path(os.environ["CAPTURE_ARGS"]).write_text(json.dumps(["helm", *sys.argv[1:]]))
            print(json.dumps(dict(kind="ConfigMap")))
            sys.exit(int(os.environ["FAKE_HELM_STATUS"]))
            """
        ).removeprefix("\n")
    )
    binary.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("CAPTURE_ARGS", str(capture))
    monkeypatch.setenv("FAKE_HELM_STATUS", str(exit_code))
    calls: list[list[str]] = []

    def execute(self: Processes, command: list[str], *, stdout: TextIO, **kwargs: object) -> subprocess.CompletedProcess[str]:
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
        result = subprocess.run(
            command,
            env={key: str(value) for key, value in mapping(kwargs["env"]).items()},
            stdout=stdout,
            text=True,
            check=False,
        )
        calls.append(json.loads(capture.read_text()))
        return result

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
    if keyword:
        assert command[command.index("--match") + 1] == keyword
    else:
        assert "--match" not in command
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


@pytest.mark.parametrize(("provider", "defer_failure"), [("gitlab", False), ("circleci", False), ("circleci", True)])
@pytest.mark.parametrize("security", [False, True])
@pytest.mark.parametrize("helm_status", [0, 1])
def test_remote_ci_commands(tmp_path: Path, provider: str, defer_failure: bool, security: bool, helm_status: int) -> None:
    """
    Exercise published job scripts with literal paths, shard routing and validator failures.

    Args:
        tmp_path (Path): Mock executable and report directory.
        provider (str): Remote configuration to exercise.
        defer_failure (bool): Persist CircleCI workspace evidence before failing the job.
        security (bool): Whether workload security routing is enabled.
        helm_status (int): Simulated Helm success or failure.

    Returns:
        None: Scripts select the right validators and retain Helm failure precedence.
    """
    from ruamel.yaml import YAML

    from hypothesis_helm.schemas.contracts import sequence

    root = Path(__file__).resolve().parents[3]
    document = mapping(YAML(typ="safe").load((root / "ci" / f"{provider}.yml").read_text()))
    if provider == "gitlab":
        commands = sequence(mapping(document["helm-properties"])["script"])
        script = "\n".join(str(command) for command in commands)
    else:
        steps = sequence(mapping(mapping(document["commands"])["test"])["steps"])
        script = str(mapping(mapping(steps[0])["run"])["command"])
    plugins = tmp_path / "plugin root"
    scanner = plugins / "hypothesis/.plugin-venv/bin/hypothesis-helm-kubesec"
    scanner.parent.mkdir(parents=True)
    binary = tmp_path / "helm"
    stub = dedent(
        f"""
        #!{sys.executable}
        import json, os, sys
        from pathlib import Path
        if sys.argv[1:2] == ["env"]:
            print(os.environ["FAKE_PLUGINS"])
            sys.exit(0)
        name = Path(sys.argv[0]).name
        with Path(os.environ["CAPTURE_ARGS"]).open("a") as stream:
            print(json.dumps([name, *sys.argv[1:]]), file=stream)
        print(json.dumps(dict(kind="ConfigMap")))
        sys.exit(int(os.environ["FAKE_HELM_STATUS"]) if name == "helm" else 2)
        """
    ).removeprefix("\n")
    for executable in (binary, scanner):
        executable.write_text(stub)
        executable.chmod(0o755)
    capture = tmp_path / "commands.jsonl"
    chart = "$(touch unexpected); chart with spaces"
    environment = {
        **os.environ,
        "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"],
        "FAKE_PLUGINS": str(plugins),
        "FAKE_HELM_STATUS": str(helm_status),
        "CAPTURE_ARGS": str(capture),
        "HELM_CHART": chart,
        "HH_CHART": chart,
        "KUBESEC_ENABLED": str(security).lower(),
        "HH_KUBESEC": str(security).lower(),
        "KUBESEC_JOBS": "auto",
        "HH_KUBESEC_JOBS": "auto",
        "K8S_VERSION": "1.35.0",
        "HH_SCHEMA_VERSION": "1.35.0",
        "SCHEMA_CACHE_DIR": "schema cache",
        "HH_SCHEMA_CACHE_DIR": "schema cache",
        "SHARD_INDEX": "2",
        "SHARD_TOTAL": "3",
        "CIRCLE_NODE_INDEX": "1",
        "CIRCLE_NODE_TOTAL": "3",
        "HH_JOBS": "auto",
        "HH_MAX_EXAMPLES": "50",
        "HH_SEED": "0",
        "SAMPLE_RANDOM": "70",
        "SAMPLE_MIN_CASES": "32",
        "HH_SAMPLE_RANDOM": "70",
        "HH_SAMPLE_MIN_CASES": "32",
        "HH_ARTIFACT_DIR": "reports/hypothesis-helm",
        "CI_PIPELINE_ID": "123",
        "CIRCLE_WORKFLOW_ID": "workflow-123",
        "HH_REPORT_GROUP": "chart",
        "HH_DEFER_FAILURE": str(defer_failure).lower(),
    }
    result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", script],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    expected_status = helm_status or (2 if security else 0)
    assert result.returncode == (0 if defer_failure else expected_status), result.stderr
    if provider == "circleci":
        assert (tmp_path / "reports/hypothesis-helm/exit-code.txt").read_text().strip() == str(expected_status)
    calls = [json.loads(line) for line in capture.read_text().splitlines()]
    command = calls[0]
    assert command[:4] == ["helm", "hypothesis", "test", chart]
    assert command[command.index("--sample-random") + 1] == "70"
    assert command[command.index("--sample-min-cases") + 1] == "32"
    assert ("--kubeconform" in command) is (not security)
    assert "--schema-offline" in command
    assert command[command.index("--shard") + 1] == "2/3"
    assert command[command.index("--run-id") + 1] == ("123-1.35.0" if provider == "gitlab" else "workflow-123-chart")
    assert len(calls) == (2 if security else 1)
    if security:
        assert "--pre-sharded" in calls[1] and "--validate-rest" in calls[1]
        assert "--schema-offline" in calls[1]
    assert not (tmp_path / "unexpected").exists()


@pytest.mark.parametrize(
    ("provider", "outcome"),
    [(provider, outcome) for provider in ("gitlab", "circleci", "github") for outcome in ("passed", "failed", "missing")]
    + [("circleci", "validator")],
)
def test_ci_aggregation_commands(tmp_path: Path, provider: str, outcome: str) -> None:
    """
    Execute the published aggregation scripts with transported reports and an idle shard.

    Args:
        tmp_path (Path): Isolated downloaded artifacts and final bundle.
        provider (str): CI configuration whose Bash command is exercised.
        outcome (str): Successful, failing, incomplete, or externally rejected shard evidence.

    Returns:
        None: Complete evidence produces one bundle and missing idle reports fail closed.
    """
    from ruamel.yaml import YAML

    from hypothesis_helm.schemas.contracts import sequence

    root = Path(__file__).resolve().parents[3]
    source = root / (".github/workflows/action.yml" if provider == "github" else f"ci/{provider}.yml")
    document = mapping(YAML(typ="safe").load(source.read_text()))
    if provider == "gitlab":
        script = str(sequence(mapping(document["helm-report"])["script"])[0])
        artifact_root = tmp_path / "reports/hypothesis-helm/1.35.0"
        final = tmp_path / "reports/final/1.35.0"
    else:
        job = mapping(mapping(document["jobs"])["aggregate"])
        steps = [mapping(step) for step in sequence(job["steps"])]
        artifact_root = tmp_path / ("workspace/chart" if provider == "circleci" else "downloaded")
        final = tmp_path / "reports/final"
        if provider == "circleci":
            run = next(mapping(step["run"]) for step in steps if isinstance(step.get("run"), dict) and "Write" in str(step["run"]))
            script = str(run["command"])
            script = script.replace("/tmp/hypothesis-helm-aggregation", str(tmp_path / "workspace"))
        else:
            script = next(str(step["run"]) for step in steps if str(step.get("name", "")).startswith("Write"))
    run_id = "123-1.35.0" if provider == "gitlab" else "workflow-123-chart"
    nodes = ["test_chart_values.py::test_alpha", "test_chart_values.py::test_beta"]
    reports = []
    for index in range(1, 4):
        selected = [node for node in nodes if Shard(index, 3).includes(node)]
        failed = outcome == "failed" and nodes[0] in selected
        junit = (
            "<testsuites><testsuite>"
            + "".join(
                f'<testcase name="{node}">' + ('<failure message="chart defect"/>' if failed and node == nodes[0] else "") + "</testcase>"
                for node in selected
            )
            + "</testsuite></testsuites>"
        )
        record = {
            "run_id": run_id,
            "suite_fingerprint": "same-suite",
            "suite": "/other-runner/generated",
            "status": "failed" if failed else "passed",
            "exit_code": int(failed),
            "jobs": 2,
            "started_epoch": 1000,
            "elapsed_seconds": 1,
            "junit_xml": junit,
            "junit_sha256": hashlib.sha256(junit.encode()).hexdigest(),
            "shard": {
                "index": index,
                "total": 3,
                "matched": len(nodes),
                "matched_digest": hashlib.sha256(json.dumps(sorted(nodes)).encode()).hexdigest(),
                "selected": len(selected),
                "tests": selected,
            },
        }
        reports.append(record)
        if outcome == "missing" and not selected:
            continue
        destination = artifact_root / str(index)
        if provider == "gitlab":
            destination = destination / "shards" / f"{index}-of-3"
        destination.mkdir(parents=True)
        (destination / "report.json").write_text(json.dumps(record))
        (destination / "exit-code.txt").write_text(str(2 if outcome == "validator" and index == 1 else int(failed)))
    assert any(not mapping(record["shard"])["selected"] for record in reports)
    result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", script],
        cwd=tmp_path,
        env=dict(
            os.environ,
            PATH=str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"],
            CI_PIPELINE_ID="123",
            K8S_VERSION="1.35.0",
            SHARD_TOTAL="3",
            CIRCLE_WORKFLOW_ID="workflow-123",
            HH_REPORT_GROUP="chart",
            HH_SHARDS="3",
            HH_RUN_ID=run_id,
        ),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == {"passed": 0, "failed": 1, "missing": 2, "validator": 2}[outcome], result.stdout + result.stderr
    if outcome == "missing":
        assert not final.exists()
    else:
        assert (final / "report.pdf").is_file()
        report = json.loads((final / "report.json").read_text())
        assert report["properties"]["selected"] == report["properties"]["tests"] == 2
        assert len(report["shards"]) == 3

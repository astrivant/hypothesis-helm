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
from hypothesis_helm.environment import refresh_env
from hypothesis_helm.execution.runtime.processes import Processes
from hypothesis_helm.integrations import github_action
from hypothesis_helm.integrations.sharding import Shard, resolve_shard
from hypothesis_helm.schemas.contracts import mapping
from hypothesis_helm.tests import PROJECT_ROOT


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
    root = PROJECT_ROOT
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
    refresh_env()
    monkeypatch.setenv("CIRCLE_NODE_TOTAL", "2")
    refresh_env()
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
    refresh_env()
    monkeypatch.setenv("HH_ARTIFACT_DIR", str(tmp_path / "reports"))
    refresh_env()
    monkeypatch.setenv("HH_CHART", "$(touch unexpected); chart")
    refresh_env()
    monkeypatch.setenv("HH_MATCH", keyword)
    refresh_env()
    monkeypatch.setenv("HH_CACHE_DIR", str(tmp_path / "cache"))
    refresh_env()
    monkeypatch.setenv("HH_RERUN", "failed")
    refresh_env()
    monkeypatch.setenv("HH_DISABLE_SCHEMA_CACHING", "true")
    refresh_env()
    monkeypatch.setenv("HH_CACHE", "false")
    refresh_env()
    monkeypatch.setenv("HH_VALIDATE_SCHEMAS", "true")
    refresh_env()
    monkeypatch.setenv("HH_SCHEMA_VERSION", "1.35.0")
    refresh_env()
    monkeypatch.setenv("HH_SCHEMA_OFFLINE", "true")
    refresh_env()
    monkeypatch.setenv("HYPOTHESIS_HELM_JOB_INDEX", "1")
    refresh_env()
    monkeypatch.setenv("HYPOTHESIS_HELM_JOB_TOTAL", "3")
    refresh_env()
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
    refresh_env()
    monkeypatch.setenv("CAPTURE_ARGS", str(capture))
    refresh_env()
    monkeypatch.setenv("FAKE_HELM_STATUS", str(exit_code))
    refresh_env()
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
    refresh_env()
    monkeypatch.setenv("HH_KUBESEC_SCORE_MINIMUM", "5")
    refresh_env()
    monkeypatch.setenv("HH_RUN_ID", "pipeline-123")
    refresh_env()
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
        assert scan_calls[0]["score_minimum"] == 5
        assert scan_calls[0]["run_id"] == "pipeline-123"
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
    assert command[command.index("--rerun") + 1] == "failed"
    assert "--disable-schema-caching" in command
    assert "--no-cache" in command
    assert ("--validate-schemas" in command) is (not security)
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


@pytest.mark.parametrize(
    ("comparison_status", "changed", "requested", "expected"),
    [
        ("resolved", False, "auto", "failed"),
        ("resolved", True, "auto", "all"),
        ("unavailable", False, "auto", "all"),
        ("resolved", False, "all", "all"),
    ],
)
def test_action_incremental_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, comparison_status: str, changed: bool, requested: str, expected: str
) -> None:
    """
    Use Git comparisons for incremental CI while respecting forced release runs.

    Args:
        tmp_path (Path): Local checkout and artifact destination.
        monkeypatch (pytest.MonkeyPatch): Replace the comparison and Helm process boundary.
        comparison_status (str): Available comparison or missing history.
        changed (bool): Whether this chart has modified files.
        requested (str): Explicit action rerun policy.
        expected (str): Effective policy passed to the shell integration.

    Returns:
        None: Only unchanged charts with usable history request cached success reuse.
    """
    monkeypatch.setenv("HH_CHART", str(tmp_path / "chart"))
    refresh_env()
    monkeypatch.setenv("HH_ARTIFACT_DIR", str(tmp_path / "results"))
    refresh_env()
    monkeypatch.setenv("HH_INCREMENTAL", "true")
    refresh_env()
    monkeypatch.setenv("HH_BASE_REF", "origin/release")
    refresh_env()
    monkeypatch.setenv("HYPOTHESIS_HELM_BASE_REF", "origin/main")
    refresh_env()
    monkeypatch.setenv("HH_RERUN", requested)
    refresh_env()

    def compare(root: Path, base_ref: str | None, **kwargs: object) -> dict[str, object]:
        """
        Return a resolved file inventory or an unavailable comparison.

        Args:
            root (Path): Chart path whose Git history is inspected.
            base_ref (str | None): User-provided comparison override.
            **kwargs (object): Explicit provider environment passed by the shared policy.

        Returns:
            dict[str, object]: Comparison metadata in the normal Git resolver format.
        """
        assert root == tmp_path / "chart"
        assert base_ref == "origin/release"
        return {
            "status": comparison_status,
            "repository": str(tmp_path),
            "base_ref": base_ref,
            "changed_files": ["chart/values.yaml"] if changed else ["README.md"],
        }

    def execute(self: Processes, command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        """
        Assert the selected policy without invoking external tools.

        Args:
            self (Processes): Replaced subprocess owner.
            command (list[str]): Action shell command.
            **kwargs (object): Environment and redirected output.

        Returns:
            subprocess.CompletedProcess[str]: Successful child result.
        """
        assert mapping(kwargs["env"])["HH_RERUN"] == expected
        assert "HYPOTHESIS_HELM_BASE_REF" not in mapping(kwargs["env"])
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("hypothesis_helm.integrations.incremental.comparison", compare)
    monkeypatch.setattr(Processes, "run", execute)
    assert github_action.main() == 0
    report = json.loads((tmp_path / "results/git-comparison.json").read_text())
    assert report["base_ref"] == "origin/release"


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

    root = PROJECT_ROOT
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
    policy = scanner.with_name("hypothesis-helm-ci-policy")
    policy.write_text(
        dedent(f"""
        #!{sys.executable}
        from hypothesis_helm.integrations.incremental import main
        raise SystemExit(main())
        """).lstrip()
    )
    policy.chmod(0o755)
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
        "KUBESEC_SCORE_MINIMUM": "5",
        "HH_KUBESEC_SCORE_MINIMUM": "5",
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
        "HH_CACHE_DIR": "cache with spaces",
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
    assert ("--validate-schemas" in command) is (not security)
    assert "--schema-offline" in command
    assert command[command.index("--shard") + 1] == "2/3"
    assert command[command.index("--run-id") + 1] == ("123-1.35.0" if provider == "gitlab" else "workflow-123-chart")
    assert command[command.index("--rerun") + 1] == "all"  # Missing Git history must never suppress tests.
    assert command[command.index("--cache-dir") + 1] == "cache with spaces"
    assert len(calls) == (2 if security else 1)
    if security:
        assert "--pre-sharded" in calls[1] and "--validate-rest" in calls[1]
        assert calls[1][calls[1].index("--score-minimum") + 1] == "5"
        assert calls[1][calls[1].index("--run-id") + 1] == command[command.index("--run-id") + 1]
        assert "--schema-offline" in calls[1]
    assert not (tmp_path / "unexpected").exists()


@pytest.mark.parametrize("provider", ["gitlab", "circleci", "github"])
@pytest.mark.parametrize("outcome", ["passed", "failed", "missing"])
def test_ci_security_aggregation(tmp_path: Path, provider: str, outcome: str) -> None:
    """
    Exercise the security aggregation branches of each published provider script.

    Args:
        tmp_path (Path): Downloaded reports and stubbed chart aggregator.
        provider (str): Published CI provider to exercise.
        outcome (str): Complete, rejected or incomplete security evidence.

    Returns:
        None: Security failures and missing idle shards fail the final CI gate.
    """
    from ruamel.yaml import YAML

    from hypothesis_helm.reporting.reports.security import publish
    from hypothesis_helm.schemas.contracts import sequence

    root = PROJECT_ROOT
    source = root / (".github/workflows/ci.yml" if provider == "github" else f"ci/{provider}.yml")
    document = mapping(YAML(typ="safe").load(source.read_text()))
    if provider == "gitlab":
        script = str(sequence(mapping(document["helm-report"])["script"])[0])
        incoming = tmp_path / ".cache/hypothesis-helm/runs/1.35.0"
        final = tmp_path / "docs/reports/final/1.35.0/kubesec"
    else:
        steps = [mapping(step) for step in sequence(mapping(mapping(document["jobs"])["aggregate"])["steps"])]
        final = tmp_path / "docs/reports/final/kubesec"
        if provider == "circleci":
            run = next(mapping(step["run"]) for step in steps if isinstance(step.get("run"), dict) and "Write" in str(step["run"]))
            script = str(run["command"]).replace("/tmp/hypothesis-helm-aggregation", str(tmp_path / "workspace"))
            incoming = tmp_path / "workspace/chart"
        else:
            script = next(str(step["run"]) for step in steps if str(step.get("name", "")).startswith("Write"))
            incoming = tmp_path / "downloaded"
    run_id = "123-1.35.0" if provider == "gitlab" else "workflow-123-chart"
    for index in range(1, 4):
        chart = incoming / str(index)
        if provider == "gitlab":
            chart = chart / "shards" / f"{index}-of-3"
        chart.mkdir(parents=True)
        (chart / "report.json").write_text("{}\n")
        (chart / "exit-code.txt").write_text("0\n")
        security = incoming / str(index) / "kubesec"
        if provider == "github":
            security = tmp_path / "downloaded-security" / str(index)
        if index == 3 and outcome == "missing":
            continue
        security.mkdir(parents=True)
        record = {"object": "Pod/demo", "valid": True, "score": 0 if outcome == "failed" else 5, "exit_code": 0, "signal": 0}
        (security / "details.jsonl").write_text("" if index == 3 else json.dumps(record) + "\n")
        publish(
            security,
            {
                "scanned": int(index != 3),
                "shard": f"{index}-of-3",
                "run_id": run_id,
                "schema_version": "1.35.0",
                "schema_identity": "snapshot",
            },
            5,
        )
    binary = tmp_path / "hypothesis-helm"
    binary.write_text("#!/bin/sh\ncat >/dev/null\nexit 0\n")
    binary.chmod(0o755)
    result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", script],
        cwd=tmp_path,
        env=dict(
            os.environ,
            PATH=os.pathsep.join((str(tmp_path), str(Path(sys.executable).parent), os.environ["PATH"])),
            KUBESEC_ENABLED="true",
            HH_KUBESEC="true",
            KUBESEC_SCORE_MINIMUM="5",
            HH_KUBESEC_SCORE_MINIMUM="5",
            HH_SCHEMA_VERSION="1.35.0",
            HH_RUN_ID=run_id,
            CI_PIPELINE_ID="123",
            K8S_VERSION="1.35.0",
            SHARD_TOTAL="3",
            CIRCLE_WORKFLOW_ID="workflow-123",
            HH_REPORT_GROUP="chart",
            HH_SHARDS="3",
        ),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == {"passed": 0, "failed": 1, "missing": 2}[outcome], result.stdout + result.stderr
    if outcome != "missing":
        assert json.loads((final / "summary.json").read_text())["status"] == outcome
        assert (final / "junit.xml").is_file()


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

    root = PROJECT_ROOT
    source = root / (".github/workflows/ci.yml" if provider == "github" else f"ci/{provider}.yml")
    document = mapping(YAML(typ="safe").load(source.read_text()))
    if provider == "gitlab":
        script = str(sequence(mapping(document["helm-report"])["script"])[0])
        artifact_root = tmp_path / ".cache/hypothesis-helm/runs/1.35.0"
        final = tmp_path / "docs/reports/final/1.35.0"
    else:
        job = mapping(mapping(document["jobs"])["aggregate"])
        steps = [mapping(step) for step in sequence(job["steps"])]
        artifact_root = tmp_path / ("workspace/chart" if provider == "circleci" else "downloaded")
        final = tmp_path / "docs/reports/final"
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

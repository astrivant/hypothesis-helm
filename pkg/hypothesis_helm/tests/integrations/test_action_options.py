"""
Exercise public Action inputs, literal Bash arguments and inline policy precedence.
"""

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from textwrap import dedent
from typing import TextIO

import pytest
from ruamel.yaml import YAML

from hypothesis_helm.cli import argument_parser
from hypothesis_helm.execution.runtime.processes import Processes
from hypothesis_helm.integrations import github_action
from hypothesis_helm.integrations.action_config import prepare_config
from hypothesis_helm.integrations.action_options import input_name, normalize_options, options
from hypothesis_helm.schemas.configuration.policy import ENVIRONMENT as INPUT_ENVIRONMENT
from hypothesis_helm.schemas.configuration.policy import inherited_policy, load_policy
from hypothesis_helm.schemas.contracts import mapping
from hypothesis_helm.tests import PROJECT_ROOT


def test_action_exposes_every_cli_option() -> None:
    """
    Require new CLI controls to be declared, wired and documented in the Action.

    Returns:
        None: Every canonical CLI option has a public input and an execution binding.
    """
    action = YAML(typ="safe").load((PROJECT_ROOT / "action.yml").read_text())
    step = next(step for step in action["runs"]["steps"] if step.get("id") == "test")
    for command, arguments in options().items():
        for name in arguments:
            assert name in action["inputs"], (command, name)
            if name == "schema-offline":
                # Preparation honors this input once; test workers then use the prepared cache offline.
                preparation = next(item for item in action["runs"]["steps"] if item.get("name") == "Prepare local Kubernetes schemas")
                assert f"${{{{ inputs.{name} }}}}" in preparation["env"].values()
            else:
                assert f"${{{{ inputs.{name} }}}}" in step["env"].values(), (command, name)
    assert action["inputs"]["max-examples"]["default"] == ""
    assert action["inputs"]["command"]["default"] == "test"


def sample_option(action: argparse.Action) -> str:
    """
    Choose a parser-valid representative for one input without enabling other options.

    Args:
        action (argparse.Action): CLI declaration under test.

    Returns:
        str: One literal public-input value.
    """
    name = input_name(action)
    samples = {
        "shard": "none",
        "jobs": "2",
        "ignore": "HH2006",
        "disable-codes": "HH2006,HH2003",
        "exhaustive-group": "$.a,$.b",
        "fail": "warning",
        "match": "name or other",
        "cache": "false",
    }
    if name in samples:
        return samples[name]
    if isinstance(action, argparse.BooleanOptionalAction) or action.nargs == 0:
        return "true"
    if action.choices:
        return str(next(iter(action.choices)))
    if action.type is int or action.type is float:
        return "2"
    if action.type and getattr(action.type, "__name__", "") == "parse_time_limit":
        return "3m"
    return "literal path with spaces"


@pytest.mark.parametrize(
    ("command", "name"),
    [(command, name) for command, arguments in options().items() for name in arguments if name != "export-minimal-values"],
)
def test_each_option_reaches_the_real_parser(tmp_path: Path, command: str, name: str) -> None:
    """
    Exercise each explicit shell expansion with the installed platform's Bash.

    Args:
        tmp_path (Path): Executable spy and captured argument vector.
        command (str): Selected CLI command.
        name (str): One public Action input.

    Returns:
        None: The actual CLI parser receives this option with its declared value and kind.
    """
    action = options()[command][name]
    value = sample_option(action)
    binary = tmp_path / "helm"
    binary.write_text(
        dedent(f"""
        #!{sys.executable}
        import json, sys
        print(json.dumps(sys.argv[1:]))
        """).lstrip()
    )
    binary.chmod(0o755)
    key = "HH_VALIDATE_SCHEMAS" if name == "schema-validation" else "HH_" + name.upper().replace("-", "_")
    environment = normalize_options({key: value}, command)
    result = subprocess.run(
        ["bash", str(PROJECT_ROOT / "pkg/hypothesis_helm/integrations/github_action.sh")],
        env={**os.environ, **environment, "PATH": f"{tmp_path}:{os.environ['PATH']}", "HH_COMMAND": command, "HH_SOURCE": "chart"},
        capture_output=True,
        text=True,
        check=True,
    )
    invocation = json.loads(result.stdout)
    assert invocation[:3] == ["hypothesis", command, "chart"]
    flag = "--disable-codes" if name == "ignore" else action.option_strings[0]
    assert flag in invocation, (command, name, invocation)
    parsed = argument_parser().parse_args(invocation[1:])
    assert hasattr(parsed, action.dest)


def test_repeated_groups_and_literals_are_not_shell_code(tmp_path: Path) -> None:
    """
    Keep repeated groups and shell-looking source/config values as individual arguments.

    Args:
        tmp_path (Path): Spy binary and marker that must never be created.

    Returns:
        None: No splitting, globbing, expansion or command substitution changes the inputs.
    """
    binary = tmp_path / "helm"
    binary.write_text(
        dedent(f"""
        #!{sys.executable}
        import json, sys
        print(json.dumps(sys.argv[1:]))
        """).lstrip()
    )
    binary.chmod(0o755)
    literal = f"$(touch {tmp_path / 'injected'}); [*] 'quoted'"
    settings = {
        "HH_EXHAUSTIVE_GROUP": "$.alpha,$.beta\n$.nested.first,$.nested.second\n",
        "HH_IGNORE": "HH2006\nHH2003",
        "HH_DISABLE_CODES": "HH2005",
        "HH_CONFIG": literal,
        "HH_MATCH": literal,
        "HH_STRICT": "false",
        "HH_BUILD_DEPENDENCIES": "false",
    }
    result = subprocess.run(
        ["bash", str(PROJECT_ROOT / "pkg/hypothesis_helm/integrations/github_action.sh")],
        env={
            **os.environ,
            **normalize_options(settings, "test"),
            "HH_COMMAND": "test",
            "HH_SOURCE": literal,
            "PATH": f"{tmp_path}:{os.environ['PATH']}",
        },
        capture_output=True,
        text=True,
        check=True,
    )
    invocation = json.loads(result.stdout)
    assert invocation.count(literal) == 3
    assert invocation.count("--exhaustive-group") == 2
    assert "--no-strict" in invocation and "--no-build-dependencies" in invocation
    assert "HH2006,HH2003,HH2005" in invocation
    assert not (tmp_path / "injected").exists()


def test_inline_policy_merge_preserves_references_and_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Resolve schema and selector paths before merging into a private temporary file.

    Args:
        tmp_path (Path): Workspace, nested config and private output directory.
        monkeypatch (pytest.MonkeyPatch): Set the repository workspace.

    Returns:
        None: CLI overrides win, lists replace, paths retain their origins and originals stay unchanged.
    """
    monkeypatch.chdir(tmp_path)
    settings = tmp_path / "settings"
    settings.mkdir()
    (settings / "widget.json").write_text('{"type":"object"}')
    (tmp_path / "other.json").write_text('{"type":"string"}')
    base = settings / "policy.yaml"
    original = dedent("""
        ignored: [HH2006]
        hypothesis:
          max_examples: 17
          character_sets: unicode
          control_characters:
            exclude: true
            allow: ["\\n"]
        compiler:
          max_call_depth: 32
        resource_schemas:
          example.org/v1/Widget: widget.json
        input_constraints:
          - charts:
              - sources: [./charts]
                names: [app]
            path: $
            hypothesis:
              max_examples: 3
        """)
    base.write_text(original)
    destination = tmp_path / "private/config.yaml"
    effective = prepare_config(
        str(base),
        dedent("""
        ignored: []
        hypothesis:
          character_sets: ascii
          control_characters:
            allow: []
        resource_schemas:
          example.org/v1/Other: ./other.json
        """),
        destination,
    )
    assert base.read_text() == original
    document = YAML(typ="safe").load(destination.read_text())
    assert document["ignored"] == []
    assert document["hypothesis"]["control_characters"] == {"exclude": True, "allow": []}
    assert document["input_constraints"][0]["charts"][0]["sources"] == [str(settings / "charts")]
    policy = load_policy(effective)
    assert mapping(policy["hypothesis"])["max_examples"] == 17
    assert policy["character_sets"] == "ascii"
    assert policy["resource_schemas"] == {"example.org/v1/Widget": {"type": "object"}, "example.org/v1/Other": {"type": "string"}}
    assert mapping(load_policy(effective, max_examples=9)["hypothesis"])["max_examples"] == 9
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600


@pytest.mark.parametrize("inline", ["[]", "typo: true", "hypothesis: {typo: true}", "ignored: []\nignored: []", "{}\n---\n{}"])
def test_invalid_inline_policy_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, inline: str) -> None:
    """
    Reject malformed, multiple or misspelled policy documents before chart execution.

    Args:
        tmp_path (Path): Empty workspace and output path.
        monkeypatch (pytest.MonkeyPatch): Avoid inheriting the repository config.
        inline (str): Invalid policy.

    Returns:
        None: The effective policy cannot silently discard invalid settings.
    """
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError):
        prepare_config("", inline, tmp_path / "effective.yaml")


@pytest.mark.parametrize(
    ("command", "settings"),
    [
        ("scan", {"HH_FILTER_TOPOLOGY": "2"}),
        ("audit", {"HH_MAX_EXAMPLES": "10"}),
        ("run", {"HH_FILTER_ADAPTIVE": "true"}),
        ("test", {"HH_PATHS": "yes"}),
    ],
)
def test_inapplicable_inputs_fail(command: str, settings: dict[str, str]) -> None:
    """
    Fail clearly when the requested command cannot honor an input.

    Args:
        command (str): CLI command selected by the caller.
        settings (dict[str, str]): Invalid or misplaced option.

    Returns:
        None: Unsupported values cannot silently change requested coverage.
    """
    with pytest.raises(ValueError, match="Action input"):
        normalize_options(settings, command)


@pytest.mark.parametrize("command", ["test", "scan", "audit", "generate", "run"])
def test_action_routes_commands_and_streams(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str) -> None:
    """
    Run the complete wrapper with public defaults and inspect its real shell invocation.

    Args:
        tmp_path (Path): Workspace and spy executable.
        monkeypatch (pytest.MonkeyPatch): Install Action input defaults and a local Helm spy.
        command (str): Selected Action operation.

    Returns:
        None: Configuration reaches all commands, and YAML/security output keeps its format.
    """
    monkeypatch.chdir(tmp_path)
    action = YAML(typ="safe").load((PROJECT_ROOT / "action.yml").read_text())
    step = next(step for step in action["runs"]["steps"] if step.get("id") == "test")
    for key, value in step["env"].items():
        if value.startswith("${{ inputs."):
            name = value.removeprefix("${{ inputs.").removesuffix(" }}")
            monkeypatch.setenv(key, str(action["inputs"][name]["default"]))
    monkeypatch.setenv("HH_COMMAND", command)
    monkeypatch.setenv("HH_SOURCE", "https://example.test/charts.git" if command == "scan" else "chart")
    monkeypatch.setenv("HH_CONFIG_INLINE", "hypothesis: {max_examples: 3}\n")
    monkeypatch.setenv("HH_OUTPUT_FORMAT", "yaml" if command in {"test", "scan", "run"} else "")
    monkeypatch.setenv("HH_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "outputs"))
    binary = tmp_path / "helm"
    binary.write_text(
        dedent(f"""
        #!{sys.executable}
        import json, sys
        from pathlib import Path
        Path('invocation.json').write_text(json.dumps(sys.argv[1:]))
        print('apiVersion: v1\\nkind: ConfigMap\\nmetadata: {{name: example}}')
        """).lstrip()
    )
    binary.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")
    assert github_action.main() == 0
    invocation = json.loads((tmp_path / "invocation.json").read_text())
    assert invocation[1] == command
    assert "--max-examples" not in invocation
    argument_parser().parse_args(invocation[1:])
    config = Path(invocation[invocation.index("--config") + 1])
    assert mapping(load_policy(config)["hypothesis"])["max_examples"] == 3
    capture = "manifests.yaml" if command in {"test", "scan", "run"} else "command-output.txt"
    assert (tmp_path / "artifacts" / capture).read_text().startswith("apiVersion: v1")
    assert not list((tmp_path / "artifacts").rglob("config.yaml"))


@pytest.mark.integration
def test_action_generates_and_executes_real_saved_suite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Verify inline settings survive generation and execution through the actual CLI and Helm.

    Args:
        tmp_path (Path): Tiny chart, launcher and retained artifacts.
        monkeypatch (pytest.MonkeyPatch): Select local executables without installing a plugin.

    Returns:
        None: Generation succeeds and the saved suite renders a valid ConfigMap.
    """
    helm = shutil.which("helm")
    if helm is None:
        pytest.skip("Helm is required")
    monkeypatch.chdir(tmp_path)
    chart = tmp_path / "chart"
    (chart / "templates").mkdir(parents=True)
    (chart / "Chart.yaml").write_text("apiVersion: v2\nname: action-example\nversion: 1.0.0\n")
    (chart / "values.yaml").write_text("message: hello\n")
    (chart / "values.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {"message": {"type": "string", "enum": ["hello", "world"], "description": "Greeting"}},
                "required": ["message"],
                "additionalProperties": False,
            }
        )
    )
    (chart / "templates/configmap.yaml").write_text(
        dedent("""
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: example
        data:
          message: {{ .Values.message | quote }}
        """).lstrip()
    )
    binary = tmp_path / "helm"
    binary.write_text(
        dedent(f"""
        #!{sys.executable}
        import os, sys
        if len(sys.argv) > 1 and sys.argv[1] == "hypothesis":
            from hypothesis_helm.cli import main
            raise SystemExit(main(sys.argv[2:]))
        os.execv({helm!r}, [{helm!r}, *sys.argv[1:]])
        """).lstrip()
    )
    binary.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:{Path(sys.executable).parent}:{os.environ['PATH']}")
    monkeypatch.setenv("HH_SOURCE", str(chart))
    monkeypatch.setenv("HH_COMMAND", "generate")
    monkeypatch.setenv("HH_CONFIG_INLINE", "hypothesis: {max_examples: 1, phases: [generate], renderer_policy: native}\n")
    monkeypatch.setenv("HH_ARTIFACT_DIR", str(tmp_path / "generated"))
    monkeypatch.setenv("HH_SHARD", "none")
    assert github_action.main() == 0
    suite = tmp_path / "generated/generated-tests"
    assert list(suite.glob("test*.py"))
    monkeypatch.setenv("HH_COMMAND", "run")
    monkeypatch.setenv("HH_JOBS", "1")
    monkeypatch.setenv("HH_SOURCE", str(suite))
    monkeypatch.setenv("HH_ARTIFACT_DIR", str(tmp_path / "executed"))
    monkeypatch.setenv("HH_CACHE", "false")
    assert github_action.main() == 0
    documents = [json.loads(line) for line in (tmp_path / "executed/manifests.jsonl").read_text().splitlines()]
    assert documents and all(document["kind"] == "ConfigMap" for document in documents)


@pytest.mark.parametrize("interrupted", [False, True])
def test_yaml_security_routing_and_interruption(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, interrupted: bool) -> None:
    """
    Convert YAML for the security dispatcher and avoid downstream work after cancellation.

    Args:
        tmp_path (Path): Action artifacts and outputs.
        monkeypatch (pytest.MonkeyPatch): Replace owned execution and the security boundary.
        interrupted (bool): Interrupt instead of returning a completed manifest stream.

    Returns:
        None: Cancellation retains status 130; otherwise security consumes valid JSON Lines.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HH_OUTPUT_FORMAT", "yaml")
    monkeypatch.setenv("HH_KUBESEC", "true")
    (tmp_path / "widget.json").write_text('{"type":"object"}')
    monkeypatch.setenv("HH_CONFIG_INLINE", "strict: true\nresource_schemas:\n  example.org/v1/Widget: widget.json\n")
    monkeypatch.setenv("HH_ARTIFACT_DIR", str(tmp_path / "results"))
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "outputs"))
    previous_policy = os.environ.get(INPUT_ENVIRONMENT)

    def execute(self: Processes, command: list[str], *, stdout: TextIO, **kwargs: object) -> subprocess.CompletedProcess[str]:
        """
        Write a completed stream or interrupt the owned command.

        Args:
            self (Processes): Replaced process owner.
            command (list[str]): Explicit shell invocation.
            stdout (TextIO): Manifest output file.
            **kwargs (object): Process environment and working directory.

        Returns:
            subprocess.CompletedProcess[str]: Successful render status.
        """
        if interrupted:
            raise KeyboardInterrupt
        stdout.write("---\nkind: ConfigMap\nmetadata: {name: first}\n---\nkind: Secret\nmetadata: {name: second}\n")
        return subprocess.CompletedProcess(command, 0)

    calls: list[Path] = []

    def security(manifests: Path, *args: object, **kwargs: object) -> int:
        """
        Verify both resources reach the scanner without changing the public stream.

        Args:
            manifests (Path): Converted JSON Lines stream.
            *args (object): Remaining security inputs.
            **kwargs (object): Scanner policy.

        Returns:
            int: Simulated security failure.
        """
        calls.append(manifests)
        assert inherited_policy()["strict"] is True
        assert inherited_policy()["resource_schemas"] == {"example.org/v1/Widget": {"type": "object"}}
        assert [json.loads(line)["kind"] for line in manifests.read_text().splitlines()] == ["ConfigMap", "Secret"]
        return 1

    monkeypatch.setattr(Processes, "run", execute)
    monkeypatch.setattr(github_action, "prepare", lambda *args, **kwargs: "{}")
    monkeypatch.setattr(github_action, "scan", security)
    assert github_action.main() == (130 if interrupted else 1)
    assert len(calls) == (0 if interrupted else 1)
    assert "manifests.yaml" in (tmp_path / "outputs").read_text()
    assert os.environ.get(INPUT_ENVIRONMENT) == previous_policy


def test_optional_switch_defaults() -> None:
    """
    Match bare CLI switches while allowing explicit false and empty overrides.

    Returns:
        None: Severity and color toggles resolve to their CLI constant values.
    """
    enabled = normalize_options({"HH_FAIL": "true", "HH_LOG_COLOR": "true", "HH_STRICT": "false"}, "test")
    assert enabled["HH_FAIL"] == "info"
    assert enabled["HH_LOG_COLOR"] == "always"
    assert enabled["HH_NO_STRICT"] == "1" and enabled["HH_STRICT"] == ""
    disabled = normalize_options({"HH_FAIL": "false", "HH_LOG_COLOR": "false"}, "test")
    assert disabled["HH_FAIL"] == ""
    assert disabled["HH_LOG_COLOR"] == "never"

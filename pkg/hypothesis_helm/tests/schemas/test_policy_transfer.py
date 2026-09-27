"""Keep large CRD policies intact without oversized subprocess environment strings."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from hypothesis_helm.schemas.configuration.policy import ENVIRONMENT, FILE_ENVIRONMENT, inherited_policy
from hypothesis_helm.schemas.contracts import mapping


def test_large_policy_survives_worker_exec(tmp_path: Path) -> None:
    """
    Transfer a policy larger than Linux's per-string limit through an absolute file path.

    Args:
        tmp_path (Path): Command-owned snapshot directory.

    Returns:
        None: A fresh process reads the complete schema and preserves validation.
    """
    policy = {"resource_schemas": {"example/v1/Test": {"type": "integer", "minimum": 1, "description": "x" * 900_000}}}
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(policy))
    assert inherited_policy({FILE_ENVIRONMENT: str(path)}) == policy
    code = (
        "from hypothesis_helm.schemas.configuration.policy import inherited_policy; "
        "from jsonschema import Draft7Validator; "
        "s=inherited_policy()['resource_schemas']['example/v1/Test']; "
        "assert len(s['description']) == 900000; "
        "assert Draft7Validator(s).is_valid(1); assert not Draft7Validator(s).is_valid(0)"
    )
    from hypothesis_helm.environment import env

    environment = {key: value for key, value in env.items() if key not in {ENVIRONMENT, FILE_ENVIRONMENT}}
    environment[FILE_ENVIRONMENT] = str(path)
    subprocess.run([sys.executable, "-c", code], env=environment, check=True, timeout=30)
    # Cache fingerprints and saved evidence use content, not temporary path identities.
    other = tmp_path / "other.json"
    other.write_bytes(path.read_bytes())
    assert inherited_policy({FILE_ENVIRONMENT: str(other)}) == inherited_policy({ENVIRONMENT: json.dumps(policy)})
    with pytest.raises(FileNotFoundError):
        inherited_policy({FILE_ENVIRONMENT: str(tmp_path / "missing")})


def test_cli_owns_large_policy_until_workers_finish(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Check actual CLI transport, subprocess execution and cleanup on a failing command.

    Args:
        tmp_path (Path): Chart and large CRD policy.
        monkeypatch (pytest.MonkeyPatch): Inspect the policy at the audit execution boundary.

    Returns:
        None: Policy stays available during execution and is cleaned up after failure.
    """
    from hypothesis_helm import cli
    from hypothesis_helm.environment import env

    (tmp_path / "Chart.yaml").write_text("apiVersion: v2\nname: demo\nversion: 0.1.0\n")
    (tmp_path / "values.yaml").write_text("enabled: true\n")
    schema = tmp_path / "schema.json"
    schema.write_text(json.dumps({"type": "object", "description": "x" * 900_000}))
    config = tmp_path / "config.yaml"
    config.write_text(f"resource_schemas:\n  example/v1/Test: {schema}\n")
    observed: list[Path] = []

    def inspect(*args: object) -> dict[str, object]:
        """
        Inspect child-visible policy and simulate an execution failure.

        Args:
            *args (object): Chart arguments supplied by the CLI.

        Returns:
            dict[str, object]: Never returned; the test intentionally raises.
        """
        assert ENVIRONMENT not in env
        observed.append(Path(env[FILE_ENVIRONMENT]))
        assert len(str(mapping(mapping(inherited_policy()["resource_schemas"])["example/v1/Test"])["description"])) == 900_000
        subprocess.run(["git", "--version"], check=True, capture_output=True, timeout=10)
        raise RuntimeError("intentional audit failure")

    monkeypatch.setattr(cli, "audit", inspect)
    previous = env.get(FILE_ENVIRONMENT)
    assert cli.main(["audit", str(tmp_path), "--config", str(config)]) == 2
    assert observed and not observed[0].exists()
    assert env.get(FILE_ENVIRONMENT) == previous

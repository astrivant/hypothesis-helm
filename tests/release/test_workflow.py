"""
Reject successful-looking tag runs that omit their public release outputs.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from hypothesis_helm.schemas.contracts import mapping, sequence
from hypothesis_helm.tests.integrations.test_workflows import all_jobs

ROOT = Path(__file__).resolve().parents[2]


def test_release_has_independent_terminal_verification() -> None:
    """
    Audit tag outputs even when a publication ancestor fails or skips.

    Returns:
        None: Source verification alone cannot satisfy the release contract.
    """
    jobs = all_jobs()
    gate = jobs["release-verification"]
    assert "always()" in str(gate["if"])
    assert "github.event_name == 'push'" in str(gate["if"])
    assert "refs/tags/v" in str(gate["if"])
    assert set(sequence(gate["needs"])) == {"verification", "deploy-stage"}
    assert "continue-on-error" not in gate
    steps = [mapping(step) for step in sequence(gate["steps"])]
    assert all("continue-on-error" not in step for step in steps)
    assert any("verify-published.sh" in str(step.get("run", "")) for step in steps)
    publisher = jobs["github-release"]
    assert publisher["needs"] == "publish"
    assert "!cancelled()" in str(publisher["if"])
    assert "needs.publish.result == 'success'" in str(publisher["if"])
    assert "needs.verification.result == 'success'" in str(jobs["deploy-stage"]["if"])
    assert jobs["deploy-stage"]["permissions"] == {"contents": "write"}
    assert publisher["permissions"] == {"contents": "write"}
    assert "permissions" not in jobs["publish"]
    assert "secrets.COSIGN_PRIVATE_KEY" not in str(gate)
    downloads = []
    for name in ("publish", "github-release"):
        candidates = [mapping(step) for step in sequence(jobs[name]["steps"])]
        step = next(step for step in candidates if str(step.get("uses", "")).startswith("actions/download-artifact@"))
        downloads.append(mapping(step["with"])["name"])
    assert downloads[0] == downloads[1]
    assert "--ignore=tests/release" in str(jobs["python-tests"])
    assert "pytest tests/release" in str(jobs["release-tools"])


@pytest.mark.parametrize("result", ["success", "failure", "skipped", "cancelled"])
@pytest.mark.parametrize("dependency", ["verification", "deploy-stage"])
def test_terminal_gate_requires_every_dependency(result: str, dependency: str) -> None:
    """
    Execute the actual aggregate gate for successful and unsuccessful prerequisites.

    Args:
        result (str): GitHub job outcome to exercise.
        dependency (str): Source or publication prerequisite.

    Returns:
        None: Only successful source verification and publication are accepted.
    """
    gate = all_jobs()["release-verification"]
    step = mapping(sequence(gate["steps"])[0])
    outcomes = {name: {"result": "success"} for name in ("verification", "deploy-stage")}
    outcomes[dependency]["result"] = result
    environment = {**os.environ, "RESULTS": json.dumps(outcomes)}
    completed = subprocess.run(["bash", "-e", "-c", str(step["run"])], env=environment, capture_output=True, check=False)
    assert (completed.returncode == 0) == (result == "success")


@pytest.mark.parametrize("state", ["missing", "draft", "auth-error"])
def test_verifier_rejects_unpublished_release(tmp_path: Path, state: str) -> None:
    """
    Exercise the shell verifier against missing, private-draft and inaccessible outputs.

    Args:
        tmp_path (Path): Isolated fake host-command directory.
        state (str): Host outcome for the release query.

    Returns:
        None: No unverified output can be reported as a successful release.
    """
    host = tmp_path / "gh"
    host.write_text("#!/bin/sh\n" + ("echo true\n" if state == "draft" else "exit 1\n"))
    host.chmod(0o700)
    environment = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "GITHUB_REPOSITORY": "example/project",
        "RELEASE_TAG": "v1.2.3",
        "SOURCE_SHA": "a" * 40,
        "COSIGN_PUBLIC_KEY_SHA256": "b" * 64,
    }
    result = subprocess.run(["bash", "scripts/release/verify-published.sh"], cwd=ROOT, env=environment, capture_output=True, check=False)
    assert result.returncode != 0


@pytest.mark.parametrize("arguments", [[], ["--repo"], ["--repo", "invalid"], ["--unknown"]])
def test_setup_rejects_invalid_inputs_without_credentials(arguments: list[str]) -> None:
    """
    Refuse incomplete setup requests before contacting GitHub or creating any keys.

    Args:
        arguments (list[str]): Invalid explicit setup arguments.

    Returns:
        None: The helper exits with its usage diagnostic.
    """
    result = subprocess.run(["bash", "scripts/release/setup-signing.sh", *arguments], cwd=ROOT, capture_output=True, check=False)
    assert result.returncode == 2
    assert b"Usage:" in result.stderr


@pytest.mark.parametrize("missing", [None, "SIGNING_KEY_CONFIGURED", "SIGNING_PASSWORD_CONFIGURED", "SIGNING_FINGERPRINT_CONFIGURED"])
def test_signing_preflight_precedes_registry_mutation(missing: str | None) -> None:
    """
    Refuse partial signing setup before another destination can be published.

    Args:
        missing (str | None): One absent configuration entry or a complete setup.

    Returns:
        None: Only complete signing configuration passes the first publication step.
    """
    step = mapping(sequence(all_jobs()["publish"]["steps"])[0])
    environment = {**os.environ, **dict.fromkeys(mapping(step["env"]), "true")}
    if missing is not None:
        environment[missing] = "false"
    result = subprocess.run(["bash", "-e", "-c", str(step["run"])], env=environment, capture_output=True, check=False)
    assert (result.returncode == 0) == (missing is None)

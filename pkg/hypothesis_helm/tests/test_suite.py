"""
Verify the Helm-facing generated-suite workflow and failure propagation.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from hypothesis_helm.charts.generate import generate_tests
from hypothesis_helm.cli import main
from hypothesis_helm.execution.processes import Processes
from hypothesis_helm.execution.suite import run_suite


@pytest.mark.integration
@pytest.mark.skipif(not shutil.which("helm"), reason="Helm is required")
def test_helm_workflow_generates_and_runs(tmp_path: Path, capfd: pytest.CaptureFixture[str]) -> None:
    """
    Run per-path properties through the same entry point used by Helm.

    Args:
        tmp_path (Path): Temporary directory receiving generated artifacts.
        capfd (pytest.CaptureFixture[str]): Captured Helm and child pytest console output.

    Returns:
        None: Generated tests pass and the report records the invocation seed.
    """
    assert (
        main(
            [
                "test",
                "examples/workload",
                "--paths",
                "--max-examples",
                "3",
                "--seed",
                "42",
                "--artifact-dir",
                str(tmp_path),
            ]
        )
        == 0
    )
    report = json.loads((tmp_path / "report.json").read_text())
    assert report["status"] == "passed"
    assert report["seed"] == 42
    assert (tmp_path / "test_chart_values.py").is_file()
    assert 'tests="4"' in (tmp_path / "junit.xml").read_text()
    output = capfd.readouterr()
    assert "[INFO] Coalescing path $.replicas" in output.err
    assert "[INFO] Generating test for path $.image.tag (schema)" in output.err
    for path in ("$.replicas", "$.image", "$.image.repository", "$.image.tag"):
        assert output.out.count(f"[INFO] Testing path {path}\n") == 1


@pytest.mark.integration
@pytest.mark.skipif(not shutil.which("helm"), reason="Helm is required")
def test_helm_workflow_returns_chart_failure(tmp_path: Path) -> None:
    """
    Preserve a failing generated property's exit status through the Helm CLI.

    Args:
        tmp_path (Path): Temporary directory receiving failure artifacts.

    Returns:
        None: The broken replica lever fails and its counterexample reaches JUnit.
    """
    assert main(["test", "examples/broken", "--max-examples", "5", "--artifact-dir", str(tmp_path)]) == 1
    assert "replicas=0" in (tmp_path / "junit.xml").read_text()
    assert json.loads((tmp_path / "report.json").read_text())["exit_code"] == 1


def test_saved_suite_isolated_from_parent_pytest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Collect a saved suite without adopting unrelated pytest flags or plugins.

    Args:
        tmp_path (Path): Temporary directory containing the saved suite.
        monkeypatch (pytest.MonkeyPatch): Fixture restoring caller environment settings.

    Returns:
        None: Selection works and an empty selection remains a nonzero result.
    """
    generate_tests("examples/workload", tmp_path, max_examples=2)
    monkeypatch.setenv("PYTEST_ADDOPTS", "--invalid-parent-option")
    monkeypatch.setenv("PYTEST_PLUGINS", "nonexistent_parent_plugin")
    assert main(["run", str(tmp_path), "--collect-only", "--match", "replicas"]) == 0
    assert main(["run", str(tmp_path), "--collect-only", "--match", "nonexistent_path"]) == 5


def test_render_flags_are_embedded(tmp_path: Path) -> None:
    """
    Preserve Helm rendering flags when generating tests through the CLI.

    Args:
        tmp_path (Path): Temporary directory receiving generated Python tests.

    Returns:
        None: Generated options contain the selected rendering environment.
    """
    assert (
        main(
            [
                "test",
                "examples/workload",
                "--paths",
                "--collect-only",
                "--timeout",
                "7",
                "--release",
                "example",
                "--namespace",
                "testing",
                "--kube-version",
                "1.31.0",
                "--helm",
                "/custom/helm",
                "--allow-empty",
                "--artifact-dir",
                str(tmp_path),
            ]
        )
        == 0
    )
    source = (tmp_path / "test_chart_values.py").read_text()
    for expected in (
        "'timeout': 7.0",
        "'helm': '/custom/helm'",
        "'namespace': 'testing'",
        "'release': 'example'",
        "'kube_version': '1.31.0'",
        "'allow_empty': True",
    ):
        assert expected in source


def test_runner_uses_own_interpreter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Use the plugin interpreter rather than a pytest executable on the caller's PATH.

    Args:
        tmp_path (Path): Temporary directory containing the generated module.
        monkeypatch (pytest.MonkeyPatch): Fixture restoring the subprocess boundary.

    Returns:
        None: The subprocess uses this interpreter and preserves collection failures.
    """
    (tmp_path / "test_chart_values.py").write_text("# saved suite\n")
    calls: list[list[str]] = []

    def execute(self: Processes, command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        """
        Record the subprocess command and emulate a collection failure.

        Args:
            self (Processes): Process owner replaced by this test.
            command (list[str]): Pytest invocation assembled by the runner.
            **kwargs (object): Subprocess execution options.

        Returns:
            subprocess.CompletedProcess[str]: Failed pytest process result.
        """
        calls.append(command)
        return subprocess.CompletedProcess(command, 2)

    monkeypatch.setattr(Processes, "run", execute)
    assert run_suite(tmp_path, jobs=1) == 2
    assert calls[0][0] == str(Path(sys.executable).with_name("pytest"))


def test_missing_suite_is_an_error(tmp_path: Path) -> None:
    """
    Reject a nonexistent saved suite before invoking pytest.

    Args:
        tmp_path (Path): Directory with no generated Python module.

    Returns:
        None: The Helm command reports a setup error.
    """
    assert main(["run", str(tmp_path)]) == 2


@pytest.mark.integration
@pytest.mark.skipif(not shutil.which("helm"), reason="Helm is required")
@pytest.mark.parametrize("mode", ["paths", "whole-chart", "exhaustive", "permutations"])
def test_json_manifest_stream(tmp_path: Path, capfd: pytest.CaptureFixture[str], mode: str) -> None:
    """
    Keep rendered resources on stdout and all test diagnostics on stderr.

    Args:
        tmp_path (Path): Directory receiving generated suite artifacts.
        capfd (pytest.CaptureFixture[str]): Captured process and child output.
        mode (str): Rendering mode exercised through the Helm entry point.

    Returns:
        None: Every output line is a resource and saved suites can stream too.
    """
    arguments = [
        "test",
        "examples/workload",
        "-o",
        "json",
        "--max-examples",
        "2",
        "--artifact-dir",
        str(tmp_path),
    ]
    if mode == "exhaustive":
        chart = tmp_path / "finite"
        shutil.copytree("examples/configmap", chart)
        schema_path = chart / "values.schema.json"
        schema = json.loads(schema_path.read_text())
        schema["properties"]["message"]["enum"] = ["hello", "world"]
        schema_path.write_text(json.dumps(schema))
        arguments[1] = str(chart)
        arguments.append("--exhaustive")
    elif mode == "whole-chart":
        arguments.append("--whole-chart")
    elif mode == "permutations":
        arguments.extend(["--permutations", "2"])
    else:
        arguments.append("--paths")
    assert main(arguments) == 0
    output = capfd.readouterr()
    resources = [json.loads(line) for line in output.out.splitlines()]
    assert resources
    assert all("apiVersion" in item and "kind" in item for item in resources)
    if mode == "permutations":
        assert "Permutation progress:" in output.err
        assert "0 remaining" in output.err
    if mode == "paths":
        assert "Testing path $.replicas" in output.err
        assert "passed" in output.err
        assert main(["run", str(tmp_path), "--output", "json", "--match", "replicas"]) == 0
        replay = capfd.readouterr()
        assert replay.out
        assert all(json.loads(line)["kind"] for line in replay.out.splitlines())
        assert main(["run", str(tmp_path), "-o", "json", "--collect-only"]) == 0
        assert capfd.readouterr().out == ""
        assert not (tmp_path / "concurrency.json").exists()
        assert json.loads((tmp_path / "report.json").read_text())["concurrency"] is None


def test_parallel_workers_and_large_manifest_stream(tmp_path: Path, capfd: pytest.CaptureFixture[str]) -> None:
    """
    Require concurrent workers and verify large manifest lines remain intact.

    Args:
        tmp_path (Path): Directory containing a suite with a cross-process barrier.
        capfd (pytest.CaptureFixture[str]): Captured manifest stream and diagnostics.

    Returns:
        None: Both workers overlap and every large JSON resource is preserved.
    """
    (tmp_path / "test_chart_values.py").write_text(
        """
import time
from pathlib import Path
import pytest
from hypothesis_helm.reporting.output import emit_manifest

@pytest.mark.parametrize("index", [0, 1])
def test_concurrent(index):
    Path(f"ready-{index}").touch()
    deadline = time.monotonic() + 15
    while not Path(f"ready-{1-index}").exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert Path(f"ready-{1-index}").exists(), "workers did not overlap"
    for iteration in range(4):
        emit_manifest({
            "apiVersion": "v1", "kind": "ConfigMap",
            "metadata": {"name": f"worker-{index}-{iteration}"},
            "data": {"payload": str(index) * 200000},
        })
"""
    )
    assert main(["run", str(tmp_path), "-j", "2", "-o", "json"]) == 0
    output = capfd.readouterr()
    resources = [json.loads(line) for line in output.out.splitlines()]
    assert len(resources) == 8
    assert len({item["metadata"]["name"] for item in resources}) == 8
    for resource in resources:
        index = resource["metadata"]["name"].split("-")[1]
        assert resource["data"]["payload"] == index * 200000
    assert json.loads((tmp_path / "report.json").read_text())["workers"] == 2
    assert 'tests="2"' in (tmp_path / "junit.xml").read_text()


@pytest.mark.parametrize("jobs", ["0", "-1"])
def test_invalid_worker_count(jobs: str) -> None:
    """
    Reject invalid worker counts before generating or executing a suite.

    Args:
        jobs (str): Invalid CLI concurrency value.

    Returns:
        None: Argument parsing rejects zero and negative worker counts.
    """
    with pytest.raises(SystemExit) as error:
        main(["test", "examples/workload", "--jobs", jobs])
    assert error.value.code == 2


@pytest.mark.parametrize("explicit_auto", [False, True])
def test_adaptive_dispatches_each_completion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, explicit_auto: bool) -> None:
    """
    Resize active concurrency without losing tests, failures, or merged reports.

    Args:
        tmp_path (Path): Directory receiving controller and JUnit reports.
        monkeypatch (pytest.MonkeyPatch): Fixture replacing pytest processes and CPU detection.
        explicit_auto (bool): Whether to request auto explicitly or use its default.

    Returns:
        None: Every selected test completes once and concurrency grows within its bound.
    """
    import os
    import threading
    import time

    (tmp_path / "test_chart_values.py").write_text("# simulated suite\n")
    lock = threading.Lock()
    active = 0
    peak = 0
    completed: list[str] = []
    nodes = [f"test_chart_values.py::test_{index}" for index in range(30)]

    def execute(self: Processes, command: list[str], *, env: dict[str, str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        """
        Emulate isolated pytest runs with overlapping work and one failing test.

        Args:
            self (Processes): Process owner replaced by this test.
            command (list[str]): Collection or single-property pytest command.
            env (dict[str, str]): Environment containing the collection destination.
            **kwargs (object): Remaining subprocess options.

        Returns:
            subprocess.CompletedProcess[str]: Simulated pytest result.
        """
        nonlocal active, peak
        if "--collect-only" in command:
            Path(env["HYPOTHESIS_HELM_COLLECT"]).write_text(json.dumps(nodes))
            return subprocess.CompletedProcess(command, 0, "", "")
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.06)
        name = command[-1].split("::")[-1]
        status = int(name == "test_7")
        Path(command[command.index("--junitxml") + 1]).write_text(
            f'<testsuites><testsuite tests="1" failures="{status}" errors="0" skipped="0">'
            f'<testcase name="{name}"/></testsuite></testsuites>'
        )
        with lock:
            active -= 1
            completed.append(name)
        return subprocess.CompletedProcess(command, status)

    monkeypatch.setattr(os, "process_cpu_count", lambda: 2)
    monkeypatch.setattr(Processes, "run", execute)
    arguments = ["run", str(tmp_path)]
    if explicit_auto:
        arguments += ["--jobs", "auto"]
    assert main(arguments) == 1
    assert len(completed) == len(set(completed)) == 30
    assert 2 < peak <= 8
    feedback = json.loads((tmp_path / "concurrency.json").read_text())
    assert feedback["mode"] == "auto"
    assert feedback["maximum"] == 8
    assert len(feedback["completions"]) == 30
    assert any(event["throughput"] > 0 for event in feedback["completions"])
    report = json.loads((tmp_path / "report.json").read_text())
    assert report["jobs"] == "auto"
    assert 'tests="30"' in (tmp_path / "junit.xml").read_text()
    assert 'failures="1"' in (tmp_path / "junit.xml").read_text()

"""
Verify persistent outcomes across serial, threaded, and CI runs.
"""

import json
from pathlib import Path

import pytest

from hypothesis_helm.execution.cache import fingerprint, read_outcomes
from hypothesis_helm.execution.environment import in_ci
from hypothesis_helm.execution.suite import run_suite


@pytest.mark.parametrize("value", ["false", "NO", "0", "off", "", " true ", "yes", "1"])
def test_ci_boolean(value: str) -> None:
    """
    Explicit CI false values override provider indicators.

    Args:
        value (str): CI environment value.

    Returns:
        None: Cache behavior matches the requested policy.
    """
    assert in_ci({"CI": value, "GITHUB_ACTIONS": "true"}) == (value.strip().lower() in {"true", "yes", "1"})


@pytest.mark.parametrize("jobs", [1, 2])
def test_cached_retry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, jobs: int) -> None:
    """
    Retries retain failed paths and CI defaults execute every path.

    Args:
        tmp_path (Path): Isolated suite and cache directory.
        monkeypatch (pytest.MonkeyPatch): Environment override fixture.
        jobs (int): Worker count to exercise.

    Returns:
        None: Cache behavior matches the requested policy.
    """
    monkeypatch.setenv("CI", "false")
    module = tmp_path / "test_chart_values.py"
    module.write_text(
        "from pathlib import Path\n"
        "def test_pass():\n"
        "    with Path('calls').open('a') as stream: stream.write('pass\\n')\n"
        "def test_fail():\n"
        "    with Path('calls').open('a') as stream: stream.write('fail\\n')\n"
        "    assert Path('fixed').exists()\n"
    )
    assert run_suite(tmp_path, jobs=jobs) == 1
    assert run_suite(tmp_path, jobs=jobs) == 1
    assert (tmp_path / "calls").read_text().splitlines().count("pass") == 1
    (tmp_path / "fixed").touch()
    assert run_suite(tmp_path, jobs=jobs) == 0
    calls = (tmp_path / "calls").read_text()
    assert run_suite(tmp_path, jobs=jobs) == 0
    assert (tmp_path / "calls").read_text() == calls
    monkeypatch.setenv("CI", "yes")
    assert run_suite(tmp_path, jobs=jobs) == 0
    assert (tmp_path / "calls").read_text().splitlines().count("pass") == 2
    assert run_suite(tmp_path, jobs=jobs, rerun="failed") == 0
    assert (tmp_path / "calls").read_text().splitlines().count("pass") == 2
    monkeypatch.setenv("CI", "no")
    assert run_suite(tmp_path, jobs=jobs, cache=False) == 0
    assert run_suite(tmp_path, jobs=jobs, rerun="all") == 0
    assert (tmp_path / "calls").read_text().splitlines().count("pass") == 4


def test_cache_invalidation(tmp_path: Path) -> None:
    """
    Chart changes and malformed data cannot reuse stale successful results.

    Args:
        tmp_path (Path): Isolated suite and cache directory.

    Returns:
        None: Cache behavior matches the requested policy.
    """
    suite = tmp_path / "suite"
    chart = tmp_path / "chart"
    suite.mkdir()
    chart.mkdir()
    source = chart / "template.yaml"
    source.write_text("before")
    (suite / "chart-source.json").write_text(json.dumps({"chart": "../chart"}))
    before = fingerprint(suite, 0, None, "None")
    source.write_text("after")
    assert fingerprint(suite, 0, None, "None") != before
    assert fingerprint(suite, 1, None, "None") != fingerprint(suite, 0, None, "None")
    source.write_text('{"bad": []}')
    assert read_outcomes(source) == {}
    assert read_outcomes(tmp_path / "missing") == {}


def test_collect_only_and_teardown_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Collection preserves results and teardown failures remain eligible for retry.

    Args:
        tmp_path (Path): Isolated suite and cache directory.
        monkeypatch (pytest.MonkeyPatch): Environment override fixture.

    Returns:
        None: Cache behavior matches the requested policy.
    """
    monkeypatch.setenv("CI", "false")
    (tmp_path / "test_chart_values.py").write_text(
        "import pytest\n"
        "@pytest.fixture\n"
        "def fixture():\n"
        "    yield\n"
        "    assert False\n"
        "def test_teardown(fixture): pass\n"
        "@pytest.mark.skip\n"
        "def test_skip(): pass\n"
    )
    assert run_suite(tmp_path, jobs=1) == 1
    cached = next((tmp_path / "cache").rglob("*.json"))
    before = cached.read_bytes()
    assert set(read_outcomes(cached).values()) == {"failed", "skipped"}
    assert run_suite(tmp_path, collect_only=True) == 0
    assert cached.read_bytes() == before
    assert run_suite(tmp_path, jobs=2) == 1
    assert set(read_outcomes(cached).values()) == {"failed", "skipped"}


def test_nested_implementation_invalidation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Invalidate cached successes when implementation in another subpackage changes.

    Args:
        tmp_path (Path): Temporary package and suite directories.
        monkeypatch (pytest.MonkeyPatch): Substitute the implementation package location.

    Returns:
        None: Nested runtime modules affect fingerprints while package tests do not.
    """
    from hypothesis_helm.execution import cache

    package = tmp_path / "package"
    implementation = package / "charts" / "runner.py"
    implementation.parent.mkdir(parents=True)
    implementation.write_text("before")
    suite = tmp_path / "suite"
    suite.mkdir()
    monkeypatch.setattr(cache, "__file__", str(package / "execution" / "cache.py"))
    before = fingerprint(suite, 0, None, "none")
    implementation.write_text("after")
    after = fingerprint(suite, 0, None, "none")
    assert after != before
    tests = package / "tests"
    tests.mkdir()
    (tests / "test_runner.py").write_text("test-only change")
    assert fingerprint(suite, 0, None, "none") == after


def test_seed_namespaces(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Isolate seeds while retaining multiple content fingerprints within each seed namespace.

    Args:
        tmp_path (Path): Suite and persistent cache directory.
        monkeypatch (pytest.MonkeyPatch): Select local rerun defaults.

    Returns:
        None: Execution and dry runs reuse only their seed's compatible entries.
    """
    from hypothesis_helm.execution.cache import seed_key
    from hypothesis_helm.execution.estimate import estimate_suite

    monkeypatch.setenv("CI", "false")
    module = tmp_path / "test_chart_values.py"
    module.write_text("def test_pass(): pass\n")
    assert seed_key(0) == "5feceb66ffc86f38d952786c6d696c79c2dbc239dd4e91b46729d73a27fb57e9"
    assert run_suite(tmp_path, jobs=1, seed=0) == 0
    first = next((tmp_path / "cache" / seed_key(0)).glob("*.json"))
    original = first.read_bytes()
    assert estimate_suite(tmp_path, seed=1)["scheduled_properties"] == 1
    assert not (tmp_path / "cache" / seed_key(1)).exists()
    assert run_suite(tmp_path, jobs=1, seed=1) == 0
    for seed in (0, 1):
        plan = estimate_suite(tmp_path, seed=seed)
        assert plan["scheduled_properties"] == 0
        assert Path(str(plan["result_cache"])).parent.name == seed_key(seed)
    module.write_text("def test_pass(): assert True\n")
    assert run_suite(tmp_path, jobs=1, seed=0) == 0
    assert len(list((tmp_path / "cache" / seed_key(0)).glob("*.json"))) == 2
    assert first.read_bytes() == original


def test_concurrent_cache_publication(tmp_path: Path) -> None:
    """
    Preserve all six independent worker updates to one shared cache key.

    Args:
        tmp_path (Path): Shared cache destination.

    Returns:
        None: Complete updates survive concurrent publication and later retry recovery.
    """
    import subprocess
    import sys

    from hypothesis_helm.execution.cache import merge_outcomes

    target = tmp_path / "shared.json"
    children = [
        subprocess.Popen(
            [
                sys.executable,
                "-c",
                "from pathlib import Path; import sys; "
                "from hypothesis_helm.execution.cache import merge_outcomes; "
                "merge_outcomes(Path(sys.argv[1]), {}, {sys.argv[2]: 'passed'})",
                str(target),
                f"node-{index}",
            ]
        )
        for index in range(6)
    ]
    try:
        for child in children:
            assert child.wait(timeout=30) == 0
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
            child.wait()
    assert read_outcomes(target) == {f"node-{index}": "passed" for index in range(6)}
    baseline = read_outcomes(target)
    merge_outcomes(target, baseline, {"conflict": "failed"})
    merge_outcomes(target, baseline, {"conflict": "passed"})
    assert read_outcomes(target)["conflict"] == "failed"
    merge_outcomes(target, read_outcomes(target), {"conflict": "passed"})
    assert read_outcomes(target)["conflict"] == "passed"
    assert not list(tmp_path.glob("*.tmp"))

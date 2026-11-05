"""
Verify persistent outcomes across serial, threaded, and CI runs.
"""

import json
from importlib.metadata import version
from pathlib import Path

import pytest

from hypothesis_helm.environment import refresh_env
from hypothesis_helm.execution.runtime.environment import in_ci
from hypothesis_helm.execution.state.cache import fingerprint, read_outcomes
from hypothesis_helm.execution.suite import run_suite


def test_random_renderer_source_invalidates_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Invalidate saved outcomes when only the optional native renderer changes.

    Args:
        tmp_path (Path): Empty suite used to isolate source identity.
        monkeypatch (pytest.MonkeyPatch): Supply different native build identities.

    Returns:
        None: Existing cached successes cannot hide changed Go execution semantics.
    """
    from hypothesis_helm.compiler.randomness import toolchain

    monkeypatch.setattr(toolchain, "identity", lambda: "source-one")
    before = fingerprint(tmp_path, 0, None, "none")
    monkeypatch.setattr(toolchain, "identity", lambda: "source-two")
    assert fingerprint(tmp_path, 0, None, "none") != before


def test_lua_implementation_invalidates_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Invalidate compiler-derived successes when the bundled kernel or Lupa version changes.

    Args:
        tmp_path (Path): Isolated implementation and suite paths.
        monkeypatch (pytest.MonkeyPatch): Point fingerprinting at the isolated package snapshot.

    Returns:
        None: Both native source and dependency identity participate in the cache key.
    """
    from hypothesis_helm.execution.state import cache

    package = tmp_path / "package"
    source = package / "execution" / "state" / "cache.py"
    source.parent.mkdir(parents=True)
    source.write_text("# unchanged Python implementation\n")
    script = package / "compiler" / "lua" / "bounds.lua"
    script.parent.mkdir(parents=True)
    script.write_text("return 1\n")
    monkeypatch.setattr(cache, "__file__", str(source))
    before = fingerprint(tmp_path, 0, None, "none")
    script.write_text("return 2\n")
    after_source = fingerprint(tmp_path, 0, None, "none")
    assert after_source != before
    monkeypatch.setattr(cache, "version", lambda name: "changed" if name == "lupa" else version(name))
    assert fingerprint(tmp_path, 0, None, "none") != after_source


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
    refresh_env()
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
    refresh_env()
    assert run_suite(tmp_path, jobs=jobs) == 0
    assert (tmp_path / "calls").read_text().splitlines().count("pass") == 2
    assert run_suite(tmp_path, jobs=jobs, rerun="failed") == 0
    assert (tmp_path / "calls").read_text().splitlines().count("pass") == 2
    monkeypatch.setenv("CI", "no")
    refresh_env()
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


def test_renderer_binary_invalidates_saved_successes(tmp_path: Path) -> None:
    """
    Prevent a renderer upgrade from reusing successes produced by another Helm binary.

    Args:
        tmp_path (Path): Generated suite, original chart and fake executable.

    Returns:
        None: Binary replacement and removal both change the suite fingerprint.
    """
    suite = tmp_path / "suite"
    chart = tmp_path / "chart"
    suite.mkdir()
    chart.mkdir()
    binary = tmp_path / "helm"
    binary.write_text("first renderer")
    binary.chmod(0o755)
    (suite / "chart-source.json").write_text(json.dumps({"chart": "../chart", "helm": str(binary)}))
    first = fingerprint(suite, 0, None, "None")
    binary.write_text("second renderer")
    second = fingerprint(suite, 0, None, "None")
    assert first != second
    binary.unlink()
    assert fingerprint(suite, 0, None, "None") not in {first, second}


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
    refresh_env()
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
    from hypothesis_helm.execution.state import cache

    package = tmp_path / "package"
    implementation = package / "charts" / "runner.py"
    implementation.parent.mkdir(parents=True)
    implementation.write_text("before")
    suite = tmp_path / "suite"
    suite.mkdir()
    monkeypatch.setattr(cache, "__file__", str(package / "execution" / "state" / "cache.py"))
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
    from hypothesis_helm.execution.planning.estimate import estimate_suite
    from hypothesis_helm.execution.state.cache import seed_key

    monkeypatch.setenv("CI", "false")
    refresh_env()
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

    from hypothesis_helm.execution.state.cache import merge_outcomes

    target = tmp_path / "shared.json"
    children = [
        subprocess.Popen(
            [
                sys.executable,
                "-c",
                "from pathlib import Path; import sys; "
                "from hypothesis_helm.execution.state.cache import merge_outcomes; "
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


def test_preparing_renderer_invalidates_native_fallback_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Retest automatic-mode cases when controlled execution becomes available after a build.

    Args:
        tmp_path (Path): Isolated working directory and suite.
        monkeypatch (pytest.MonkeyPatch): Keep the renderer identity fixed while publishing its executable.

    Returns:
        None: Cached native-mode success cannot replace newly available controlled testing.
    """
    from hypothesis_helm.compiler.randomness import toolchain

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(toolchain, "identity", lambda: "same-reviewed-sources")
    before = fingerprint(tmp_path, 0, None, "none")
    renderer = tmp_path / ".cache/random-renderer/same-reviewed-sources/renderer"
    renderer.parent.mkdir(parents=True)
    renderer.touch()
    assert fingerprint(tmp_path, 0, None, "none") != before

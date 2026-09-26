"""
Check framework-suite partitioning without depending on chart execution or CI environment variables.
"""

import subprocess
import sys
from pathlib import Path

import pytest


def test_suite_shards_cover_collection_once(tmp_path: Path) -> None:
    """
    Compare independent shard collections against the unpartitioned suite.

    Args:
        tmp_path (Path): Minimal suite with separately identified parameterized tests.

    Returns:
        None: Each test belongs to exactly one shard, regardless of local worker count.
    """
    path = tmp_path / "test_example.py"
    path.write_text('import pytest\n@pytest.mark.parametrize("value", range(32))\ndef test_value(value):\n    assert value >= 0\n')
    command = [sys.executable, "-m", "pytest", "-p", "hypothesis_helm.tests.sharding", "-q", str(path)]
    baseline = subprocess.run([*command, "--collect-only"], cwd=tmp_path, capture_output=True, text=True, check=True, timeout=30)
    expected = {line for line in baseline.stdout.splitlines() if "::test_value[" in line}
    assert len(expected) == 32
    observed: set[str] = set()
    for index in range(1, 5):
        shard = [*command, "--suite-shard", f"{index}/4"]
        result = subprocess.run([*shard, "--collect-only"], cwd=tmp_path, capture_output=True, text=True, check=True, timeout=30)
        selected = {line for line in result.stdout.splitlines() if "::test_value[" in line}
        assert selected and not observed.intersection(selected)
        observed.update(selected)
        # xdist collects independently in each child; the same partition must execute there.
        result = subprocess.run([*shard, "-n", "2"], cwd=tmp_path, capture_output=True, text=True, check=True, timeout=30)
        assert f"{len(selected)} passed" in result.stdout
    assert observed == expected


@pytest.mark.parametrize("coordinate", ["0/4", "5/4", "1/0", "one", "1/2/3"])
def test_invalid_suite_shard_fails(tmp_path: Path, coordinate: str) -> None:
    """
    Reject malformed shard coordinates instead of silently dropping tests.

    Args:
        tmp_path (Path): Minimal test suite.
        coordinate (str): Invalid partition argument.

    Returns:
        None: Invalid configuration reports pytest's usage-error status.
    """
    path = tmp_path / "test_example.py"
    path.write_text("def test_example():\n    pass\n")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "hypothesis_helm.tests.sharding", "--suite-shard", coordinate, str(path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 4
    assert "1 <= INDEX <= TOTAL" in result.stderr

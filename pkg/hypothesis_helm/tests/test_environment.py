"""
Verify shared CI detection and concurrency defaults across their caller policies.
"""

import pytest

from hypothesis_helm.execution.environment import CI_PROVIDERS, in_ci
from hypothesis_helm.execution.parallel import worker_limit


@pytest.mark.parametrize("marker", ["CI", *CI_PROVIDERS])
@pytest.mark.parametrize("value", ["", "0", " false ", "NO", " off ", "true", "1", " yes ", "https://ci.example"])
def test_ci_markers(marker: str, value: str) -> None:
    """
    Apply identical whitespace and boolean handling to every recognized marker.

    Args:
        marker (str): Generic CI flag or provider marker.
        value (str): Enabled or disabled marker value.

    Returns:
        None: Both policies agree when no explicit override conflicts with a provider.
    """
    expected = value.strip().lower() in {"true", "1", "yes", "https://ci.example"}
    assert in_ci({marker: value}) is expected
    assert in_ci({marker: value}, honor_override=False) is expected


def test_environment_is_read_at_call_time(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Keep explicit empty environments isolated and observe changes to the current process.

    Args:
        monkeypatch (pytest.MonkeyPatch): Change process markers between calls.

    Returns:
        None: No cached environment or truthiness fallback leaks into explicit mappings.
    """
    monkeypatch.setenv("CI", "true")
    assert in_ci()
    assert not in_ci({})
    monkeypatch.setenv("CI", "false")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert not in_ci()
    assert in_ci(honor_override=False)


@pytest.mark.parametrize("cpus, expected", [(None, 4), (1, 4), (8, 32)])
def test_automatic_worker_limit(cpus: int | None, expected: int, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Use available process CPUs for automatic ceilings while retaining explicit limits.

    Args:
        cpus (int | None): Available CPU count or unavailable platform result.
        expected (int): Expected automatic worker ceiling.
        monkeypatch (pytest.MonkeyPatch): Replace the process CPU probe.

    Returns:
        None: Fixed and automatic modes share a validated concurrency rule.
    """
    monkeypatch.setattr("hypothesis_helm.execution.parallel.os.process_cpu_count", lambda: cpus)
    assert worker_limit("auto") == expected
    assert worker_limit(3) == 3
    with pytest.raises(ValueError, match="jobs must be positive"):
        worker_limit(0)

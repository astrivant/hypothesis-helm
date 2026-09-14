"""
Check benchmark progress, CI output and partial completion accounting.
"""

import io

import pytest
from rich.console import Console

from hypothesis_helm.benchmarking.reporting import progress
from hypothesis_helm.benchmarking.reporting.progress import BenchmarkProgress
from hypothesis_helm.reporting.display import start_progress


@pytest.mark.parametrize(
    "marker", ["CI", "GITHUB_ACTIONS", "GITLAB_CI", "CIRCLECI", "TF_BUILD", "JENKINS_URL", "BUILD_BUILDID", "BUILDKITE"]
)
def test_ci_disables_even_forced_bars(marker: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """
    Suppress terminal bars in CI while retaining readable benchmark counts.

    Args:
        marker (str): CI platform marker.
        monkeypatch (pytest.MonkeyPatch): Set CI and simulate an allocated terminal.
        capsys (pytest.CaptureFixture[str]): Capture both output channels.

    Returns:
        None: CI never prints bars or escapes even when progress is forced.
    """
    monkeypatch.setenv("CI", "false")
    monkeypatch.setenv(marker, "true")
    monkeypatch.setattr(progress, "Console", lambda **kwargs: Console(stderr=True, force_terminal=True))
    with BenchmarkProgress("Matrix checks") as display:
        assert not display.interactive
        assert list(display.track([1, 2])) == [1, 2]
    tests, task = start_progress(2, 1, force=True)
    tests.update(task, advance=2, refresh=True)
    tests.stop()
    output = capsys.readouterr()
    assert not output.out
    assert "Matrix checks: complete; 2/2 complete, 0 remaining" in output.err
    assert "Tests" not in output.err
    assert "\x1b" not in output.err
    assert "━" not in output.err


def test_terminal_bar_tracks_expansion(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Include newly scheduled checks in the local bar without changing traversal.

    Args:
        monkeypatch (pytest.MonkeyPatch): Supply a local terminal and disable CI detection.

    Returns:
        None: The bar finishes at the expanded count and restores its live display.
    """
    stream = io.StringIO()
    monkeypatch.setattr(progress, "in_ci", lambda **kwargs: False)
    monkeypatch.setattr(progress, "Console", lambda **kwargs: Console(file=stream, force_terminal=True, width=120))
    items = [1, 2]
    visited = []
    with BenchmarkProgress("Expansion") as display:
        for item in display.track(items):
            visited.append(item)
            if item == 1:
                items.append(3)
    assert visited == [1, 2, 3]
    assert display.completed == display.total == 3
    assert not display.progress.live.is_started
    assert "3/3" in stream.getvalue()
    assert "\x1b" in stream.getvalue()


def test_interruption_preserves_partial_count(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """
    Count only completed work when a timeout interrupts a benchmark item.

    Args:
        monkeypatch (pytest.MonkeyPatch): Force plain CI output.
        capsys (pytest.CaptureFixture[str]): Capture the final partial status.

    Returns:
        None: Original interruptions propagate and remaining work stays visible.
    """
    monkeypatch.setenv("CI", "true")
    with pytest.raises(TimeoutError), BenchmarkProgress("Checks") as display:
        for item in display.track(range(3)):
            if item == 1:
                raise TimeoutError()
    assert "stopped; 1/3 complete, 2 remaining" in capsys.readouterr().err
    assert not display.progress.live.is_started


def test_redirected_updates_are_throttled(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """
    Emit periodic plain status lines without logging every individual render.

    Args:
        monkeypatch (pytest.MonkeyPatch): Advance a deterministic clock in CI.
        capsys (pytest.CaptureFixture[str]): Count emitted updates.

    Returns:
        None: Start, periodic and final updates contain measured remaining time.
    """
    clock = [0.0]
    monkeypatch.setenv("CI", "true")
    monkeypatch.setattr("hypothesis_helm.benchmarking.reporting.progress.time.monotonic", lambda: clock[0])
    with BenchmarkProgress("Renders") as display:
        for _ in display.track(range(25)):
            clock[0] += 1
    output = capsys.readouterr().err
    assert len(output.splitlines()) == 4
    assert "10/25 complete, 15 remaining; elapsed 10.0s; ETA 15.0s" in output
    assert "complete; 25/25" in output


def test_nested_progress_shares_terminal_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Keep nested studies on one display and release it after an inner failure.

    Args:
        monkeypatch (pytest.MonkeyPatch): Use a simulated local terminal.

    Returns:
        None: Inner cleanup leaves the outer display alive and resets ownership.
    """
    stream = io.StringIO()
    monkeypatch.setattr(progress, "in_ci", lambda **kwargs: False)
    monkeypatch.setattr(progress, "Console", lambda **kwargs: Console(file=stream, force_terminal=True))
    with BenchmarkProgress("Study") as outer:
        with pytest.raises(ValueError), BenchmarkProgress("Case") as inner:
            assert inner.progress is outer.progress
            raise ValueError("render failed")
        assert outer.progress.live.is_started
        assert progress.ACTIVE.get() is outer.progress
        assert list(outer.track([1])) == [1]
    assert progress.ACTIVE.get() is None
    assert not outer.progress.live.is_started

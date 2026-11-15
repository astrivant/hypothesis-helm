"""
Verify resource ownership, independent rankings and missing-data behavior.
"""

from __future__ import annotations

import json
import resource
import sys
import threading
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis_helm.compiler.backends.engine import prepare
from hypothesis_helm.compiler.backends.model import Limits, Node, Opcode, Plan, State, digest
from hypothesis_helm.compiler.backends.scheduler import Worker
from hypothesis_helm.environment import refresh_env
from hypothesis_helm_benchmarking.execution.device import DeviceInterval
from hypothesis_helm_benchmarking.execution.profiling import PROFILE_DIRECTORY, capture
from hypothesis_helm_benchmarking.execution.resources import METRICS, Resources, Snapshot, phase_for, snapshot
from hypothesis_helm_benchmarking.reporting.flamegraph import render_profiles
from hypothesis_helm_benchmarking.reporting.resources import rank


def profile(phases: dict[str, dict[str, float | None]], *, complete: bool = True) -> dict[str, object]:
    """
    Create explicitly synthetic metric receipts without running a workload.

    Args:
        phases (dict[str, dict[str, float | None]]): Per-phase metrics to exercise aggregation.
        complete (bool): Whether the recording hook remained installed.

    Returns:
        dict[str, object]: A synthetic resource capture in the public report format.
    """
    return {
        "capture_complete": complete,
        "resources": {
            "format": "hypothesis-helm-phase-resources-v1",
            "phases": [{"name": name, "values": dict.fromkeys(METRICS) | values} for name, values in phases.items()],
        },
    }


def test_independent_resource_rankings_do_not_sum_peaks_or_rank_unknowns() -> None:
    """
    Rank CPU independently of RAM, retaining missing GPU observations and complete ties.

    Returns:
        None: Counts sum, peaks take maxima, and unavailable measurements remain unranked.
    """
    captures = [
        profile({"Render": {"cpu_seconds": 9, "rss_peak_bytes": 10}, "Prune": {"cpu_seconds": 1, "rss_peak_bytes": 50}}),
        profile({"Render": {"cpu_seconds": 3, "rss_peak_bytes": 20}, "Prune": {"cpu_seconds": 1, "rss_peak_bytes": 40}}),
    ]
    cpu, memory = rank(captures, "cpu_seconds"), rank(captures, "rss_peak_bytes")
    assert [(row.phase, row.value) for row in cpu] == [("Render", 12), ("Prune", 2)]
    assert sum(row.share_percent or 0 for row in cpu) == pytest.approx(100)
    assert [(row.phase, row.value) for row in memory] == [("Prune", 50), ("Render", 20)]
    assert all(row.share_percent is None for row in memory)
    assert all(row.value is row.position is None for row in rank(captures, "gpu_seconds"))
    captures.append(profile({"Render": {"cpu_seconds": None}}))
    partial = next(row for row in rank(captures, "cpu_seconds") if row.phase == "Render")
    assert partial.value is partial.position is None
    assert (partial.observed, partial.available, partial.captures) == (12, 2, 3)
    assert all(row.share_percent is None for row in rank(captures, "cpu_seconds"))


@given(st.lists(st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False), min_size=1, max_size=12))
@settings(max_examples=20, deadline=None)
def test_rank_conserves_additive_counters_and_peak_bounds(values: list[float]) -> None:
    """
    Check aggregation identities over independently generated nonnegative observations.

    Args:
        values (list[float]): Synthetic observed counter deltas or memory peaks.

    Returns:
        None: Sum and maximum match independent Python identities without input mutation.
    """
    captures = [profile({"phase": {"cpu_seconds": value, "rss_peak_bytes": value}}) for value in values]
    before = json.dumps(captures)
    assert rank(captures, "cpu_seconds")[0].value == sum(values)
    assert rank(captures, "rss_peak_bytes")[0].value == max(values)
    assert json.dumps(captures) == before


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1.0, True, "1"])
def test_invalid_resource_measurements_are_rejected(value: object) -> None:
    """
    Reject fabricated, coercible and invalid physical resource quantities.

    Args:
        value (object): One malformed observation.

    Returns:
        None: The report refuses to draw unsupported numeric evidence.
    """
    capture_document = profile({"phase": {"cpu_seconds": 1}})
    capture_document["resources"] = {
        "format": "hypothesis-helm-phase-resources-v1",
        "phases": [{"name": "phase", "values": {"cpu_seconds": value}}],
    }
    with pytest.raises(ValueError, match="finite and nonnegative"):
        rank([capture_document], "cpu_seconds")


def test_unobserved_and_interrupted_captures_are_not_zero_cost() -> None:
    """
    Preserve historical and interrupted coverage gaps in independent rankings.

    Returns:
        None: Neither missing records nor lost hooks establish a zero resource cost.
    """
    assert rank([{}], "gpu_seconds")[0].value is None
    assert rank([profile({"phase": {"cpu_seconds": 2}}, complete=False)], "cpu_seconds")[0].value is None


def test_procfs_units_and_missing_platform_metrics(tmp_path: Path) -> None:
    """
    Decode resident pages and storage bytes without confusing them with block counts.

    Args:
        tmp_path (Path): Synthetic procfs directory, independent of the host OS.

    Returns:
        None: Valid bytes preserve units; missing and malformed files produce unavailable metrics.
    """
    assert snapshot(tmp_path).rss is None
    (tmp_path / "statm").write_text("20 3 0 0 0 0 0\n")
    (tmp_path / "io").write_text("rchar: 99999\nread_bytes: 1024\nwrite_bytes: 4096\n")
    observed = snapshot(tmp_path)
    assert observed.rss == 3 * resource.getpagesize()
    assert (observed.read, observed.write) == (1024, 4096)
    (tmp_path / "io").write_text("not a procfs counter")
    assert snapshot(tmp_path).read is None


def test_phase_boundaries_conserve_cpu_wall_and_disk_deltas() -> None:
    """
    Assign nested exclusive intervals once, preserving reaped CPU as a separate metric.

    Returns:
        None: Counter deltas and sampled peaks match independently specified intervals.
    """
    readings = iter([Snapshot(0, 0, 0, 10, 0, 0), Snapshot(2, 1, 0, 20, 100, 0), Snapshot(5, 2, 2, 30, 100, 200)])
    usage = Resources(read=lambda: next(readings))
    usage.transition("Helm rendering")
    receipt = usage.finish()
    rows = {str(row["name"]): row["values"] for row in receipt["phases"]}
    assert rows["Other and orchestration"]["wall_seconds"] == 2
    assert rows["Helm rendering"]["wall_seconds"] == 3
    assert rows["Helm rendering"]["cpu_seconds"] == 1
    assert rows["Helm rendering"]["child_cpu_seconds"] == 2
    assert rows["Helm rendering"]["disk_write_bytes"] == 200
    assert rows["Helm rendering"]["rss_peak_bytes"] == 30


def test_known_phase_boundaries_and_unknown_context_are_explicit() -> None:
    """
    Distinguish rendering, exact pruning, topology selection and unknown source.

    Returns:
        None: Unknown definitions preserve their caller phase without invented attribution.
    """
    assert phase_for("/pkg/hypothesis_helm/charts/testing/rendering.py", "render_output", "Other") == "Helm rendering"
    assert phase_for("/pkg/hypothesis_helm/compiler/passes/pruning.py", "Pruner.candidate", "Other") == "Exact-equivalence analysis"
    assert phase_for("/pkg/hypothesis_helm/compiler/passes/topology.py", "trim_topology", "Other") == "Topology filtering"
    assert phase_for("/unknown.py", "unknown", "Helm rendering") == "Helm rendering"


def test_cuda_event_units_synchronization_and_peak_scope() -> None:
    """
    Exercise the supported CUDA contract with explicit synthetic device observations.

    Returns:
        None: Milliseconds become seconds only after completion and allocator peaks remain bytes.
    """
    calls: list[str] = []

    class Marker:
        def record(self) -> None:
            calls.append("record")

        def synchronize(self) -> None:
            calls.append("synchronize")

        def elapsed_time(self, end_event: Marker) -> float:
            assert calls[-1] == "synchronize"
            return 25.0

    class Adapter:
        def Event(self, *, enable_timing: bool) -> Marker:  # noqa: N802 - upstream API name.
            assert enable_timing
            return Marker()

        def reset_peak_memory_stats(self) -> None:
            calls.append("reset")

        def max_memory_allocated(self) -> int:
            return 4096

    interval = DeviceInterval(Adapter())
    assert interval.finish() == (0.025, 4096)
    assert calls == ["reset", "record", "record", "synchronize"]
    assert DeviceInterval.current("mps") is None


def test_backend_process_capture_and_resource_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Exercise the real spawned backend boundary and redraw metrics without benchmark execution.

    Args:
        tmp_path (Path): Disposable raw capture and report directories.
        monkeypatch (pytest.MonkeyPatch): Scope the existing opt-in profiling environment input.

    Returns:
        None: The actual backend process owns its receipt, metrics, role and figure inventory.
    """
    monkeypatch.setenv(PROFILE_DIRECTORY, str(tmp_path))
    refresh_env()
    plan = Plan(digest({}), (), (Node(Opcode.CONSTANT, table=(State.TRUE,)),), 0, limits=Limits(batch_size=4))

    def execute() -> int:
        worker = Worker(plan, "reference")
        try:
            assert worker.evaluate((0,)).states == prepare(plan, "reference").evaluate((0,)).states
            return 0
        finally:
            worker.close()

    assert capture(execute, tmp_path, "coordinator") == 0
    assert sys.getprofile() is None
    backend = json.loads(next(tmp_path.glob("backend-*.json")).read_text())
    assert backend["resources"]["phases"]
    result = render_profiles(tmp_path, tmp_path / "plots")
    assert result["resources"]["roles"] == ["backend", "coordinator"]
    ranks = json.loads((tmp_path / "plots/resources/rankings.json").read_text())
    assert any(row["value"] is not None for row in ranks["backend"]["cpu_seconds"])
    assert all(row["value"] is None for row in ranks["backend"]["gpu_seconds"])
    assert 'id="plot-question"' in (tmp_path / "plots/resources/backend.svg").read_text()
    assert not any(thread.name == "benchmark-resource-sampler" for thread in threading.enumerate())

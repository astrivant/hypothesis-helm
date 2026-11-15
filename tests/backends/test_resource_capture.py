"""
Exercise profiling inside the actual native CPU or GPU worker selected by CI.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis_helm.compiler.backends.scheduler import Worker
from hypothesis_helm.environment import refresh_env
from hypothesis_helm_benchmarking.comparison.model import Workload
from hypothesis_helm_benchmarking.execution.profiling import PROFILE_DIRECTORY
from hypothesis_helm_benchmarking.reporting.resources import rank


def test_resource_capture_owns_actual_native_device(native_backend: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Require device instrumentation to preserve ordered results and finish its owned capture.

    Args:
        native_backend (str): Explicit CI lane, without silent hardware fallback.
        tmp_path (Path): Disposable capture directory.
        monkeypatch (pytest.MonkeyPatch): Scope the supported profiling input to this test.

    Returns:
        None: CPU metrics are observed; CUDA event and allocator measurements exist on the real CUDA lane.
    """
    monkeypatch.setenv(PROFILE_DIRECTORY, str(tmp_path))
    refresh_env()
    workload = Workload("1" * 40, "local", candidates=8, factors=4, batches=(8,), repeats=2)
    plan, ids, expected = workload.inputs(8)
    worker = Worker(plan, native_backend)
    try:
        result = worker.evaluate(ids)
        assert result.ids == ids
        assert result.states == expected
        device = worker.device
    finally:
        worker.close()
    captures = [json.loads(path.read_text()) for path in tmp_path.glob("backend-*.json")]
    assert len(captures) == 1
    assert captures[0]["capture_complete"] is True
    assert not captures[0]["resources"]["device_errors"]
    assert any(row.value is not None for row in rank(captures, "cpu_seconds"))
    for metric in ("gpu_seconds", "gpu_peak_bytes"):
        measured = [row.value for row in rank(captures, metric) if row.value is not None]
        if device == "cuda":
            assert measured and all(value >= 0 for value in measured)
        else:
            assert not measured

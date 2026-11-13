"""
Require source-bound matched lanes and fail-closed comparison publication in CI.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

PROJECT = Path(__file__).resolve().parents[2]


def test_gpu_refresh_joins_all_matched_lanes_before_the_single_publisher() -> None:
    """
    Keep comparison fanout independent and publication conditional on complete evidence.

    Returns:
        None: GPU refreshes require the comparison while CPU refreshes admit its explicit skip.
    """
    workflow = yaml.safe_load((PROJECT / ".github/workflows/stage-measure.yml").read_text())
    jobs = workflow["jobs"]
    comparison = jobs["refresh-comparison"]
    assert comparison["needs"] == "refresh-request"
    assert comparison["uses"] == "./.github/workflows/stage-backend-comparison.yml"
    assert comparison["with"]["source"] == "${{ github.sha }}"
    assert "inputs.refresh" in comparison["if"] and "inputs.benchmark-backend == 'gpu'" in comparison["if"]
    finish = jobs["refresh-finish"]
    assert "refresh-comparison" in finish["needs"]
    assert "!cancelled()" in finish["if"]
    assert "needs.refresh-comparison.result == 'success'" in finish["if"]
    assert "inputs.benchmark-backend != 'gpu' && needs.refresh-comparison.result == 'skipped'" in finish["if"]
    steps = finish["steps"]
    comparison_input = next(step for step in steps if step.get("with", {}).get("name") == "backend-comparison-plots")
    publisher = next(step for step in steps if step.get("id") == "commit")
    assert comparison_input["if"] == "${{ inputs.benchmark-backend == 'gpu' }}"
    assert comparison_input["with"]["path"] == "studies/backend-comparison"
    assert steps.index(comparison_input) < steps.index(publisher)


def test_comparison_matrix_uses_real_devices_and_same_dispatch_manifest() -> None:
    """
    Bind all three hardware lanes to one frozen source and run before rendering.

    Returns:
        None: Workers cannot substitute missing lanes, different sources or CPU fallback.
    """
    workflow = yaml.safe_load((PROJECT / ".github/workflows/stage-backend-comparison.yml").read_text())
    jobs = workflow["jobs"]
    lanes = jobs["measure"]["strategy"]["matrix"]["include"]
    assert {(lane["backend"], lane["device"]) for lane in lanes} == {("reference", "reference"), ("cpu-vector", "cpu"), ("gpu", "cuda")}
    assert jobs["measure"]["strategy"]["fail-fast"] is False
    assert jobs["measure"]["needs"] == "prepare"
    assert jobs["report"]["needs"] == "measure"
    assert "if" not in jobs["report"]  # A failed or cancelled lane must skip this producer.
    assert jobs["measure"]["runs-on"] == "${{ matrix.backend == 'gpu' && vars.HH_GPU_RUNNER || 'ubuntu-24.04' }}"
    for job in jobs.values():
        checkout = next(step for step in job["steps"] if step.get("uses", "").startswith("actions/checkout@"))
        assert checkout["with"]["ref"] == "${{ inputs.source }}"
        assert checkout["with"]["persist-credentials"] is False
        commands = "\n".join(step.get("run", "") for step in job["steps"])
        assert '--source "$SOURCE" --run "$GITHUB_RUN_ID" --attempt "$GITHUB_RUN_ATTEMPT"' in commands
    command = next(step["run"] for step in jobs["measure"]["steps"] if "run" in step)
    assert '--require-device "$DEVICE"' in command
    report = next(step["run"] for step in jobs["report"]["steps"] if "run" in step)
    assert all(f"backend-comparison/{lane}.json" in report for lane in ("reference", "cpu-vector", "gpu"))
    assert jobs["report"]["steps"][-1]["with"]["name"] == "backend-comparison-plots"


@pytest.mark.parametrize("backend,hardware", [("reference", "CPU x64"), ("cpu-vector", "CPU x64"), ("gpu", "NVIDIA T4")])
def test_study_names_expose_backend_and_hardware(backend: str, hardware: str) -> None:
    """
    Keep names paired with the backend expression that controls runner routing.

    Args:
        backend (str): One supported refresh selection.
        hardware (str): Expected visible hardware classification.

    Returns:
        None: Compute jobs include their backend and hardware, while shared work names CPU.
    """
    workflow = yaml.safe_load((PROJECT / ".github/workflows/stage-measure.yml").read_text())
    jobs = workflow["jobs"]
    for name in ("refresh-study", "refresh-error-surface", "refresh-stress", "refresh-structural-sparsity"):
        job = jobs[name]
        context = "matrix.backend" if name == "refresh-study" else "inputs.benchmark-backend"
        assert "${{ " + context + " }}" in job["name"]
        assert context in job["runs-on"]
        expression = "${{ " + context + " == 'gpu' && 'NVIDIA T4' || 'CPU x64' }}"
        assert expression in job["name"]
        rendered = job["name"].replace(expression, hardware).replace("${{ " + context + " }}", backend)
        assert backend in rendered and hardware in rendered
    for name in ("refresh-prepare-inputs", "refresh-prepare", "refresh-error-surface-merge", "refresh-finish"):
        assert "CPU x64" in jobs[name]["name"]

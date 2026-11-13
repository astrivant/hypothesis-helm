"""
Exercise matched workload, worker ownership, evidence rejection and plot publication.
"""

from __future__ import annotations

import json
from itertools import count
from pathlib import Path

import pytest
from attrs import evolve
from cattrs.errors import ClassValidationError
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis_helm.compiler.backends.engine import Batch, Engine, prepare
from hypothesis_helm.compiler.backends.model import Plan
from hypothesis_helm.reporting.documentation.contents import with_contents
from hypothesis_helm_benchmarking.comparison.cli import main
from hypothesis_helm_benchmarking.comparison.measure import measure
from hypothesis_helm_benchmarking.comparison.model import BACKENDS, Hardware, Lane, Workload, read_lanes, read_workload, save, validate_lane
from hypothesis_helm_benchmarking.comparison.report import report, validate_comparison

HOST = Hardware("Synthetic", "synthetic-x64", 4, "3.13.0", "2.0.0", "synthetic", "CPU")
WORKLOAD = Workload("1" * 40, "local", candidates=32, factors=8, batches=(8, 32), repeats=2)


def simulated_lane(workload: Workload, backend: str) -> Lane:
    """
    Supply explicitly simulated device receipts using real reference evaluation.

    Args:
        workload (Workload): Small deterministic contract-test manifest.
        backend (str): Requested simulated label; no GPU execution is claimed.

    Returns:
        Lane: Synthetic timing evidence unsuitable for a real benchmark conclusion.
    """

    def factory(plan: Plan, selection: str) -> Engine:
        """
        Evaluate with the reference engine and label only the synthetic fixture.

        Args:
            plan (Plan): Exact executable test plan.
            selection (str): Simulated backend label.

        Returns:
            Engine: Real reference implementation with a simulated device field.
        """
        engine = prepare(plan, "reference")
        engine.device = {"reference": "reference", "cpu-vector": "cpu", "gpu": "cuda"}[selection]
        return engine

    ticks = count()
    host = evolve(HOST, accelerator="Synthetic GPU") if backend == "gpu" else HOST
    return measure(workload, backend, host, lambda: float(next(ticks)), factory)


@given(st.integers(min_value=0, max_value=2**32 - 1))
@settings(max_examples=12, deadline=None)
def test_seeded_workload_is_deterministic_and_oracle_matches_reference(seed: int) -> None:
    """
    Check reproducibility and independent truth-state semantics across generated seeds.

    Args:
        seed (int): Replayed finite-dictionary and candidate-order seed.

    Returns:
        None: Both batch sizes preserve the same IDs and oracle states.
    """
    workload = evolve(WORKLOAD, seed=seed)
    first = workload.inputs(8)
    second = workload.inputs(32)
    assert first == workload.inputs(8)
    assert first[1:] == second[1:]
    lane = simulated_lane(workload, "reference")
    validate_lane(workload, lane)


@pytest.mark.parametrize(
    "damage",
    ["source", "run", "attempt", "seed", "repeats", "missing", "duplicate", "fallback", "output", "nan", "negative", "runtime", "cpu"],
)
def test_comparison_rejects_unmatched_or_incomplete_evidence(damage: str) -> None:
    """
    Reject incomparable results instead of manufacturing cross-backend speedups.

    Args:
        damage (str): One independently corrupted comparison boundary.

    Returns:
        None: Every incomplete or non-equivalent lane set is rejected.
    """
    workload = WORKLOAD
    lanes = [simulated_lane(workload, backend) for backend in BACKENDS]
    if damage in {"source", "run", "attempt", "seed", "repeats"}:
        workload = {
            "source": evolve(workload, source="2" * 40),
            "run": evolve(workload, run="123"),
            "attempt": evolve(workload, attempt=2),
            "seed": evolve(workload, seed=42),
            "repeats": evolve(workload, repeats=3),
        }[damage]
    elif damage == "missing":
        lanes.pop()
    elif damage == "duplicate":
        lanes[2] = lanes[1]
    elif damage == "fallback":
        lanes[2] = evolve(lanes[2], device="reference")
    elif damage in {"runtime", "cpu"}:
        host = evolve(lanes[1].hardware, python="3.14.0") if damage == "runtime" else evolve(lanes[1].hardware, cpus=8)
        lanes[1] = evolve(lanes[1], hardware=host)
    else:
        case = lanes[2].cases[0]
        if damage == "output":
            case = evolve(case, output="0" * 64)
        else:
            sample = evolve(case.samples[0], wall=float("nan") if damage == "nan" else -1.0)
            case = evolve(case, samples=(sample, *case.samples[1:]))
        lanes[2] = evolve(lanes[2], cases=(case, *lanes[2].cases[1:]))
    with pytest.raises(ValueError):
        validate_comparison(workload, tuple(lanes))


def test_worker_failure_closes_owned_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Keep a failed measurement from leaking its worker or producing a successful receipt.

    Args:
        monkeypatch (pytest.MonkeyPatch): Corrupt one worker result without pre-closing the engine.

    Returns:
        None: The worker closes even when ordered results do not match.
    """
    engines = []

    def factory(plan: Plan, backend: str) -> Engine:
        """
        Supply a live engine that returns an incomplete first result.

        Args:
            plan (Plan): Small immutable program.
            backend (str): Explicit reference selection.

        Returns:
            Engine: Open engine whose incomplete result must fail admission.
        """
        engine = prepare(plan, backend)

        def incomplete(ids: tuple[int, ...], choices: tuple[tuple[int, ...], ...] = ()) -> Batch:
            """
            Return an intentionally incomplete synthetic worker result.

            Args:
                ids (tuple[int, ...]): Requested ordered candidate IDs.
                choices (tuple[tuple[int, ...], ...]): Unused explicit choice rows.

            Returns:
                Batch: Empty result states that must fail the oracle check.
            """
            return Batch(ids, (), 0.0)

        monkeypatch.setattr(engine, "evaluate", incomplete)
        engines.append(engine)
        return engine

    with pytest.raises(ValueError, match="independent oracle"):
        measure(WORKLOAD, "reference", HOST, lambda: 1.0, factory)
    assert len(engines) == 1 and engines[0].closed


def test_report_replays_committed_measurements_without_rebenchmarking(tmp_path: Path) -> None:
    """
    Generate canonical plots and retain exact measurements for offline redraws.

    Args:
        tmp_path (Path): Isolated synthetic comparison output.

    Returns:
        None: Both figure formats, the question subtitle and typed data survive a CLI round trip.
    """
    lanes = tuple(simulated_lane(WORKLOAD, backend) for backend in BACKENDS)
    report(WORKLOAD, lanes, tmp_path)
    assert read_workload(tmp_path / "workload.json") == WORKLOAD
    assert read_lanes(tmp_path / "measurements.json") == lanes
    readme = (tmp_path / "README.md").read_text()
    assert with_contents(readme, max_depth=3) == readme
    assert "How do backend latency" in (tmp_path / "comparison.svg").read_text()
    assert (tmp_path / "comparison.png").stat().st_size > 1000
    assert (
        main(
            [
                "report",
                "--input",
                str(tmp_path / "workload.json"),
                "--lanes",
                str(tmp_path / "measurements.json"),
                "--output",
                str(tmp_path / "redrawn"),
            ]
        )
        == 0
    )
    assert (tmp_path / "redrawn/measurements.json").read_bytes() == (tmp_path / "measurements.json").read_bytes()


@pytest.mark.parametrize("field,value", [("source", "2" * 40), ("run", "123"), ("attempt", "2")])
def test_cli_rejects_foreign_dispatch_before_starting_workers(tmp_path: Path, field: str, value: str) -> None:
    """
    Catch stale artifacts at the executable entrypoint before running paid work.

    Args:
        tmp_path (Path): Isolated frozen manifest and output.
        field (str): One expected dispatch field.
        value (str): A foreign source, run or attempt.

    Returns:
        None: No result is written for a different dispatch.
    """
    save(tmp_path / "input.json", WORKLOAD)
    with pytest.raises(ValueError, match="different source, run or attempt"):
        main(
            [
                "measure",
                "--input",
                str(tmp_path / "input.json"),
                "--backend",
                "reference",
                f"--{field}",
                value,
                "--output",
                str(tmp_path / "output.json"),
            ]
        )
    assert not (tmp_path / "output.json").exists()


def test_invalid_manifest_rejected_before_execution(tmp_path: Path) -> None:
    """
    Reject unknown fields and unsupported batch/repetition settings.

    Args:
        tmp_path (Path): Isolated malformed retained manifest.

    Returns:
        None: No malformed workload enters a native engine.
    """
    for invalid in (evolve(WORKLOAD, repeats=0), evolve(WORKLOAD, batches=(32, 8)), evolve(WORKLOAD, factors=64)):
        with pytest.raises(ValueError):
            invalid.validate()
    path = tmp_path / "input.json"
    save(path, WORKLOAD)
    payload = json.loads(path.read_text())
    payload["unexpected"] = "field"
    path.write_text(json.dumps(payload))
    with pytest.raises(ClassValidationError):
        read_workload(path)


@pytest.mark.parametrize("value", ["2", True, 2.5])
def test_wire_scalars_are_not_coerced(tmp_path: Path, value: object) -> None:
    """
    Keep strings, booleans and fractional values out of integer manifest fields.

    Args:
        tmp_path (Path): Isolated invalid manifest.
        value (object): Scalar whose JSON type differs from the declared integer.

    Returns:
        None: The typed boundary rejects the lossy representation.
    """
    path = tmp_path / "input.json"
    save(path, WORKLOAD)
    payload = json.loads(path.read_text())
    payload["repeats"] = value
    path.write_text(json.dumps(payload))
    with pytest.raises(ClassValidationError):
        read_workload(path)

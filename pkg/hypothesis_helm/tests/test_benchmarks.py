"""
Verify predictable generated outputs, disjoint benchmarking shards and truthful scaling.
"""

import json
import math
import shutil
import time
from pathlib import Path
from unittest.mock import Mock

import pytest

from hypothesis_helm.charts.runner import Chart
from hypothesis_helm.integrations.sharding import Shard
from hypothesis_helm.reporting.budget import TimeLimitReached
from hypothesis_helm.schemas.contracts import configuration_key, mapping, sequence
from scripts.benchmark_helm import parser
from scripts.benchmarking.plots import paired_ratio
from scripts.benchmarking.runner import Job, execute_worker
from scripts.benchmarking.workload import expected_output, partition_indices, standard_values
from scripts.generate_benchmark_chart import generate


def test_generated_distribution_and_oracle(tmp_path: Path) -> None:
    """
    Recompute quantiles for every finite output and verify requested distribution parameters.

    Args:
        tmp_path (Path): Generated chart location.

    Returns:
        None: The chart has the declared complexity and bounded quantile distribution.
    """
    spec = generate(
        tmp_path,
        input_complexity=12,
        mean_value=42,
        stddev=7,
        output_bins=16,
        precision=4,
        lower=28,
        upper=56,
    )
    chart = Chart.load(tmp_path)
    assert len(mapping(chart.schema["properties"])) == 12
    assert spec["active_inputs"] == 4
    assert spec["unused_inputs"] == 8
    assert math.isclose(float(str(spec["discrete_mean"])), 42)
    for index, emitted in enumerate(sequence(spec["output_strings"])):
        values: dict[str, object] = {
            f"input{bit:03d}": bool((index >> bit) & 1) for bit in range(12)
        }
        assert expected_output(values, spec) == emitted
        assert 28 <= float(str(emitted)) <= 56
    # The oracle recomputes the distribution; it does not trust the generated table.
    sequence(spec["output_strings"])[0] = "tampered"
    assert expected_output(dict.fromkeys(chart.defaults, False), spec) != "tampered"


def test_input_stream_is_bijective_and_output_repetitions_are_controlled() -> None:
    """
    Exhaust a small domain to prove no duplicate inputs occur across quantile cycles.

    Returns:
        None: Every input is unique while consecutive groups share active output bits.
    """
    inputs = [standard_values(index, 5, complexity=6, bins=8) for index in range(64)]
    assert len({configuration_key(value) for value in inputs}) == 64
    assert all(inputs[0][f"input{bit:03d}"] == inputs[7][f"input{bit:03d}"] for bit in range(3))
    assert inputs[0] != inputs[7]
    assert (
        len(
            {
                configuration_key(standard_values(index, 5, complexity=3, bins=8))
                for index in range(8)
            }
        )
        == 8
    )


def test_shards_and_replicas_partition_identical_global_inputs() -> None:
    """
    Preserve global workload identity under uneven CI partitions and different worker counts.

    Returns:
        None: Shard unions equal the global prefix, without overlap or lost input IDs.
    """
    owners: set[int] = set()
    for index in range(1, 4):
        serial = partition_indices(101, Shard(index, 3), 1)[0]
        parallel = partition_indices(101, Shard(index, 3), 4)
        flattened = [item for worker in parallel for item in worker]
        assert serial == flattened
        assert not owners.intersection(flattened)
        owners.update(flattened)
    assert owners == set(range(101))
    # Weak scaling uses base * replicas * shard_total global inputs.
    assert [len(worker) for worker in partition_indices(12 * 4 * 3, Shard(2, 3), 4)] == [12] * 4


@pytest.mark.skipif(shutil.which("helm") is None, reason="requires real Helm")
def test_real_outputs_and_pruning_match_independent_oracle(tmp_path: Path) -> None:
    """
    Compare actual Helm and pruned representative outputs with the declared quantile oracle.

    Args:
        tmp_path (Path): Small standardized chart.

    Returns:
        None: Both execution modes check every input and only exact equivalents skip renders.
    """
    generate(tmp_path, input_complexity=12, mean_value=10, stddev=2, output_bins=16)
    baseline = execute_worker(
        Job(str(tmp_path), list(range(32)), 5, 8, False, "helm", time.perf_counter() + 30)
    )
    filtered = execute_worker(
        Job(str(tmp_path), list(range(32)), 5, 8, True, "helm", time.perf_counter() + 30)
    )
    assert baseline["status"] == filtered["status"] == "passed"
    assert baseline["completed"] == filtered["completed"] == 32
    assert baseline["oracle_checks"] == filtered["oracle_checks"] == 32
    assert baseline["rendered"] == 32
    assert filtered["rendered"] == 4
    assert filtered["pruned"] == 28
    assert baseline["received_mean"] == filtered["received_mean"]
    assert baseline["input_histogram"] == filtered["input_histogram"]


def test_wrong_output_fails_instead_of_becoming_a_representative(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Reject a mismatch before it can seed pruning or contribute successful measurements.

    Args:
        tmp_path (Path): Generated chart location.
        monkeypatch (pytest.MonkeyPatch): Supplies a wrong renderer output.

    Returns:
        None: The failure retains zero oracle successes and zero completed inputs.
    """
    generate(tmp_path, input_complexity=8)
    monkeypatch.setattr(
        "scripts.benchmarking.runner.render", Mock(return_value=[{"data": {"value": "999"}}])
    )
    result = execute_worker(
        Job(str(tmp_path), [0, 1], 5, 8, True, "helm", time.perf_counter() + 30)
    )
    assert result["status"] == "failed"
    assert result["completed"] == result["oracle_checks"] == result["pruned"] == 0
    assert "quantile" in str(result["error"])


def test_censored_timing_is_never_a_scaling_speedup() -> None:
    """
    Exclude unfinished runs rather than dividing their capped runtimes into speedups.

    Returns:
        None: Only paired successful repetitions contribute a ratio.
    """
    baseline: list[dict[str, object]] = [
        {"repeat": 0, "status": "passed", "elapsed_seconds": 10},
    ]
    capped: list[dict[str, object]] = [
        {"repeat": 0, "status": "time-limit", "elapsed_seconds": 1},
    ]
    assert paired_ratio(baseline, capped) is None
    capped[0]["status"] = "passed"
    assert paired_ratio(baseline, capped) == 10


@pytest.mark.parametrize("complexity", [1, 3, 100])
def test_generator_adapts_default_quantile_bits(tmp_path: Path, complexity: int) -> None:
    """
    Accept small input spaces without requiring a separate quantile-bin override.

    Args:
        tmp_path (Path): Chart destination.
        complexity (int): Desired independent input count.

    Returns:
        None: Active bits fit the declared input hierarchy.
    """
    spec = generate(tmp_path, input_complexity=complexity)
    assert int(str(spec["active_inputs"])) <= complexity
    assert json.loads((tmp_path / "benchmark.json").read_text()) == spec


def test_linear_prefix_checkpoints_commit_only_completed_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Record 50-input checkpoints without treating an unfinished target as completed work.

    Args:
        tmp_path (Path): Small finite predictable chart.
        monkeypatch (pytest.MonkeyPatch): Provides fast correct renders and a controlled stop.

    Returns:
        None: Only prefixes 50 and 100 complete before the 121st assertion stops the run.
    """
    spec = generate(tmp_path, input_complexity=12, output_bins=16)
    calls = [0]

    def oracle(values: dict[str, object], config: dict[str, object]) -> str:
        """
        Simulate expiration while evaluating a candidate beyond the second checkpoint.

        Args:
            values (dict[str, object]): Candidate effective values.
            config (dict[str, object]): Declared distribution.

        Returns:
            str: Independent expected output until the controlled stop.
        """
        calls[0] += 1
        if calls[0] == 121:
            raise TimeLimitReached()
        return expected_output(values, config)

    def render(
        chart: object, values: dict[str, object], **kwargs: object
    ) -> list[dict[str, object]]:
        """
        Supply a correct scalar without invoking Helm in the checkpoint bookkeeping test.

        Args:
            chart (object): Chart context.
            values (dict[str, object]): Complete candidate values.
            **kwargs (object): Renderer settings.

        Returns:
            list[dict[str, object]]: Oracle-correct resource.
        """
        return [{"data": {"value": expected_output(values, spec)}}]

    monkeypatch.setattr("scripts.benchmarking.runner.render", render)
    monkeypatch.setattr("scripts.benchmarking.runner.expected_output", oracle)
    started = time.perf_counter()
    result = execute_worker(
        Job(
            str(tmp_path),
            list(range(200)),
            5,
            8,
            True,
            "helm",
            started + 30,
            checkpoints=[50, 100, 150, 200],
            started=started,
        )
    )
    checkpoints = [mapping(item) for item in sequence(result["checkpoints"])]
    assert result["status"] == "time-limit"
    assert result["completed"] == result["oracle_checks"] == 120
    assert [item["requested_permutations"] for item in checkpoints] == [50, 100]
    assert [item["completed"] for item in checkpoints] == [50, 100]
    assert [item["rendered"] for item in checkpoints] == [7, 13]
    assert all(item["remaining"] == 0 for item in checkpoints)


def test_default_linear_grid_and_four_worker_shards() -> None:
    """
    Use fifty-input increments and all shard counts from one through four.

    Returns:
        None: Default controls implement the requested linear benchmark grid.
    """
    args = parser().parse_args([])
    assert args.step == 50
    assert args.counts is None
    assert args.replicas == [1, 2, 3, 4]
    assert args.scaling_counts == list(range(50, 501, 50))

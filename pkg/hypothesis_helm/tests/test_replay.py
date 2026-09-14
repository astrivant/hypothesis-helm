"""
Check memory bounds, historical ordering and mutation isolation of replayable cases.
"""

import hashlib
import json
import pickle
import tracemalloc
from pathlib import Path

import pytest

from hypothesis_helm.benchmarking.charts.workload import load_inputs, partition_indices
from hypothesis_helm.benchmarking.execution.runner import assignment_digest
from hypothesis_helm.charts.model import Chart
from hypothesis_helm.execution.sampling import Sampling
from hypothesis_helm.execution.traversal import order_configurations
from hypothesis_helm.integrations.sharding import Shard
from hypothesis_helm.schemas.combinations import plan_interactions
from hypothesis_helm.schemas.contracts import configuration_key
from hypothesis_helm.schemas.finite import enumerate_values
from hypothesis_helm.schemas.replay import Replay, concatenate, select, transform


def test_replay_views_do_not_construct_or_retain_a_population() -> None:
    """
    Build a billion-position workload while touching only explicitly requested values.

    Returns:
        None: Slicing, transforms and concatenation retain positional metadata only.
    """
    visited: list[int] = []

    def make(index: int) -> dict[str, object]:
        """
        Record actual factory invocations.

        Args:
            index (int): Requested position.

        Returns:
            dict[str, object]: Fresh mutable input.
        """
        visited.append(index)
        return {"value": index}

    values = Replay(10**9, make)
    assert order_configurations(values, lambda value: value, {}, strategy="linear") is values
    view = concatenate(select(values, [3, 1]), values[-2:])
    mapped = transform(view, lambda value: {**value, "flag": True})
    assert visited == [] and len(mapped) == 4
    assert mapped[0] == {"value": 3, "flag": True}
    assert visited == [3]
    assert [item["value"] for item in view] == [3, 1, 10**9 - 2, 10**9 - 1]
    with pytest.raises(IndexError):
        _ = values[10**9]
    with pytest.raises(IndexError):
        _ = values[-(10**9) - 1]
    with pytest.raises(ValueError):
        _ = values[::0]
    selected, _ = Sampling(50, minimum=1).select(view, configuration_key, 42)
    before = list(selected)
    selected[0]["value"] = "mutated"
    assert list(selected) == before


@pytest.mark.parametrize(
    ("fields", "strength", "threshold", "cases", "interactions", "checksum"),
    [
        (4, 2, 0, 11, 24, "1fb981803c6b4c1c45dd1c63a5f72ae199b5a3ad5ca6631ea9e95ba1bff91fe8"),
        (5, 3, 0, 26, 80, "61f2f5bc7a4134c4a4f0226fd1bc718439c9f84dabb90ed7c9fe34be2e2a772b"),
        (4, 2, 10000, 16, 16, "8ef4ce9cf17a3d124e4bd45f4af6e21d848f27200facc883dffb1b8c6335fe30"),
    ],
)
def test_replay_plans_match_pre_conversion_fixtures(
    fields: int, strength: int, threshold: int, cases: int, interactions: int, checksum: str
) -> None:
    """
    Preserve the exact ordered populations recorded before the storage conversion.

    Args:
        fields (int): Independent Boolean fields.
        strength (int): Required interaction order.
        threshold (int): Automatic exhaustive threshold.
        cases (int): Historical candidate and retained case count.
        interactions (int): Historical covered interaction count.
        checksum (str): SHA-256 of the previous ordered JSON configurations.

    Returns:
        None: Coverage counts, values and ordering match the former list-based planner.
    """
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {f"p{index}": {"type": "boolean"} for index in range(fields)},
        "required": [f"p{index}" for index in range(fields)],
    }
    plan = plan_interactions(schema, strength, exhaustive_threshold=threshold)
    assert isinstance(plan.values, Replay)
    assert len(plan.values) == plan.candidates == cases
    assert plan.interactions == interactions
    assert hashlib.sha256(json.dumps(list(plan.values), sort_keys=True).encode()).hexdigest() == checksum
    plan.values[0].clear()
    assert hashlib.sha256(json.dumps(list(plan.values), sort_keys=True).encode()).hexdigest() == checksum


def test_worker_ranges_preserve_hashes_and_small_serialization() -> None:
    """
    Keep huge and empty worker assignments compact without changing their IDs or hashes.

    Returns:
        None: Assignment bytes stay bounded and the historical checksum is unchanged.
    """
    workers = partition_indices(10**12, Shard(2, 3), 6)
    assert len(pickle.dumps(workers)) < 1024
    assert all(isinstance(worker, range) for worker in workers)
    assert sum(map(len, workers)) == len(range(1, 10**12, 3))
    assert workers[0][0] == 1 and workers[-1][-1] == range(1, 10**12, 3)[-1]
    for worker in partition_indices(2, Shard(3, 3), 6) + partition_indices(100, Shard(2, 3), 6):
        assert assignment_digest(worker) == hashlib.sha256(json.dumps(list(worker)).encode()).hexdigest()


def test_jsonl_inputs_replay_and_reject_changed_records(tmp_path: Path) -> None:
    """
    Read custom workloads by verified byte offsets instead of storing parsed documents.

    Args:
        tmp_path (Path): Custom JSONL workload directory.

    Returns:
        None: Mutable instances are independent, duplicate inputs and edited bytes are rejected.
    """
    source = tmp_path / "values.jsonl"
    source.write_text('{"nested": {"value": 1}}\n\n{"nested": {"value": 2}}\n')
    chart = Chart(tmp_path, {"type": "object"}, {})
    values = load_inputs(chart, source)
    assert isinstance(values, Replay)
    first = values[0]["nested"]
    assert isinstance(first, dict)
    first["value"] = 99
    assert values[0] == {"nested": {"value": 1}}
    assert values[-1] == {"nested": {"value": 2}}
    source.write_text('{"nested": {"value": 3}}\n\n{"nested": {"value": 2}}\n')
    with pytest.raises(ValueError, match="changed after validation"):
        _ = values[0]
    source.write_text('{"a": 1, "b": 2}\n{"b": 2, "a": 1}\n')
    with pytest.raises(ValueError, match="distinct effective inputs"):
        load_inputs(chart, source)


def test_finite_replay_uses_less_memory_than_materialized_cases() -> None:
    """
    Measure bounded replay storage against the same fully constructed Boolean population.

    Returns:
        None: Planning peak stays below the additional memory needed to retain all generated cases.
    """
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {f"input{index}": {"type": "boolean"} for index in range(11)},
        "required": [f"input{index}" for index in range(11)],
    }
    tracemalloc.start()
    try:
        values = enumerate_values(schema, 4096)
        retained, planning_peak = tracemalloc.get_traced_memory()
        tracemalloc.reset_peak()
        materialized = list(values)
        _, expanded_peak = tracemalloc.get_traced_memory()
        assert len(materialized) == 2048
        assert planning_peak < expanded_peak - retained
    finally:
        tracemalloc.stop()

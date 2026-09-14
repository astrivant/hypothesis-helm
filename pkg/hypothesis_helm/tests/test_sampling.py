"""
Verify sampling floors, protected cases, finite plans, dry runs, and disjoint shards.
"""

import json
from pathlib import Path
from textwrap import dedent

import pytest

from hypothesis_helm.benchmarking.charts.generator import generate
from hypothesis_helm.charts.runner import Chart, check_chart
from hypothesis_helm.execution.estimate import estimate_suite
from hypothesis_helm.execution.sampling import Sampling
from hypothesis_helm.execution.suite import run_suite
from hypothesis_helm.integrations.sharding import Shard
from hypothesis_helm.reporting.shards import aggregate
from hypothesis_helm.schemas.contracts import mapping, sequence


def test_sampling_is_nested_stable_and_protected() -> None:
    """
    Preserve sample floors and mandatory cases independently of input order.

    Returns:
        None: Fixed seeds select nested, unique subsets and small populations remain intact.
    """
    values = [str(index) for index in range(1000)]
    small, evidence = Sampling(30, 128).select(values, str, 19, protected={"999"})
    larger, _ = Sampling(70, 128).select(values, str, 19, protected={"999"})
    reversed_sample, _ = Sampling(30, 128).select(list(reversed(values)), str, 19, protected={"999"})
    assert len(small) == 300 and len(larger) == 700
    assert set(small) <= set(larger) and "999" in small
    assert set(small) == set(reversed_sample)
    assert evidence["omitted"] == 700 and evidence["bug_recall_guaranteed"] is False
    assert Sampling(1, 128).select(values[:100], str, 19)[0] == values[:100]
    assert len(Sampling(1, 128).select(values, str, 19)[0]) == 128
    assert Sampling(30, 128).select(values, str, 20)[0] != small
    assert Sampling().select([], str, 0)[0] == []


@pytest.mark.parametrize("percent,minimum", [(0, 1), (101, 1), (float("nan"), 1), (70, 0)])
def test_invalid_sampling_is_rejected(percent: float, minimum: int) -> None:
    """
    Reject ambiguous or invalid sampling requests before executing work.

    Args:
        percent (float): Invalid retained percentage or valid percentage paired with a bad floor.
        minimum (int): Requested retained floor.

    Returns:
        None: Invalid requests fail validation.
    """
    with pytest.raises(ValueError):
        Sampling(percent, minimum)


@pytest.mark.parametrize("topology,exhaustive", [(0, False), (2, False), (0, True)])
def test_finite_sampling_preserves_defaults_and_topology(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, topology: int, exhaustive: bool
) -> None:
    """
    Apply sampling before traversal while retaining baseline and topology representatives.

    Args:
        tmp_path (Path): Finite chart and result directory.
        monkeypatch (pytest.MonkeyPatch): Deterministic rendering without subprocess overhead.
        topology (int): Optional symbolic topology filter.
        exhaustive (bool): Enumerate the full domain before selecting a sample.

    Returns:
        None: Known omissions are reported and default inputs are always evaluated.
    """
    generate(tmp_path, input_complexity=8, output_bins=4)
    chart = Chart.load(tmp_path)
    observed: list[dict[str, object]] = []

    def rendered(chart: Chart, values: dict[str, object], **kwargs: object) -> list[dict[str, object]]:
        """
        Record input identity and return a valid manifest for execution checks.

        Args:
            chart (Chart): Chart being evaluated.
            values (dict[str, object]): Selected overrides, including the empty baseline.
            **kwargs (object): Renderer context.

        Returns:
            list[dict[str, object]]: Valid constant ConfigMap for this selection test.
        """
        observed.append(values)
        return [{"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "test"}, "data": {"value": "valid"}}]

    monkeypatch.setattr("hypothesis_helm.charts.runner.render", rendered)
    result = check_chart(
        chart,
        permutations=None if exhaustive else 2,
        exhaustive=exhaustive,
        trim_topology=topology,
        sampling=Sampling(30, 8),
        time_limit=10,
    )
    assert result["status"] == "passed" and observed[0] == {}
    evidence = result["sampling"]
    assert isinstance(evidence, dict)
    assert evidence["omitted"] > 0 and result["coverage_complete"] is False
    assert evidence["protected"] == (4 if topology else 0)


@pytest.mark.parametrize("size,percent,minimum", [(12, 30, 2), (2, 1, 1)])
def test_sampled_shards_match_dry_run_and_aggregate(tmp_path: Path, size: int, percent: int, minimum: int) -> None:
    """
    Execute the globally sampled subset once across shards, including empty partitions.

    Args:
        tmp_path (Path): Saved suite and isolated shard reports.
        size (int): Number of available properties.
        percent (int): Retained percentage.
        minimum (int): Sample floor.

    Returns:
        None: Estimates and worker reports agree, and aggregation rejects mixed policies.
    """
    source = tmp_path / "suite"
    source.mkdir()
    blocks = [
        dedent("""
        from pathlib import Path
        """)
    ]
    for index in range(size):
        blocks.append(
            dedent(f"""
            def test_value_{index}():
                destination = Path(__file__).parent / "ran-{index}"
                assert not destination.exists()
                destination.touch()
            """)
        )
    (source / "test_chart_values.py").write_text("\n".join(blocks))
    policy = Sampling(percent, minimum)
    estimate = estimate_suite(source, sampling=policy, cache=False)
    expected = {mapping(row)["test"] for row in sequence(estimate["properties"])}
    seen: set[str] = set()
    reports = []
    for index in (1, 2, 3):
        assert (
            run_suite(
                source,
                sampling=policy,
                cache=False,
                jobs=2,
                shard=Shard(index, 3),
                artifact_dir=tmp_path / "reports",
                run_id="sampling-test",
            )
            == 0
        )
        path = tmp_path / "reports/shards" / f"{index}-of-3" / "report.json"
        report = json.loads(path.read_text())
        selected = set(report["shard"]["tests"])
        assert not seen & selected
        seen.update(selected)
        assert report["sampling"]["retained"] == len(expected)
        reports.append(path)
    assert seen == expected and len(list(source.glob("ran-*"))) == len(expected)
    assert aggregate(reports, 3, "sampling-test", tmp_path / "final") == 0
    changed = json.loads(reports[0].read_text())
    changed["sampling"]["minimum"] += 1
    reports[0].write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="sampling"):
        aggregate(reports, 3, "sampling-test", tmp_path / "invalid")

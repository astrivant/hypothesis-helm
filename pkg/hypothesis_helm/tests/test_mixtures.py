"""
Check categorical topology fixtures against independent schema and manifest oracles.
"""

import json
import shutil
from pathlib import Path

import pytest

from hypothesis_helm.benchmarking.benchmark_matrix import bundle_key, reference_space
from hypothesis_helm.benchmarking.generate_benchmark_chart import generate
from hypothesis_helm.benchmarking.mixtures import normalized_weights
from hypothesis_helm.benchmarking.structures import expected_manifests
from hypothesis_helm.charts.runner import Chart, render
from hypothesis_helm.schemas.contracts import mapping


@pytest.mark.parametrize("weights", [None, {"dependencies": 1, "interactions": 1, "equivalence": 1}])
def test_mixed_oracle(tmp_path: Path, weights: dict[str, float] | None) -> None:
    """
    Independently verify every valid assignment of a small reproducible mixed chart.

    Args:
        tmp_path (Path): Fixture output root.
        weights (dict[str, float] | None): Uniform or supported-category distribution.

    Returns:
        None: All actual Helm manifests agree with the independent component oracle.
    """
    helm = shutil.which("helm")
    if helm is None:
        pytest.skip("Helm required")
    spec = generate(
        tmp_path / "chart",
        input_complexity=7,
        output_bins=4,
        topology_components=12,
        topology_weights=weights,
    )
    repeated = generate(
        tmp_path / "repeat",
        input_complexity=7,
        output_bins=4,
        topology_components=12,
        topology_weights=weights,
    )
    assert spec == repeated
    chart = Chart.load(tmp_path / "chart")
    truth, _ = reference_space(chart, spec, 192)
    assert truth
    for encoded in sorted(truth):
        values = json.loads(encoded)
        actual = render(chart, values, helm=helm, release="matrix")
        assert bundle_key(actual) == bundle_key(expected_manifests(values, spec))
        names = [(item["kind"], mapping(item["metadata"])["name"]) for item in actual]
        assert len(names) == len(set(names))
    generate(tmp_path / "chart", input_complexity=7, output_bins=4, force=True)
    assert not list((tmp_path / "chart/templates").glob("structure-component-*.yaml"))


@pytest.mark.parametrize(
    "weights",
    [{}, {"unknown": 1}, {"dependencies": -1}, {"dependencies": float("nan")}, {"dependencies": 0}],
)
def test_invalid_mixture_weights(weights: dict[str, float]) -> None:
    """
    Reject invalid distributions before generating any chart files.

    Args:
        weights (dict[str, float]): Invalid categorical weights.

    Returns:
        None: Invalid weights cannot silently fall back to uniform sampling.
    """
    with pytest.raises(ValueError):
        normalized_weights(weights)


@pytest.mark.parametrize("weights", [None, {"dependencies": 1, "interactions": 1, "equivalence": 1}])
def test_nested_components(tmp_path: Path, weights: dict[str, float] | None) -> None:
    """
    Keep component wiring fixed while added gate depths change actual resource visibility.

    Args:
        tmp_path (Path): Fixture output root.
        weights (dict[str, float] | None): Uniform or supported component distribution.

    Returns:
        None: Sampled manifests match an independent oracle and depth prefixes remain stable.
    """
    import random

    from hypothesis_helm.schemas.contracts import sequence

    helm = shutil.which("helm")
    if not helm:
        pytest.skip("Helm required")
    previous = None
    for label, depths in (
        ("shallow", {1: 1.0}),
        ("deep", {5: 1.0}),
        ("random", dict.fromkeys(range(1, 6), 1.0)),
    ):
        spec = generate(
            tmp_path / label,
            input_complexity=10,
            output_bins=4,
            topology_components=12,
            topology_weights=weights,
            topology_depth_weights=depths,
        )
        chart = Chart.load(tmp_path / label)
        truth, _ = reference_space(chart, spec, 1536)
        components = [mapping(component) for component in sequence(mapping(spec["structure"])["components"])]
        if previous is not None:
            for first, current in zip(previous, components, strict=True):
                assert first["paths"] == current["paths"] and first["name"] == current["name"]
                left, right = sequence(first["gate_paths"]), sequence(current["gate_paths"])
                width = min(len(left), len(right))
                assert left[:width] == right[:width]
        previous = components
        assert all(component["gate_depth"] in depths for component in components)
        samples = random.Random(42).sample(sorted(truth), 12) + [sorted(truth)[-1]]
        for encoded in samples:
            values = json.loads(encoded)
            assert bundle_key(render(chart, values, helm=helm, release="matrix")) == bundle_key(expected_manifests(values, spec))
        from hypothesis_helm.benchmarking.benchmark_nesting import select_plan

        reference: dict[str, object] = {
            "values": [
                chart.defaults,
                *[json.loads(value) for value in sorted(truth) if json.loads(value) != chart.defaults],
            ]
        }
        planned = select_plan(chart, reference, 8, 2, 2026)
        assert mapping(planned["planning"])["effective_strength"] == 8
        assert mapping(planned["planning"])["strategy"] == "interactions"

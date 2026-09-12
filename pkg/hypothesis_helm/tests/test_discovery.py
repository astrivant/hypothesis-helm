"""
Validate seeded defect fixtures independently of the interaction planner.
"""

import itertools
import shutil
from pathlib import Path

import pytest

from hypothesis_helm.charts.runner import render
from hypothesis_helm.schemas.combinations import plan_interactions
from hypothesis_helm.schemas.contracts import mapping
from scripts.benchmark_discovery import Fault, faults, fixture


def test_strength_exposes_higher_order_fault(tmp_path: Path) -> None:
    """
    Verify that pairwise coverage misses a known triple which three-way coverage exposes.

    Args:
        tmp_path (Path): Generated fixture directory.

    Returns:
        None: The actual planner exposes the defect at its required strength.
    """
    defect = Fault("bug000", {f"input{bit:03d}": True for bit in range(3)})
    chart = fixture(tmp_path, 8, [defect])
    pairwise = plan_interactions(chart.schema, 2, exhaustive_threshold=0)
    triples = plan_interactions(chart.schema, 3, exhaustive_threshold=0)
    assert not any(defect.active(values) for values in pairwise.values)
    assert any(defect.active(values) for values in triples.values)


def test_helm_faults_match_independent_triggers(tmp_path: Path) -> None:
    """
    Exhaust a tiny Helm fixture to verify both active and inactive defect outcomes.

    Args:
        tmp_path (Path): Generated chart directory.

    Returns:
        None: Every emitted defect field matches its independently evaluated trigger.
    """
    if not shutil.which("helm"):
        pytest.skip("Helm is required")
    defects = faults(3, 3, 4, 2026)
    assert defects == faults(3, 3, 4, 2026)
    assert len({tuple(sorted(defect.terms.items())) for defect in defects}) == len(defects)
    chart = fixture(tmp_path, 3, defects)
    for bits in itertools.product([False, True], repeat=3):
        values: dict[str, object] = {f"input{bit:03d}": value for bit, value in enumerate(bits)}
        resources = render(chart, values)
        data = mapping(
            next(
                resource
                for resource in resources
                if mapping(resource["metadata"])["name"] == "injected-faults"
            )["data"]
        )
        for defect in defects:
            assert (data[defect.name] == "incorrect") == defect.active(values)


def test_generator_bug_percentage(tmp_path: Path) -> None:
    """
    Verify exact populations, reproducible placement and bounded generation.

    Args:
        tmp_path (Path): Generated percentage-based fault fixture directory.

    Returns:
        None: Injected counts match the documented percentage denominator.
    """
    from scripts.benchmarking.faults import select_faults
    from scripts.generate_benchmark_chart import generate

    selected, metadata = select_faults(4, (2, 3), 50, 2026, 100)
    assert len(selected) == 28
    assert selected == select_faults(4, (2, 3), 50, 2026, 100)[0]
    assert selected != select_faults(4, (2, 3), 50, 42, 100)[0]
    full, _ = select_faults(4, (2, 3), 100, 2026, 100)
    expected = {
        tuple(zip((f"input{bit:03d}" for bit in subset), values, strict=True))
        for order in (2, 3)
        for subset in itertools.combinations(range(4), order)
        for values in itertools.product([False, True], repeat=order)
    }
    assert {tuple(fault.terms.items()) for fault in full} == expected
    spec = generate(tmp_path, input_complexity=4, bug_percent=50, bug_orders=(2, 3))
    assert spec["bugs"] == metadata
    assert (tmp_path / "templates/faults.yaml").exists()
    generate(tmp_path, input_complexity=4, force=True)
    assert not (tmp_path / "templates/faults.yaml").exists()
    with pytest.raises(ValueError, match="max-bugs"):
        select_faults(100, (6,), 1, 2026, 1000)

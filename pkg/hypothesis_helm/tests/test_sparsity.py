"""
Check exact discrete distribution metrics and reproducible input thinning.
"""

import pytest

from scripts.benchmark_sparsity import quality, samples


def test_distribution_quality() -> None:
    """
    Check identical distributions, missed support and ordered CDF differences.

    Returns:
        None: Known finite examples have exact expected distances.
    """
    reference = {"0.0": 1, "1.0": 1, "2.0": 2}
    assert quality({"0.0": 10, "1.0": 10, "2.0": 20}, reference) == {
        "coverage": 1,
        "total_variation": 0,
        "cdf_error": 0,
    }
    assert quality({"0.0": 4}, reference) == {
        "coverage": 1 / 3,
        "total_variation": 0.75,
        "cdf_error": 0.75,
    }
    with pytest.raises(ValueError):
        quality({}, reference)


def test_nested_samples() -> None:
    """
    Ensure sparse runs are unique reproducible subsets of their predecessors.

    Returns:
        None: Sample sizes decrease and no duplicate inputs enter a run.
    """
    stages = samples(128, 0.25, 6, 2026)
    assert [len(stage) for stage in stages] == [128, 32, 8, 2, 1]
    assert stages == samples(128, 0.25, 6, 2026)
    assert stages != samples(128, 0.25, 6, 42)
    for larger, smaller in zip(stages, stages[1:], strict=False):
        assert len(set(larger)) == len(larger)
        assert set(smaller) < set(larger)
    with pytest.raises(ValueError):
        samples(128, 1, 5, 0)

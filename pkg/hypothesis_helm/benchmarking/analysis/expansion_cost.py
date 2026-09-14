"""
Calculate exact sampling expectations for an explicitly bounded region-expansion model.
"""

import math


def expected_checks(size: int, errors: int, sample: int) -> float:
    """
    Compute expected checks when one discovered error expands the entire region.

    Args:
        size (int): Number of distinct configurations in the region.
        errors (int): Erroneous configurations within it.
        sample (int): Uniform initial sample size, without replacement or forced representatives.

    Returns:
        float: Exact finite-population expectation evaluated in floating point.
    """
    if not 0 <= errors <= size or not 0 <= sample <= size:
        raise ValueError("require 0 <= errors, sample <= region size")
    probability = 1 - math.comb(size - errors, sample) / math.comb(size, sample)
    return sample + (size - sample) * probability


def equal_regions(total: int, regions: int, errors: int, retention: float) -> tuple[float, float]:
    """
    Bound expected work across equal regions by concentrating or spreading a fixed error count.

    Args:
        total (int): Fixed number of configurations.
        regions (int): Equal-sized regions dividing the total.
        errors (int): Total erroneous configurations, held constant between placements.
        retention (float): Initial fraction kept per region, rounded upward with at least one representative.

    Returns:
        tuple[float, float]: Minimum and maximum expected checks under the stated uniform-sampling model.
    """
    if total < 1 or regions < 1 or total % regions or not 0 <= errors <= total or not 0 < retention <= 1:
        raise ValueError("require equal nonempty regions, valid error count and retention in (0, 1]")
    size = total // regions
    sample = max(1, math.ceil(size * retention))
    full, tail = divmod(errors, size)
    low = float(full * size)
    if full < regions:
        low += expected_checks(size, tail, sample) + (regions - full - 1) * sample
    each, extra = divmod(errors, regions)
    high = (regions - extra) * expected_checks(size, each, sample)
    if extra:
        high += extra * expected_checks(size, each + 1, sample)
    return low, high

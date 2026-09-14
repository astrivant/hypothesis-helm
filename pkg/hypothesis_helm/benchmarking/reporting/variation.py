"""
Show empirical variation across comparable repeats without assuming a normal distribution.
"""

import math
from collections.abc import Sequence
from statistics import mean, stdev

from matplotlib.axes import Axes


def bands(
    axis: Axes,
    xs: Sequence[float],
    centers: Sequence[float],
    deviations: Sequence[float],
    counts: Sequence[int],
    color: str,
    *,
    upper: float | None = None,
) -> None:
    """
    Shade one and two sample standard deviations around recorded means.

    Args:
        axis (Axes): Destination axes.
        xs (Sequence[float]): Fixed parameter settings.
        centers (Sequence[float]): Arithmetic means at those settings.
        deviations (Sequence[float]): Sample deviations, using the n minus one denominator.
        counts (Sequence[int]): Comparable observations contributing to each estimate.
        color (str): Series color shared with its mean line.
        upper (float | None): Optional physical upper bound, such as 100 for percentages.

    Returns:
        None: Bands and whiskers omit singleton and missing estimates; endpoints respect physical bounds.
    """
    rows = list(zip(xs, centers, deviations, counts, strict=True))
    valid = [n >= 2 and math.isfinite(center) and math.isfinite(deviation) for _, center, deviation, n in rows]
    if not any(valid):
        return
    samples = [n for (_, _, _, n), good in zip(rows, valid, strict=True) if good]
    for scale, alpha, width in ((2, 0.10, 0.6), (1, 0.22, 1.4)):
        lows = [
            max(0, center - scale * deviation) if good else math.nan for (_, center, deviation, _), good in zip(rows, valid, strict=True)
        ]
        highs = [
            min(upper if upper is not None else math.inf, center + scale * deviation) if good else math.nan
            for (_, center, deviation, _), good in zip(rows, valid, strict=True)
        ]
        axis.fill_between(xs, lows, highs, color=color, alpha=alpha, label=f"_variation_n={min(samples)}:{max(samples)}")
        # Whiskers keep isolated measured settings visible when a band has no neighbouring point.
        axis.errorbar(
            [x for (x, _, _, _), good in zip(rows, valid, strict=True) if good],
            [center for (_, center, _, _), good in zip(rows, valid, strict=True) if good],
            yerr=[
                [center - low for (_, center, _, _), low, good in zip(rows, lows, valid, strict=True) if good],
                [high - center for (_, center, _, _), high, good in zip(rows, highs, valid, strict=True) if good],
            ],
            fmt="none",
            color=color,
            alpha=0.55,
            elinewidth=width,
            capsize=2,
        )


def repeated_line(
    axis: Axes,
    xs: Sequence[float],
    observations: Sequence[Sequence[float]],
    label: str,
    color: str,
    *,
    upper: float | None = None,
) -> list[float]:
    """
    Plot means with measured spread, preserving gaps where no comparable run completed.

    Args:
        axis (Axes): Destination axes.
        xs (Sequence[float]): Fixed parameter settings, not repeated checkpoints from a single run.
        observations (Sequence[Sequence[float]]): Independent repetitions or declared seed trials per setting.
        label (str): Legend description identifying the measured population.
        color (str): Mean, band and whisker color.
        upper (float | None): Optional physical upper bound.

    Returns:
        list[float]: Means, including NaN for missing observations.
    """
    centers = [mean(batch) if batch else math.nan for batch in observations]
    deviations = [stdev(batch) if len(batch) > 1 else math.nan for batch in observations]
    axis.plot(xs, centers, "o-", markersize=4, linewidth=1.5, label=label, color=color)
    bands(axis, xs, centers, deviations, [len(batch) for batch in observations], color, upper=upper)
    return centers

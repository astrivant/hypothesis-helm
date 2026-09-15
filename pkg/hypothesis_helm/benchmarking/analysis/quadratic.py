"""
Fit a scaled two-factor polynomial to observed cell means without extrapolating.
"""

import math

import numpy as np
from attrs import frozen


@frozen
class Polynomial:
    """
    Store the fitted polynomial and descriptive training residuals.

    Attributes:
        coefficients (tuple[float, ...]): Coefficients in the recorded powers order.
        bounds (tuple[float, float, float, float]): Minimum and maximum x, then minimum and maximum y.
        rmse (float): Root mean squared error across fitted cell means.
        r_squared (float | None): Explained variation, undefined for constant observations.
        residual_sd (float): Residual deviation using cells minus fitted terms degrees of freedom.
        cells (int): Number of distinct measured settings.
        powers (tuple[tuple[int, int], ...]): Exponents of u and v for each coefficient.
        degree (int): Maximum total polynomial degree.
    """

    coefficients: tuple[float, ...]
    bounds: tuple[float, float, float, float]
    rmse: float
    r_squared: float | None
    residual_sd: float
    cells: int
    powers: tuple[tuple[int, int], ...]
    degree: int

    def predict(self, x: float, y: float) -> float:
        """
        Evaluate inside the fitted rectangle, retaining negative predictions for diagnosis.

        Args:
            x (float): First factor in original units.
            y (float): Second factor in original units.

        Returns:
            float: Predicted response in original units.
        """
        low_x, high_x, low_y, high_y = self.bounds
        if not low_x <= x <= high_x or not low_y <= y <= high_y:
            raise ValueError("prediction outside fitted factor bounds")
        u = 2 * (x - low_x) / (high_x - low_x) - 1
        v = 2 * (y - low_y) / (high_y - low_y) - 1
        return sum(coefficient * term for coefficient, term in zip(self.coefficients, (u**i * v**j for i, j in self.powers), strict=True))


def fit(points: list[tuple[float, float, float]], degree: int = 2) -> Polynomial:
    """
    Estimate a quadratic or quartic by equal-cell ordinary least squares.

    Args:
        points (list[tuple[float, float, float]]): Unique x, y cells and their mean measured responses.
        degree (int): Total degree, either two or four.

    Returns:
        Polynomial: Full-rank fit with descriptive residual diagnostics.
    """
    if degree not in (2, 4):
        raise ValueError("degree must be two or four")
    powers: tuple[tuple[int, int], ...] = ((0, 0), (1, 0), (0, 1), (1, 1), (2, 0), (0, 2))
    if degree == 4:
        powers += tuple((i, total - i) for total in (3, 4) for i in range(total + 1))
    terms = len(powers)
    if len(points) <= terms or not all(math.isfinite(value) for point in points for value in point):
        raise ValueError(f"need more than {'six' if terms == 6 else terms} finite cells to fit and assess coefficients")
    if len({(x, y) for x, y, _ in points}) != len(points):
        raise ValueError("average repeated measurements before fitting")
    x, y, z = np.asarray(points, dtype=float).T
    bounds = float(x.min()), float(x.max()), float(y.min()), float(y.max())
    if bounds[0] == bounds[1] or bounds[2] == bounds[3]:
        raise ValueError("both factors must vary")
    u = 2 * (x - bounds[0]) / (bounds[1] - bounds[0]) - 1
    v = 2 * (y - bounds[2]) / (bounds[3] - bounds[2]) - 1
    design = np.column_stack([u**i * v**j for i, j in powers])
    coefficients, _, rank, _ = np.linalg.lstsq(design, z, rcond=None)
    if rank != terms:
        raise ValueError(f"factor settings cannot identify all {terms} degree-{degree} coefficients")
    residual = z - design @ coefficients
    sse = float(residual @ residual)
    total = float(np.sum((z - z.mean()) ** 2))
    return Polynomial(
        tuple(float(value) for value in coefficients),
        bounds,
        math.sqrt(sse / len(points)),
        1 - sse / total if total > 0 else None,
        math.sqrt(sse / (len(points) - terms)),
        len(points),
        powers,
        degree,
    )

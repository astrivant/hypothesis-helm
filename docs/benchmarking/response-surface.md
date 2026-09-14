# Quadratic response surfaces

[Benchmarking](../../benchmarks/README.md) · [Collected and fitted surfaces](../../benchmarks/studies/error-surface/quadratic-fits.md)

We expect each control to affect runtime and error discovery, and one control to change
another's effect. A quadratic gives these hypotheses explicit terms without assuming
that every effect increases monotonically. We estimate its coefficients from measurements;
we do not fabricate observations from those hypotheses.

For each filtering method, we fit runtime and missed erroneous inputs separately:

```text
prediction(x, y) = b0 + b1*u + b2*v + b12*u*v + b11*u² + b22*v²
u = 2*(x - xmin)/(xmax - xmin) - 1
v = 2*(y - ymin)/(ymax - ymin) - 1
```

| Parameter | Meaning |
| --- | --- |
| `x`, `y` | The two varied controls, identified on each graph. In the clustering study: failure clustering and requested error percentage. |
| `xmin`, `xmax`, `ymin`, `ymax` | Smallest and largest measured settings. Predictions are restricted to this rectangle. |
| `u`, `v` | Controls rescaled to -1 through 1, so different units do not dominate numerical fitting. |
| `b0` | Predicted response at the midpoint of both controls. |
| `b1`, `b2` | Individual slopes at that midpoint, per unit of the rescaled control. |
| `b12` | Interaction: how changing one control changes the other's slope. |
| `b11`, `b22` | Curvature along each control; these allow a bend instead of a straight-line response. |

All six coefficients have the response's units: seconds or erroneous input counts.
The generated `quadratic-fits.json` records their values, bounds, cell counts and fit diagnostics.
Other chart settings remain fixed within each surface. An erroneous input count is not a count of distinct bugs.

## Estimation and interpretation

We average paired repeats at each setting, then use ordinary least squares with equal
weight per cell. A fit requires more than six distinct cells, a full-rank six-column
model matrix, and a complete grid of completed repeats. Timed-out or missing cells
prevent fitting that surface: dropping slow measurements could bias the result.

Each figure places measured means beside a continuous quadratic prediction and a
residual panel (observed minus predicted). Measured labels include one sample standard
deviation when repeats are available. Residuals reveal structure the quadratic misses.
The continuous plot between integer settings is a model visualization, not a measurement
or necessarily an executable chart configuration.

RMSE is the typical cell-mean prediction error in the response's units. R² describes
how much observed variation the fit explains; it is undefined when every observation
is identical. `residual_sd` uses the remaining `cells - 6` degrees of freedom.
These are training-data diagnostics, not confidence intervals or validation on unseen charts.
We do not add confidence bands that assume independent, constant-variance errors across
cells: the experiment deliberately reuses paired seeds.

The quadratic is descriptive. It can predict negative runtimes or error counts outside
physical bounds, and we leave these visible to expose a poor fit. Discontinuities from
filter decisions may need a different model. Neither a fitted peak nor the largest
observed value proves the global worst case.

## Regeneration and reference

The existing refresh's `error-surface` study generates these fits with its other plots.
To regenerate them from retained measurements without running Helm again:

```sh
hypothesis-helm-benchmark error-surface --plot-only --output benchmarks/studies/error-surface
```

The polynomial follows the two-factor quadratic form described in the
[NIST/SEMATECH handbook: Response surface designs](https://www.itl.nist.gov/div898/handbook/pri/section3/pri336.htm).
Our measurement design is a full grid of the chosen factor settings, not a central
composite or Box-Behnken design. Choosing a quadratic model does not change that design.

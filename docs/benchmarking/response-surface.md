# Quadratic response surfaces

<!-- toc:start -->
**Table of contents**

- [Estimation and interpretation](#estimation-and-interpretation)
- [Regeneration and reference](#regeneration-and-reference)
- [Quadratic versus quartic comparison](#quadratic-versus-quartic-comparison)
- [Optional symbolic regression](#optional-symbolic-regression)
<!-- toc:end -->

[Benchmarking](README.md) · [Collected and fitted surfaces](../../studies/error-surface/quadratic-fits.md)

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
hypothesis-helm-benchmark error-surface --plot-only --output studies/error-surface
```

The polynomial follows the two-factor quadratic form described in the
[NIST/SEMATECH handbook: Response surface designs](https://www.itl.nist.gov/div898/handbook/pri/section3/pri336.htm).
Our measurement design is a full grid of the chosen factor settings, not a central
composite or Box-Behnken design. Choosing a quadratic model does not change that design.

## Quadratic versus quartic comparison

The separate `polynomial-surface` analysis keeps the existing quadratic figures and measurements.
It compares a six-coefficient quadratic with a fifteen-coefficient quartic:

```text
prediction(u, v) = sum(b[i,j] * u**i * v**j for i+j <= degree)
degree = 2 (quadratic) or 4 (quartic)
```

Both models include interactions and can have diagonal axes. Degree four adds cubic and quartic
terms, allowing two isolated peaks separated by a valley. It also has more freedom to overfit;
a closer fit to training observations does not establish better prediction.

Before fitting either model, we reserve 25% of factor settings (rounding up, keeping the four corners
in training) and the last repeat. Both models use exactly the same remaining cell means.
The report separately scores withheld settings, the withheld repeat at training settings, and
settings withheld in that repeat. The last group tests both kinds of generalization together.
No held-out observations select coefficients or tune the model. Scores are descriptive results
for these measurements and this split, not guarantees for other charts.

A quartic needs more than 15 training cells and a full-rank design matrix. It needs at least five
distinct settings along each axis; that alone does not guarantee rank after withholding cells.
The original quick study has only three clustering settings, so its quartic is explicitly unavailable.
We do not interpolate new training observations or silently substitute a different polynomial.

```sh
hypothesis-helm-benchmark polynomial-surface --input studies/error-surface/results.json
```

For a completed higher-resolution run, replace the input with that run's `results.json`.
PNG/SVG comparisons, coefficients, exact splits and RMSE/R² scores go into a separate
`polynomial-comparison/` directory beside the source. Use `--output` to keep multiple comparisons
and `--seed` to change the reproducible holdout. The command returns 1 when a model is unavailable,
while still saving the available results and reasons. Neither Helm nor PySR is run by this command.

[Original quick study: sparse-grid limitations](../../studies/error-surface/polynomial-comparison/README.md)

[Additional 5×5 comparison](../../studies/error-surface-quartic/polynomial-comparison/README.md)
uses eight input fields, combined filtering, two repeats and 50 completed runs.
The original quick study and its fitted results remain unchanged.

## Optional symbolic regression

[PySR](https://github.com/astroautomata/PySR) searches for an equation as well as its coefficients.
It is an optional benchmark dependency; ordinary chart testing does not import it or Julia.
Install it with `pip install 'hypothesis-helm[symbolic]'`.

To compare models using existing measurements only:

```sh
hypothesis-helm-benchmark symbolic-surface --input studies/error-surface/results.json --iterations 20 --fit-timeout 15
```

Results go to `symbolic/` beside the measurement file, or to `--output DIR`.
`--methods filter filter-adaptive` restricts the comparison. The source ledger is not rewritten.
For a combined plot refresh, add `--symbolic-fit` to `error-surface --plot-only`.
Future full refreshes opt in with `BENCHMARK_SYMBOLIC_FIT=true`; the extra must be installed first.

Both models receive identical training cell means. We reserve the last repeat before computing those means,
then reserve 25% of factor cells (rounded upward), keeping all four corners in training so the factor bounds stay fixed.
The report scores three separate groups: unseen cells on training repeats, the unseen repeat at training cells,
and the joint holdout of both. The seed controls the cell split. At least two complete repeats and an identifiable
quadratic training design are required; censored or incomplete surfaces are not fitted.
With only two repeats, this provides one held-out seed, not a reliable estimate of variation across many seeds.

The initial search permits `+`, `-`, `*`, `/`, `square`, and `exp`. It defaults to 40 iterations and a maximum
expression complexity of 20 (`--iterations`, `--max-size`). PySR chooses an expression using its `best` criterion
on training data; holdouts do not select the equation, tune parameters or change runtime filtering.
This is a candidate empirical explanation, not an automatic replacement for the quadratic or a pruning guarantee.
Repeatedly tuning against these same holdouts would invalidate their role as independent evaluation data.

Search is serial and seeded (`--seed`, default 2026). `--fit-timeout` defaults to 60 seconds per model;
Julia installation, compilation and initialization are additional costs. Time-limited searches may stop at
different iterations across machines, so the time limit prevents a promise of identical fitted equations.
Backend scratch files are temporary. Published JSON retains versions, source checksum, splits, expressions,
coefficients, predictions and RMSE/R² scores. Predictions remain unclipped to expose invalid approximations.

The comparison plots show the reserved repeat beside each model's predictions on the same discrete settings.
A smoother or more complex expression is useful only if its held-out errors improve.
See the [PySR API](https://ai.damtp.cam.ac.uk/pysr/v1.5.9/api.html) for search complexity, model selection and determinism.

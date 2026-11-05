# Fitted response surfaces

<!-- toc:start -->
**Table of contents**

- [clustering: combined, Total runtime (seconds)](#clustering-combined-total-runtime-seconds)
- [clustering: combined, Erroneous inputs missed](#clustering-combined-erroneous-inputs-missed)
<!-- toc:end -->

[Measurements](README.md) · [Model definition](<../../docs/benchmarking/response-surface.md>)

Quadratics fitted to collected cell means, separately for each method and response. Coefficients are not theoretical predictions.
Only cells with every requested repeat completed enter the fit. Missing or timed-out cells remain blank.
A fit requires a complete rectangular grid and more than six identifiable cells; otherwise its reason is recorded below.
Mean ±1 sample SD labels describe seed variation, not confidence intervals. Residuals are observed minus fitted cell means.
Continuous predictions between discrete settings describe the model, not additional Helm measurements.
Negative predictions remain visible; neither nonnegative runtime nor bounded error counts are enforced by this polynomial.
RMSE and R² measure agreement with the training cells, not performance on unseen charts. No global worst-case claim is made.

Coefficients, bounds and diagnostics (local run data)

## clustering: combined, Total runtime (seconds)

RMSE: 0.02501; R²: 0.224; cells: 25.

![Collected and fitted surfaces with residuals](quadratic-clustering-combined-total-seconds.png)

## clustering: combined, Erroneous inputs missed

RMSE: 0.3798; R²: 1.000; cells: 25.

![Collected and fitted surfaces with residuals](quadratic-clustering-combined-errors-missed.png)


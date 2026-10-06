# Fitted response surfaces

<!-- toc:start -->
<details>
<summary>Table of contents</summary>

- [clustering: default, Total runtime (seconds)](#clustering-default-total-runtime-seconds)
- [clustering: default, Erroneous inputs missed](#clustering-default-erroneous-inputs-missed)
- [clustering: exact-equivalence, Total runtime (seconds)](#clustering-exact-equivalence-total-runtime-seconds)
- [clustering: exact-equivalence, Erroneous inputs missed](#clustering-exact-equivalence-erroneous-inputs-missed)
- [clustering: random, Total runtime (seconds)](#clustering-random-total-runtime-seconds)
- [clustering: random, Erroneous inputs missed](#clustering-random-erroneous-inputs-missed)
- [clustering: topology, Total runtime (seconds)](#clustering-topology-total-runtime-seconds)
- [clustering: topology, Erroneous inputs missed](#clustering-topology-erroneous-inputs-missed)
- [clustering: combined, Total runtime (seconds)](#clustering-combined-total-runtime-seconds)
- [clustering: combined, Erroneous inputs missed](#clustering-combined-erroneous-inputs-missed)
- [clustering: filter, Total runtime (seconds)](#clustering-filter-total-runtime-seconds)
- [clustering: filter, Erroneous inputs missed](#clustering-filter-erroneous-inputs-missed)
- [clustering: filter-adaptive, Total runtime (seconds)](#clustering-filter-adaptive-total-runtime-seconds)
- [clustering: filter-adaptive, Erroneous inputs missed](#clustering-filter-adaptive-erroneous-inputs-missed)
- [clustering: sample-random, Total runtime (seconds)](#clustering-sample-random-total-runtime-seconds)
- [clustering: sample-random, Erroneous inputs missed](#clustering-sample-random-erroneous-inputs-missed)
- [depth: default, Total runtime (seconds)](#depth-default-total-runtime-seconds)
- [depth: default, Erroneous inputs missed](#depth-default-erroneous-inputs-missed)
- [depth: exact-equivalence, Total runtime (seconds)](#depth-exact-equivalence-total-runtime-seconds)
- [depth: exact-equivalence, Erroneous inputs missed](#depth-exact-equivalence-erroneous-inputs-missed)
- [depth: random, Total runtime (seconds)](#depth-random-total-runtime-seconds)
- [depth: random, Erroneous inputs missed](#depth-random-erroneous-inputs-missed)
- [depth: topology, Total runtime (seconds)](#depth-topology-total-runtime-seconds)
- [depth: topology, Erroneous inputs missed](#depth-topology-erroneous-inputs-missed)
- [depth: combined, Total runtime (seconds)](#depth-combined-total-runtime-seconds)
- [depth: combined, Erroneous inputs missed](#depth-combined-erroneous-inputs-missed)
- [depth: filter, Total runtime (seconds)](#depth-filter-total-runtime-seconds)
- [depth: filter, Erroneous inputs missed](#depth-filter-erroneous-inputs-missed)
- [depth: filter-adaptive, Total runtime (seconds)](#depth-filter-adaptive-total-runtime-seconds)
- [depth: filter-adaptive, Erroneous inputs missed](#depth-filter-adaptive-erroneous-inputs-missed)
- [depth: sample-random, Total runtime (seconds)](#depth-sample-random-total-runtime-seconds)
- [depth: sample-random, Erroneous inputs missed](#depth-sample-random-erroneous-inputs-missed)
- [redundancy: default, Total runtime (seconds)](#redundancy-default-total-runtime-seconds)
- [redundancy: default, Erroneous inputs missed](#redundancy-default-erroneous-inputs-missed)
- [redundancy: exact-equivalence, Total runtime (seconds)](#redundancy-exact-equivalence-total-runtime-seconds)
- [redundancy: exact-equivalence, Erroneous inputs missed](#redundancy-exact-equivalence-erroneous-inputs-missed)
- [redundancy: random, Total runtime (seconds)](#redundancy-random-total-runtime-seconds)
- [redundancy: random, Erroneous inputs missed](#redundancy-random-erroneous-inputs-missed)
- [redundancy: topology, Total runtime (seconds)](#redundancy-topology-total-runtime-seconds)
- [redundancy: topology, Erroneous inputs missed](#redundancy-topology-erroneous-inputs-missed)
- [redundancy: combined, Total runtime (seconds)](#redundancy-combined-total-runtime-seconds)
- [redundancy: combined, Erroneous inputs missed](#redundancy-combined-erroneous-inputs-missed)
- [redundancy: filter, Total runtime (seconds)](#redundancy-filter-total-runtime-seconds)
- [redundancy: filter, Erroneous inputs missed](#redundancy-filter-erroneous-inputs-missed)
- [redundancy: filter-adaptive, Total runtime (seconds)](#redundancy-filter-adaptive-total-runtime-seconds)
- [redundancy: filter-adaptive, Erroneous inputs missed](#redundancy-filter-adaptive-erroneous-inputs-missed)
- [redundancy: sample-random, Total runtime (seconds)](#redundancy-sample-random-total-runtime-seconds)
- [redundancy: sample-random, Erroneous inputs missed](#redundancy-sample-random-erroneous-inputs-missed)

</details>
<!-- toc:end -->

[Measurements](<README.md>) · [Model definition](../../docs/benchmarking/response-surface.md)

Quadratics fitted to collected cell means, separately for each method and response. Coefficients are not theoretical predictions.
Only cells with every requested repeat completed enter the fit. Missing or timed-out cells remain blank.
A fit requires a complete rectangular grid and more than six identifiable cells; otherwise its reason is recorded below.
Mean ±1 sample SD labels describe seed variation, not confidence intervals. Residuals are observed minus fitted cell means.
Continuous predictions between discrete settings describe the model, not additional Helm measurements.
Negative predictions remain visible; neither nonnegative runtime nor bounded error counts are enforced by this polynomial.
RMSE and R² measure agreement with the training cells, not performance on unseen charts. No global worst-case claim is made.

Coefficients, bounds and diagnostics (local run data)

## clustering: default, Total runtime (seconds)

RMSE: 0.3627; R²: 0.003; cells: 143.

![Collected and fitted surfaces with residuals](<quadratic-clustering-default-total-seconds.png>)

## clustering: default, Erroneous inputs missed

RMSE: 0; R²: N/A (constant observations); cells: 143.

![Collected and fitted surfaces with residuals](<quadratic-clustering-default-errors-missed.png>)

## clustering: exact-equivalence, Total runtime (seconds)

RMSE: 0.05756; R²: 0.006; cells: 143.

![Collected and fitted surfaces with residuals](<quadratic-clustering-exact-equivalence-total-seconds.png>)

## clustering: exact-equivalence, Erroneous inputs missed

RMSE: 0; R²: N/A (constant observations); cells: 143.

![Collected and fitted surfaces with residuals](<quadratic-clustering-exact-equivalence-errors-missed.png>)

## clustering: random, Total runtime (seconds)

RMSE: 0.02759; R²: 0.003; cells: 143.

![Collected and fitted surfaces with residuals](<quadratic-clustering-random-total-seconds.png>)

## clustering: random, Erroneous inputs missed

RMSE: 0.4667; R²: 1.000; cells: 143.

![Collected and fitted surfaces with residuals](<quadratic-clustering-random-errors-missed.png>)

## clustering: topology, Total runtime (seconds)

RMSE: 0.02754; R²: 0.010; cells: 143.

![Collected and fitted surfaces with residuals](<quadratic-clustering-topology-total-seconds.png>)

## clustering: topology, Erroneous inputs missed

RMSE: 0.6966; R²: 1.000; cells: 143.

![Collected and fitted surfaces with residuals](<quadratic-clustering-topology-errors-missed.png>)

## clustering: combined, Total runtime (seconds)

RMSE: 0.01194; R²: 0.002; cells: 143.

![Collected and fitted surfaces with residuals](<quadratic-clustering-combined-total-seconds.png>)

## clustering: combined, Erroneous inputs missed

RMSE: 0.4346; R²: 1.000; cells: 143.

![Collected and fitted surfaces with residuals](<quadratic-clustering-combined-errors-missed.png>)

## clustering: filter, Total runtime (seconds)

RMSE: 0.5773; R²: 0.960; cells: 143.

![Collected and fitted surfaces with residuals](<quadratic-clustering-filter-total-seconds.png>)

## clustering: filter, Erroneous inputs missed

RMSE: 5.492; R²: 0.423; cells: 143.

![Collected and fitted surfaces with residuals](<quadratic-clustering-filter-errors-missed.png>)

## clustering: filter-adaptive, Total runtime (seconds)

RMSE: 0.5859; R²: 0.958; cells: 143.

![Collected and fitted surfaces with residuals](<quadratic-clustering-filter-adaptive-total-seconds.png>)

## clustering: filter-adaptive, Erroneous inputs missed

RMSE: 5.492; R²: 0.423; cells: 143.

![Collected and fitted surfaces with residuals](<quadratic-clustering-filter-adaptive-errors-missed.png>)

## clustering: sample-random, Total runtime (seconds)

RMSE: 0.2492; R²: 0.013; cells: 143.

![Collected and fitted surfaces with residuals](<quadratic-clustering-sample-random-total-seconds.png>)

## clustering: sample-random, Erroneous inputs missed

RMSE: 0.7721; R²: 0.999; cells: 143.

![Collected and fitted surfaces with residuals](<quadratic-clustering-sample-random-errors-missed.png>)

## depth: default, Total runtime (seconds)

RMSE: 0.357; R²: 0.061; cells: 78.

![Collected and fitted surfaces with residuals](<quadratic-depth-default-total-seconds.png>)

## depth: default, Erroneous inputs missed

RMSE: 0; R²: N/A (constant observations); cells: 78.

![Collected and fitted surfaces with residuals](<quadratic-depth-default-errors-missed.png>)

## depth: exact-equivalence, Total runtime (seconds)

RMSE: 0.06595; R²: 0.895; cells: 78.

![Collected and fitted surfaces with residuals](<quadratic-depth-exact-equivalence-total-seconds.png>)

## depth: exact-equivalence, Erroneous inputs missed

RMSE: 0; R²: N/A (constant observations); cells: 78.

![Collected and fitted surfaces with residuals](<quadratic-depth-exact-equivalence-errors-missed.png>)

## depth: random, Total runtime (seconds)

RMSE: 0.02814; R²: 0.067; cells: 78.

![Collected and fitted surfaces with residuals](<quadratic-depth-random-total-seconds.png>)

## depth: random, Erroneous inputs missed

RMSE: 0.4334; R²: 1.000; cells: 78.

![Collected and fitted surfaces with residuals](<quadratic-depth-random-errors-missed.png>)

## depth: topology, Total runtime (seconds)

RMSE: 0.04068; R²: 0.921; cells: 78.

![Collected and fitted surfaces with residuals](<quadratic-depth-topology-total-seconds.png>)

## depth: topology, Erroneous inputs missed

RMSE: 0.9745; R²: 1.000; cells: 78.

![Collected and fitted surfaces with residuals](<quadratic-depth-topology-errors-missed.png>)

## depth: combined, Total runtime (seconds)

RMSE: 0.02808; R²: 0.983; cells: 78.

![Collected and fitted surfaces with residuals](<quadratic-depth-combined-total-seconds.png>)

## depth: combined, Erroneous inputs missed

RMSE: 0.8124; R²: 1.000; cells: 78.

![Collected and fitted surfaces with residuals](<quadratic-depth-combined-errors-missed.png>)

## depth: filter, Total runtime (seconds)

RMSE: 0.5196; R²: 0.965; cells: 78.

![Collected and fitted surfaces with residuals](<quadratic-depth-filter-total-seconds.png>)

## depth: filter, Erroneous inputs missed

RMSE: 7.686; R²: 0.785; cells: 78.

![Collected and fitted surfaces with residuals](<quadratic-depth-filter-errors-missed.png>)

## depth: filter-adaptive, Total runtime (seconds)

RMSE: 0.5187; R²: 0.965; cells: 78.

![Collected and fitted surfaces with residuals](<quadratic-depth-filter-adaptive-total-seconds.png>)

## depth: filter-adaptive, Erroneous inputs missed

RMSE: 7.686; R²: 0.785; cells: 78.

![Collected and fitted surfaces with residuals](<quadratic-depth-filter-adaptive-errors-missed.png>)

## depth: sample-random, Total runtime (seconds)

RMSE: 0.2504; R²: 0.061; cells: 78.

![Collected and fitted surfaces with residuals](<quadratic-depth-sample-random-total-seconds.png>)

## depth: sample-random, Erroneous inputs missed

RMSE: 1.164; R²: 0.998; cells: 78.

![Collected and fitted surfaces with residuals](<quadratic-depth-sample-random-errors-missed.png>)

## redundancy: default, Total runtime (seconds)

RMSE: 0.3918; R²: 0.124; cells: 104.

![Collected and fitted surfaces with residuals](<quadratic-redundancy-default-total-seconds.png>)

## redundancy: default, Erroneous inputs missed

RMSE: 0; R²: N/A (constant observations); cells: 104.

![Collected and fitted surfaces with residuals](<quadratic-redundancy-default-errors-missed.png>)

## redundancy: exact-equivalence, Total runtime (seconds)

RMSE: 0.5565; R²: 0.960; cells: 104.

![Collected and fitted surfaces with residuals](<quadratic-redundancy-exact-equivalence-total-seconds.png>)

## redundancy: exact-equivalence, Erroneous inputs missed

RMSE: 0; R²: N/A (constant observations); cells: 104.

![Collected and fitted surfaces with residuals](<quadratic-redundancy-exact-equivalence-errors-missed.png>)

## redundancy: random, Total runtime (seconds)

RMSE: 0.02924; R²: 0.132; cells: 104.

![Collected and fitted surfaces with residuals](<quadratic-redundancy-random-total-seconds.png>)

## redundancy: random, Erroneous inputs missed

RMSE: 0.4334; R²: 1.000; cells: 104.

![Collected and fitted surfaces with residuals](<quadratic-redundancy-random-errors-missed.png>)

## redundancy: topology, Total runtime (seconds)

RMSE: 0.562; R²: 0.956; cells: 104.

![Collected and fitted surfaces with residuals](<quadratic-redundancy-topology-total-seconds.png>)

## redundancy: topology, Erroneous inputs missed

RMSE: 16.86; R²: 0.951; cells: 104.

![Collected and fitted surfaces with residuals](<quadratic-redundancy-topology-errors-missed.png>)

## redundancy: combined, Total runtime (seconds)

RMSE: 0.5525; R²: 0.960; cells: 104.

![Collected and fitted surfaces with residuals](<quadratic-redundancy-combined-total-seconds.png>)

## redundancy: combined, Erroneous inputs missed

RMSE: 16.13; R²: 0.958; cells: 104.

![Collected and fitted surfaces with residuals](<quadratic-redundancy-combined-errors-missed.png>)

## redundancy: filter, Total runtime (seconds)

RMSE: 1.002; R²: 0.873; cells: 104.

![Collected and fitted surfaces with residuals](<quadratic-redundancy-filter-total-seconds.png>)

## redundancy: filter, Erroneous inputs missed

RMSE: 10.88; R²: 0.650; cells: 104.

![Collected and fitted surfaces with residuals](<quadratic-redundancy-filter-errors-missed.png>)

## redundancy: filter-adaptive, Total runtime (seconds)

RMSE: 1.016; R²: 0.874; cells: 104.

![Collected and fitted surfaces with residuals](<quadratic-redundancy-filter-adaptive-total-seconds.png>)

## redundancy: filter-adaptive, Erroneous inputs missed

RMSE: 10.88; R²: 0.650; cells: 104.

![Collected and fitted surfaces with residuals](<quadratic-redundancy-filter-adaptive-errors-missed.png>)

## redundancy: sample-random, Total runtime (seconds)

RMSE: 0.274; R²: 0.139; cells: 104.

![Collected and fitted surfaces with residuals](<quadratic-redundancy-sample-random-total-seconds.png>)

## redundancy: sample-random, Erroneous inputs missed

RMSE: 1.164; R²: 0.998; cells: 104.

![Collected and fitted surfaces with residuals](<quadratic-redundancy-sample-random-errors-missed.png>)


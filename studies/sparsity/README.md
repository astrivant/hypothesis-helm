# Sparsity and Stochasticity

<!-- toc:start -->
**Table of contents**

- [Fresh measurements](#fresh-measurements)
<!-- toc:end -->

[Benchmarking](<../../docs/benchmarking/README.md>)

This study varies case count, not `--permutations` interaction strength. It measures
outcome coverage and distribution error; see the main benchmark for bug discovery.

~~~sh
hypothesis-helm-benchmark \
  --parameters pkg/hypothesis_helm_benchmarking/assets/fixture/parameters/standard.yaml \
  sparsity --count 32768 --retain 0.25 --levels 8 --time-limit 9m --output .cache/benchmarks/sparsity
~~~

Each run uses a nested random subset, fresh caches, and a nine-minute budget.
Received frequencies are compared with the chart's exact finite distribution.
This is one seeded trajectory; distribution errors can fluctuate.
Raw results (local run data) retain counts and run details.

![Outcome coverage and distribution error](sparsity-quality.png)

![Received distributions as case counts decrease](sparsity-distributions.png)

The application exposes this tradeoff through `--filter-random N` (default `0`): each step
retains 25% of non-default planned cases, rounded upward. See [filtering](<../../docs/execution/README.md#optional-filtering>).
This fixture's distribution coverage does not establish a generally safe filter
level for bug discovery; rare faults can be lost when cases are omitted.

## Fresh measurements

| Stage | Inputs checked / assigned | Helm renders | Scalar coverage | Total variation | Maximum CDF error | Seconds |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 32,768 / 32,768 | 256 | 100.00% | 0.00000 | 0.00000 | 138.99 |
| 2 | 8,192 / 8,192 | 256 | 100.00% | 0.06726 | 0.01123 | 41.47 |
| 3 | 2,048 / 2,048 | 256 | 100.00% | 0.14258 | 0.01807 | 17.87 |
| 4 | 512 / 512 | 220 | 85.94% | 0.27930 | 0.03711 | 10.98 |
| 5 | 128 / 128 | 107 | 41.80% | 0.58203 | 0.05078 | 5.10 |
| 6 | 32 / 32 | 31 | 12.11% | 0.87891 | 0.12891 | 2.29 |
| 7 | 8 / 8 | 8 | 3.12% | 0.96875 | 0.29297 | 0.60 |
| 8 | 2 / 2 | 2 | 0.78% | 0.99219 | 0.46094 | 0.23 |

CSV measurements (local run data)

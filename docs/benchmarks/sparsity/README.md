# Sparsity and Stochasticity

[Benchmarking](../README.md)

This study varies case count, not `--permutations` interaction strength. It measures
outcome coverage and distribution error; see the main benchmark for bug discovery.

~~~sh
hypothesis-helm-benchmark sparsity \
  --count 32768 --retain 0.25 --levels 8 --output reports/sparsity
~~~

Each run uses a nested random subset, fresh caches, and a three-minute budget.
Received frequencies are compared with the chart's exact finite distribution.
This is one seeded trajectory; distribution errors can fluctuate.
[Raw results](results.json) retain counts and run details.

![Outcome coverage and distribution error](sparsity-quality.png)

![Received distributions as case counts decrease](sparsity-distributions.png)

The application exposes this tradeoff through `--trim-random N` (default `0`): each step
retains 25% of non-default planned cases, rounded upward. See [trimming](../../execution/README.md#optional-trimming).
This fixture's distribution coverage does not establish a generally safe trim
level for bug discovery; rare faults can be lost when cases are omitted.

# Benchmarking

[Documentation](../README.md) · [Project](../../README.md)

## Install and run

```sh
pip install "hypothesis-helm[benchmarking]"
hypothesis-helm-benchmark generate --output benchmark-chart --input-complexity 10
hypothesis-helm-benchmark run --chart benchmark-chart --time-limit 9m
```

The extra installs NumPy and Matplotlib. Helm 4 must be available on `PATH` for
rendering. All benchmark commands run from the installed package; no checkout is
needed. Results default to `reports/benchmarks/` under the working directory.

Use `hypothesis-helm-benchmark --help` to list studies, or append `--help` to a
study such as `hypothesis-helm-benchmark nesting --help`.

Render an exported compiler dependency graph with Matplotlib:

```sh
hypothesis-helm-benchmark topology --graph topology.json --output reports/topology
```

The PNG/SVG plots retain all vertices and directed edges. See
[graph invariants and layout semantics](../inputs/README.md#render-the-mathematical-graph).
Browse the [synthetic and real-chart topology catalog](chart-topologies/README.md)
for complete graphs, per-chart measurements, and downloadable graph data.

## Local shard wrapper

Run saved suites with 1–4 local GNU Parallel shards:

~~~sh
brew bundle # macOS; Debian/Ubuntu: sudo apt-get install parallel
for shards in 1 2 3 4; do
  bash scripts/benchmark-shards.sh --shards "$shards" examples/generated-workload
done
~~~

The [wrapper](../../scripts/benchmark-shards.sh) launches `helm hypothesis run` with one
worker per shard and caching disabled. Logs and reports go to
`reports/local-shards/`. Pass additional run options after `--`.

Generate a chart with predictable, rounded normal-distribution outputs:

~~~sh
hypothesis-helm-benchmark generate \
  --output .cache/benchmark-chart \
  --input-complexity 100 --mean 0 --stddev 1 --output-bins 256
~~~

Run the [plotting benchmark](../../pkg/hypothesis_helm/benchmarking/benchmark_helm.py):

~~~sh
hypothesis-helm-benchmark run \
  --chart .cache/benchmark-chart --step 50 --time-limit 9m --max-permutations 600000 \
  --shards 1,2,3,4 --shard none --output reports/benchmark
~~~

Checkpoints increase by **50, 100, 150, …** inputs. Each trajectory or scaling run
has a nine-minute execution budget; the complete study takes longer. Outputs are
checked against an independent oracle, and exact-equivalent renders are skipped.
Use each script's `--help` for options.

The figures below use local Python workers and the [standard chart](standard-chart).
In this Helm 4 run, pruning completed **169,070 checks with 256 renders**, compared
with **11,831 checks** without pruning, within each nine-minute budget.
[Raw measurements](results.json), [CSV](results.csv), and
[refresh provenance](refresh/README.md) include the host and run details.
These are single-run measurements; they do not establish timing variability.

Progressive checkpoints share one execution. Dashed tails mark unfinished targets
at the deadline.

![Measured permutation runtime and completed-work plateau](progressive.png)

![Observed Helm values and expected normal distribution](output-distribution.png)

**Strong scaling** keeps total work fixed. **Weak scaling** keeps work per worker fixed.

![Strong scaling against permutation count and worker replicas](strong-scaling.png)

![Weak scaling against permutation count and worker replicas](weak-scaling.png)

![Parallel replica throughput and render skips](replicas.png)

## Bug discovery by permutation strength

Compare pairs, triples, and higher-order coverage against known chart faults:

~~~sh
hypothesis-helm-benchmark generate \
  --output .cache/faulty-chart --input-complexity 8 \
  --bug-percent 5 --bug-orders 2,3,4,5,6 --bug-seed 2026
hypothesis-helm-benchmark discovery \
  --chart .cache/faulty-chart --max-strength 6 --output reports/discovery
~~~

`--bug-percent` selects that percentage of path-subset/value-pattern assignments at
each order, rounded down. The seed fixes their random placement; `benchmark.json`
records exact counts. Trigger overlap means this is not the percentage of complete
configurations that fail. `--max-bugs` bounds fixture size.

The x-axis is `--permutations` interaction strength. The chart, its 256 possible
configurations, and its injected faults stay fixed. Runs use the application's
planner and real Helm renders, with automatic enumeration and inferred groups
disabled to isolate strength. [Raw results](bug-density/results.json) retain the
first failing case for each fault. These discovery rates describe the seeded fixture.

The recorded 5% fixture contains 261 faults: pairs found 136, triples found 208,
and strength five found all 261.

![Known bugs discovered as permutation strength increases](bug-density/bug-discovery.png)

![Discovery rate by fault interaction order](bug-density/bug-order.png)

The separate [Sparsity and Stochasticity study](sparsity/README.md) measures distribution
coverage as the number of cases falls.

## Topology fixture

Generate the normal-quantile chart with downstream interactions:

```sh
hypothesis-helm-benchmark generate \
  --output .cache/topology-chart --input-complexity 100 --topology
```

`--topology` uses six additional input bits for resource gates, shared Service/Ingress
ports, replica thresholds, and a nested rare branch. `--topology-opaque` adds a loop
to test conservative fallback. Both retain the normal quantile projection; the
benchmark runner checks the added projections against an independent oracle.
Fault injection (`--bug-percent`, `--bug-orders`, `--bug-seed`) remains available.

The [small fixture](../../examples/topology-benchmark) has 1,024 possible inputs for
complete comparisons. See [sampling controls and complexity](../execution/README.md#optional-trimming).

```sh
hypothesis-helm-benchmark sparsity \
  --chart examples/topology-benchmark --count 1024 --levels 5 \
  --output reports/topology-sparsity
```

Raw results include `topology_counts` and `topology_quality` (categorical outcome
coverage and total variation), alongside scalar-distribution statistics. No CDF
error is assigned to unordered topology outcomes.

## Strategy matrix

[Compare strategies across six structural cases](matrix/README.md).
The matrix uses fully enumerable fixtures to measure exact outcome coverage,
with a nine-minute execution ceiling for each independent run.

```sh
hypothesis-helm-benchmark matrix \
  --input-complexity 10 --trim-level 2 --seed 2026 --time-limit 9m \
  --output reports/strategy-matrix
```

Use `--structure constraints|control-flow|dependencies|interactions|equivalence|boundaries`
with the chart generator to create an individual case. Boundary profiles include
an integer input; the matrix harness enumerates their declared domains rather
than assuming every parameter is Boolean.

## Output-space PCA

[Before and after trimming, with 5% seeded errors](pca/README.md).
Compare random trimming, topology trimming, and both across the six structural
cases. Each category keeps fixed PCA axes and reports exact error recall and
output coverage alongside the projection.

```sh
hypothesis-helm-benchmark pca \
  --input-complexity 10 --error-percent 5 --trim-level 2 \
  --time-limit 9m --output reports/pca
```

## Failure expansion

[Compare each strategy with and without `--expand-failures`](expansion/README.md).
The paired matrix separates distinct erroneous outputs from erroneous inputs
exercised, and records the additional physical renders.

```sh
hypothesis-helm-benchmark expansion \
  --input-complexity 10 --error-percent 5 --trim-level 2 \
  --time-limit 9m --output reports/expansion
```

## Topology distributions and trim depth

[Generate mixed topology fixtures](topology-mixtures/README.md) with seeded category
weights and shared input wiring. [Compare trim depths 0–5](topology-depth/README.md)
with random trimming disabled and failure expansion enabled.

## Chart nesting at permutation strength eight

[Matrix and shared-frame PCA](nesting/README.md) compare shallow (1), deep (5),
and seeded random nesting depths (1–5). `--permutations 8` stays fixed; each
chart retains 12 topology components. Shared PCA axes make depth profiles
comparable within each topology family.

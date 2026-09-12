# Benchmarking

[Documentation](../README.md) · [Project](../../README.md)

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
bash scripts/project-python.sh -m scripts.generate_benchmark_chart \
  --output .cache/benchmark-chart \
  --input-complexity 100 --mean 0 --stddev 1 --output-bins 256
~~~

Run the [plotting benchmark](../../scripts/benchmark_helm.py):

~~~sh
bash scripts/project-python.sh -m scripts.benchmark_helm \
  --chart .cache/benchmark-chart --step 50 --time-limit 3m \
  --shards 1,2,3,4 --shard none --output reports/benchmark
~~~

Checkpoints increase by **50, 100, 150, …** inputs. Each trajectory or scaling run
has a three-minute execution budget; the complete study takes longer. Outputs are
checked against an independent oracle, and exact-equivalent renders are skipped.
Use each script's `--help` for options.

The figures below use local Python workers and the [standard chart](../../examples/benchmark).
In one recorded run, pruning completed **49,733 checks with 256 renders**, compared
with **3,535 checks** without pruning. [Raw measurements](results.json)
and [CSV](results.csv) include the host and run details.

Progressive checkpoints share one execution. Dashed tails mark unfinished targets
at the deadline.

![Measured permutation runtime and completed-work plateau](progressive.png)

![Observed Helm values and expected normal distribution](output-distribution.png)

**Strong scaling** keeps total work fixed. **Weak scaling** keeps work per worker fixed.

![Strong scaling against permutation count and worker replicas](strong-scaling.png)

![Weak scaling against permutation count and worker replicas](weak-scaling.png)

![Parallel replica throughput and render skips](replicas.png)

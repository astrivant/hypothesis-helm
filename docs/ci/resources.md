# Starting CI resources

[Recommended workflow](README.md#recommended-workflow)

Start with **two path workers on MR/PR jobs**, **four on main**, and **six for large
dependency-heavy charts**. Reserve at least as many vCPUs as workers. The workflow
table budgets roughly 2 GiB per vCPU for path testing for the Python workers, Helm children, coordinator
and CI overhead. This is an initial allocation to tune, not a measured requirement.

## What the Bitnami data tells us

Across **115 pinned Bitnami charts**, the supplied `values.yaml` files contain a
median of **320 distinct key paths**. At least 90% contain **1,007 or fewer**; the
largest contains **1,497**. Containers and their nested keys are counted separately.
These counts describe the supplied files, before dependencies and template-only
fields are added.<sup>[\[1\]](../../benchmarks/studies/resource-sizing/README.md)</sup>

Actual discovery can produce a much larger queue: the current Airflow run selected
**2,754 paths**. At ten examples per path, that allows up to 27,540 generated examples
before shrinking or other checks. Some finite path domains finish with fewer examples.
A five-minute timeout does not promise completion of that queue.

Fifteen process-tree samples during that six-worker run observed at most **633 MiB
of summed resident memory**. This includes the coordinator and descendants present
at each sample. It is a short macOS observation, not peak Linux memory usage, and
does not establish requirements for other charts or Kubernetes schema validators.
The suggested RAM allocations deliberately leave room beyond that observation.

## Workers and shards do different jobs

- **Local workers** share the current chart's path queue and one chart deadline.
  `--jobs 4` runs up to four path properties concurrently, then moves to the next chart.
- **CI shards** are separate CI jobs, each with its own CPU and RAM allocation.
  The new repository path queue does not support distributed sharding. Use one CI job
  for the filtered recursive test/scan commands in the workflow table.
- **Generated pytest suites** support `--shard` and report aggregation. If a measured
  suite misses its target duration, try two shards before increasing further. Two
  shards with four local workers each need two runners: eight vCPUs and 16 GiB in
  total at the main-branch allocation. They do not share a global chart deadline.
- **Explicit exhaustive testing** currently runs serially and cannot be sharded.
  Finite interaction plans also remain serial. More CPU cores do not remove
  finite-domain or execution-budget limits.

The [sharded CI examples](README.md#gitlab) use the generated-suite workflow.
Do not add their shard settings to a filtered repository queue and assume the work
will be partitioned. Disable automatic shard detection with `--shard none` when
using local recursive `test` inside an existing CI matrix.

## Adjust after the first run

Use completed paths and elapsed testing time to compare two, four and six workers
on the same chart, seed and example limit. Increase workers when throughput improves;
otherwise keep the smaller runner. Check peak memory on the actual CI runner before
tightening its allocation. No CPU or memory optimum has been measured for these presets.

Start large charts near or above 1,000 supplied paths at six workers on 8 vCPU / 16 GiB,
then adjust using their discovered queue and measured throughput. This threshold is
a practical starting rule based on the inventory's upper tenth, not a complexity law.
Path count alone cannot predict render cost, shrinking work or the size of a finite
permutation space. `--filter-aggressive` also falls back to ordinary filtering when
its calibration does not cover the chart, including the current path-property mode.

Runner labels may provide more resources than these allocations. Check the provider's
[GitHub runner specifications](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
or [GitLab runner specifications](https://docs.gitlab.com/ci/runners/hosted_runners/linux/)
before setting worker counts; two shards on the same constrained host do not double
its available CPU or memory.

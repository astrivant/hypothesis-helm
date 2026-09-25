# Choosing test coverage

<!-- toc:start -->
**Table of contents**

- [Development stages](#development-stages)
- [Release checks](#release-checks)
<!-- toc:end -->

[Documentation](README.md) · [Project](../README.md)

## Development stages

For a single chart, use progressively broader coverage as changes approach a release:

| When | Recommended mode | Starting CPU / RAM per CI job | Local workers | CI shards |
| --- | --- | --- | ---: | ---: |
| MR / PR | `--filter-adaptive` | 2 vCPU / 4 GiB | `--jobs 2` | 1 |
| Changes on `main` | `--filter` | 2 vCPU / 4 GiB | `--jobs 2` | 1 |
| Before tagging a release | `--exhaustive` | 4 vCPU / 8 GiB | `--jobs 4` | 1 |

Use these starting allocations to collect measurements for your workload.
Use one CI job per chart: two workers for filtered checks, or four workers for exhaustive release checks.
Apply the same starting allocations to dependency-heavy charts, then adjust using measured throughput.
Exhaustive testing parallelizes within that job; it cannot split one chart across CI shards.
Exhaustive runs launch concurrent Helm processes; the coordinator validates outputs and writes reports in seeded order.
[Sizing evidence and shard limitations](ci/resources.md) explain how to adjust these estimates.

After installing the plugin, use these commands in the corresponding CI jobs:

```sh
# Merge request / pull request
helm hypothesis test ./chart --filter-adaptive --jobs 2 --chart-timeout 3m --shard none

# Main branch
helm hypothesis test ./chart --filter --jobs 2 --chart-timeout 5m --shard none

# Manual pre-tag check, once per chart with a finite values.schema.json
helm hypothesis test ./chart --exhaustive --jobs 4 --shard none
```

Adaptive sampling falls back to ordinary filtering when the chart has no matching
calibration. Neither filtered mode establishes exhaustive coverage. See the
[adaptive filtering guide](adaptive-filtering/README.md) for the selection policy.

## Release checks

Run the exhaustive check manually on `main` just before tagging a service release.
It checks the accumulated changes on the exact commit you intend to tag. Leave
filter presets, individual case filters and percentage sampling disabled. Explicit exhaustive mode runs
one local chart at a time, with four concurrent Helm processes in this example, and does not support sharding; use a separate job from the
[sharded CI examples](ci/README.md).

The schema must have a supported finite input domain. `--max-cases` bounds enumeration;
`--time-limit` bounds execution. Increase these budgets to fit the chart, and require
completed coverage in the report before tagging. An unsupported domain, a failure or
a timeout does not establish exhaustive coverage. For unbounded domains such as free-form
strings, use a documented finite test domain and state that coverage is limited to it.

The [CI examples](ci/README.md) demonstrate sharded property tests, report aggregation and cache
retention. Their manual triggers do not make them exhaustive. For these cached property
checks, `--rerun all` (`rerun: all` in the action) executes the selected tests again and
refreshes their cache, including failures. The explicit exhaustive command above renders
its configurations afresh. If tagging is automated, require the exhaustive check to finish
successfully before tagging the tested commit; these examples do not create tags.

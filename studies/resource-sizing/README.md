# CI sizing observations

<!-- toc:start -->
**Table of contents**

- [CI sizing observations](#ci-sizing-observations)
<!-- toc:end -->

[Recommended resources](../../docs/ci/resources.md) · [Benchmarking](../../docs/benchmarking/README.md)

These are inventory counts and short process observations, not a resource-scaling benchmark.

| Supplied Bitnami values files | Distinct key paths |
| --- | ---: |
| Median across 115 charts | 320 |
| 90th percentile (nearest rank) | 1,007 |
| Maximum | 1,497 |

Counts include mapping containers and their nested keys. Keys inside repeated list
items use the same wildcard path and are counted once. Dependency expansion and
template-only fields are excluded. Each CSV row records the source file checksum.

[Chart counts and checksums](bitnami-inputs.csv) · [Pinned revision and counting rules](inventory-summary.json)

The [process samples](process-samples.json) record fifteen one-second-spaced observations
during the six-worker Bitnami rerun. The largest observed sum of coordinator and
descendant resident memory was 633.4 MiB. Sampling can miss peaks; summed RSS can
also count shared pages more than once. These macOS observations do not establish
Linux memory requirements, cross-chart limits or ideal worker counts.

The [run configuration](../../docs/reports/bitnami-runs/bitnami-charts_1789389834/run-metadata.json)
records the source and implementation used by the active scan. Suggested resources
remain estimates until repeated CI measurements compare allocations directly.

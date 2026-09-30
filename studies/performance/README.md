# Performance and scaling

<!-- toc:start -->
**Table of contents**

- [Performance and scaling](#performance-and-scaling)
<!-- toc:end -->

[Benchmarking](../../docs/benchmarking/README.md#performance-and-scaling)

Figures below show the measurements available for this run. Deadline-limited work remains incomplete.
Progressive checkpoints share one growing run; unfinished targets are not independent timing observations.
Strong scaling holds total inputs fixed; weak scaling holds inputs per worker fixed. Replicas are local worker processes.

Raw measurements (local run data) · CSV table (local run data)
[Reading variation bands](../../docs/benchmarking/README.md#reading-variation-bands) explains when repeats support deviations.

![Progressive runtime and completed work](<progressive.png>)

![Observed output distribution](<output-distribution.png>)

![Strong scaling](<strong-scaling.png>)

![Weak scaling](<weak-scaling.png>)

![Replica throughput and render skips](<replicas.png>)

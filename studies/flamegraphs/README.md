# Flame graphs

<!-- toc:start -->
**Table of contents**

- [coordinator-2995-784710bcc7f215d7b330a28f8cc46cd5](#coordinator-2995-784710bcc7f215d7b330a28f8cc46cd5)
- [worker-3011-c88285ee576cc4d3e29c9e220882aa47](#worker-3011-c88285ee576cc4d3e29c9e220882aa47)
- [worker-3025-27f7323bedf227eb5fdd39eb2d704805](#worker-3025-27f7323bedf227eb5fdd39eb2d704805)
- [worker-3028-8af8cd0e8d9a2aa388324622051fcf26](#worker-3028-8af8cd0e8d9a2aa388324622051fcf26)
- [worker-3053-cdb84facb7544822f6c112e1a4442ec3](#worker-3053-cdb84facb7544822f6c112e1a4442ec3)
- [worker-3056-98355ba335278ace8883c67c9e54d197](#worker-3056-98355ba335278ace8883c67c9e54d197)
- [workers-combined](#workers-combined)
<!-- toc:end -->

[Benchmarking](../../docs/benchmarking/README.md#flame-graphs-across-worker-cores)

Fresh captures from a separate scaling run with four cases and one or two workers.
Profiling adds overhead, so these captures do not contribute to the uninstrumented timing studies.

Wider boxes mean more time in a function and its children; stacked boxes show who called whom.
Combined workers sum overlapping process time. Helm waits appear under Python callers; Helm internals are not profiled.

Captured 6 profiles across 5 worker processes.
Recording limits and incomplete captures are reported in the capture index (local run data).
Raw captures (local run data) retain the measured stacks for redrawing.

## coordinator-2995-784710bcc7f215d7b330a28f8cc46cd5

![coordinator-2995-784710bcc7f215d7b330a28f8cc46cd5](coordinator-2995-784710bcc7f215d7b330a28f8cc46cd5.png)

[Open zoomable SVG](coordinator-2995-784710bcc7f215d7b330a28f8cc46cd5.svg)

## worker-3011-c88285ee576cc4d3e29c9e220882aa47

![worker-3011-c88285ee576cc4d3e29c9e220882aa47](worker-3011-c88285ee576cc4d3e29c9e220882aa47.png)

[Open zoomable SVG](worker-3011-c88285ee576cc4d3e29c9e220882aa47.svg)

## worker-3025-27f7323bedf227eb5fdd39eb2d704805

![worker-3025-27f7323bedf227eb5fdd39eb2d704805](worker-3025-27f7323bedf227eb5fdd39eb2d704805.png)

[Open zoomable SVG](worker-3025-27f7323bedf227eb5fdd39eb2d704805.svg)

## worker-3028-8af8cd0e8d9a2aa388324622051fcf26

![worker-3028-8af8cd0e8d9a2aa388324622051fcf26](worker-3028-8af8cd0e8d9a2aa388324622051fcf26.png)

[Open zoomable SVG](worker-3028-8af8cd0e8d9a2aa388324622051fcf26.svg)

## worker-3053-cdb84facb7544822f6c112e1a4442ec3

![worker-3053-cdb84facb7544822f6c112e1a4442ec3](worker-3053-cdb84facb7544822f6c112e1a4442ec3.png)

[Open zoomable SVG](worker-3053-cdb84facb7544822f6c112e1a4442ec3.svg)

## worker-3056-98355ba335278ace8883c67c9e54d197

![worker-3056-98355ba335278ace8883c67c9e54d197](worker-3056-98355ba335278ace8883c67c9e54d197.png)

[Open zoomable SVG](worker-3056-98355ba335278ace8883c67c9e54d197.svg)

## workers-combined

![workers-combined](workers-combined.png)

[Open zoomable SVG](workers-combined.svg)

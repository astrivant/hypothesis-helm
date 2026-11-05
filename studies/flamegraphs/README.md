# Flame graphs

<!-- toc:start -->
**Table of contents**

- [coordinator-3179-8bcff977636fd3d5c7142f418d3eed10](#coordinator-3179-8bcff977636fd3d5c7142f418d3eed10)
- [worker-3194-79d668766dcbf8dfffa475430b53c2ec](#worker-3194-79d668766dcbf8dfffa475430b53c2ec)
- [worker-3208-bb2d12e2e2459dec5a330f45f72216a4](#worker-3208-bb2d12e2e2459dec5a330f45f72216a4)
- [worker-3211-de896d92083ce11923058461022c2c45](#worker-3211-de896d92083ce11923058461022c2c45)
- [worker-3236-19e1cd396bd65ccf48e7810bf66a7748](#worker-3236-19e1cd396bd65ccf48e7810bf66a7748)
- [worker-3239-a5a15145c022e114c70336a9171df8a1](#worker-3239-a5a15145c022e114c70336a9171df8a1)
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

## coordinator-3179-8bcff977636fd3d5c7142f418d3eed10

![coordinator-3179-8bcff977636fd3d5c7142f418d3eed10](<coordinator-3179-8bcff977636fd3d5c7142f418d3eed10.png>)

[Open zoomable SVG](<coordinator-3179-8bcff977636fd3d5c7142f418d3eed10.svg>)

## worker-3194-79d668766dcbf8dfffa475430b53c2ec

![worker-3194-79d668766dcbf8dfffa475430b53c2ec](<worker-3194-79d668766dcbf8dfffa475430b53c2ec.png>)

[Open zoomable SVG](<worker-3194-79d668766dcbf8dfffa475430b53c2ec.svg>)

## worker-3208-bb2d12e2e2459dec5a330f45f72216a4

![worker-3208-bb2d12e2e2459dec5a330f45f72216a4](<worker-3208-bb2d12e2e2459dec5a330f45f72216a4.png>)

[Open zoomable SVG](<worker-3208-bb2d12e2e2459dec5a330f45f72216a4.svg>)

## worker-3211-de896d92083ce11923058461022c2c45

![worker-3211-de896d92083ce11923058461022c2c45](<worker-3211-de896d92083ce11923058461022c2c45.png>)

[Open zoomable SVG](<worker-3211-de896d92083ce11923058461022c2c45.svg>)

## worker-3236-19e1cd396bd65ccf48e7810bf66a7748

![worker-3236-19e1cd396bd65ccf48e7810bf66a7748](<worker-3236-19e1cd396bd65ccf48e7810bf66a7748.png>)

[Open zoomable SVG](<worker-3236-19e1cd396bd65ccf48e7810bf66a7748.svg>)

## worker-3239-a5a15145c022e114c70336a9171df8a1

![worker-3239-a5a15145c022e114c70336a9171df8a1](<worker-3239-a5a15145c022e114c70336a9171df8a1.png>)

[Open zoomable SVG](<worker-3239-a5a15145c022e114c70336a9171df8a1.svg>)

## workers-combined

![workers-combined](<workers-combined.png>)

[Open zoomable SVG](<workers-combined.svg>)

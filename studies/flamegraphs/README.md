# Flame graphs

<!-- toc:start -->
**Table of contents**

- [coordinator-3124-661c0857c69129bf8727ed4e23b005fd](#coordinator-3124-661c0857c69129bf8727ed4e23b005fd)
- [worker-3139-a6576695955fb1834cd4421820ff7c88](#worker-3139-a6576695955fb1834cd4421820ff7c88)
- [worker-3153-31a33fa6ed3d4e98f353e85f94be1ea0](#worker-3153-31a33fa6ed3d4e98f353e85f94be1ea0)
- [worker-3156-f072abd64cf525f3bd24d1d0df0b1fdb](#worker-3156-f072abd64cf525f3bd24d1d0df0b1fdb)
- [worker-3182-f3ad0b2df86f373f38ca330801245b02](#worker-3182-f3ad0b2df86f373f38ca330801245b02)
- [worker-3185-70af94b32a8038ee7ef3df07950996e2](#worker-3185-70af94b32a8038ee7ef3df07950996e2)
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

## coordinator-3124-661c0857c69129bf8727ed4e23b005fd

![coordinator-3124-661c0857c69129bf8727ed4e23b005fd](<coordinator-3124-661c0857c69129bf8727ed4e23b005fd.png>)

[Open zoomable SVG](<coordinator-3124-661c0857c69129bf8727ed4e23b005fd.svg>)

## worker-3139-a6576695955fb1834cd4421820ff7c88

![worker-3139-a6576695955fb1834cd4421820ff7c88](<worker-3139-a6576695955fb1834cd4421820ff7c88.png>)

[Open zoomable SVG](<worker-3139-a6576695955fb1834cd4421820ff7c88.svg>)

## worker-3153-31a33fa6ed3d4e98f353e85f94be1ea0

![worker-3153-31a33fa6ed3d4e98f353e85f94be1ea0](<worker-3153-31a33fa6ed3d4e98f353e85f94be1ea0.png>)

[Open zoomable SVG](<worker-3153-31a33fa6ed3d4e98f353e85f94be1ea0.svg>)

## worker-3156-f072abd64cf525f3bd24d1d0df0b1fdb

![worker-3156-f072abd64cf525f3bd24d1d0df0b1fdb](<worker-3156-f072abd64cf525f3bd24d1d0df0b1fdb.png>)

[Open zoomable SVG](<worker-3156-f072abd64cf525f3bd24d1d0df0b1fdb.svg>)

## worker-3182-f3ad0b2df86f373f38ca330801245b02

![worker-3182-f3ad0b2df86f373f38ca330801245b02](<worker-3182-f3ad0b2df86f373f38ca330801245b02.png>)

[Open zoomable SVG](<worker-3182-f3ad0b2df86f373f38ca330801245b02.svg>)

## worker-3185-70af94b32a8038ee7ef3df07950996e2

![worker-3185-70af94b32a8038ee7ef3df07950996e2](<worker-3185-70af94b32a8038ee7ef3df07950996e2.png>)

[Open zoomable SVG](<worker-3185-70af94b32a8038ee7ef3df07950996e2.svg>)

## workers-combined

![workers-combined](<workers-combined.png>)

[Open zoomable SVG](<workers-combined.svg>)

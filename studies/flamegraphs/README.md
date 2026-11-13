# Flame graphs

<!-- toc:start -->
**Table of contents**

- [coordinator-3018-514d38c855f17331075827d513446a3c](#coordinator-3018-514d38c855f17331075827d513446a3c)
- [worker-3034-297fbbcdbc0c6823b7ed1b0d08de2115](#worker-3034-297fbbcdbc0c6823b7ed1b0d08de2115)
- [worker-3050-298832f27b657ed12438a951b4585749](#worker-3050-298832f27b657ed12438a951b4585749)
- [worker-3053-fd58064d8bdd2f38e94ce7ed561d17f1](#worker-3053-fd58064d8bdd2f38e94ce7ed561d17f1)
- [worker-3156-4409c7fff5a60ef4a187cd386e9427b9](#worker-3156-4409c7fff5a60ef4a187cd386e9427b9)
- [worker-3159-1afa85a73f5e83c8cc618a3cdf18dca4](#worker-3159-1afa85a73f5e83c8cc618a3cdf18dca4)
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

## coordinator-3018-514d38c855f17331075827d513446a3c

![coordinator-3018-514d38c855f17331075827d513446a3c](coordinator-3018-514d38c855f17331075827d513446a3c.png)

[Open zoomable SVG](coordinator-3018-514d38c855f17331075827d513446a3c.svg)

## worker-3034-297fbbcdbc0c6823b7ed1b0d08de2115

![worker-3034-297fbbcdbc0c6823b7ed1b0d08de2115](worker-3034-297fbbcdbc0c6823b7ed1b0d08de2115.png)

[Open zoomable SVG](worker-3034-297fbbcdbc0c6823b7ed1b0d08de2115.svg)

## worker-3050-298832f27b657ed12438a951b4585749

![worker-3050-298832f27b657ed12438a951b4585749](worker-3050-298832f27b657ed12438a951b4585749.png)

[Open zoomable SVG](worker-3050-298832f27b657ed12438a951b4585749.svg)

## worker-3053-fd58064d8bdd2f38e94ce7ed561d17f1

![worker-3053-fd58064d8bdd2f38e94ce7ed561d17f1](worker-3053-fd58064d8bdd2f38e94ce7ed561d17f1.png)

[Open zoomable SVG](worker-3053-fd58064d8bdd2f38e94ce7ed561d17f1.svg)

## worker-3156-4409c7fff5a60ef4a187cd386e9427b9

![worker-3156-4409c7fff5a60ef4a187cd386e9427b9](worker-3156-4409c7fff5a60ef4a187cd386e9427b9.png)

[Open zoomable SVG](worker-3156-4409c7fff5a60ef4a187cd386e9427b9.svg)

## worker-3159-1afa85a73f5e83c8cc618a3cdf18dca4

![worker-3159-1afa85a73f5e83c8cc618a3cdf18dca4](worker-3159-1afa85a73f5e83c8cc618a3cdf18dca4.png)

[Open zoomable SVG](worker-3159-1afa85a73f5e83c8cc618a3cdf18dca4.svg)

## workers-combined

![workers-combined](workers-combined.png)

[Open zoomable SVG](workers-combined.svg)

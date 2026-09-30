# Flame graphs

<!-- toc:start -->
**Table of contents**

- [coordinator-2898-39f57827d2ff4062be31a8e13164f9a3](#coordinator-2898-39f57827d2ff4062be31a8e13164f9a3)
- [worker-2913-8800af5d480e4b9bc9eae9d6e050868a](#worker-2913-8800af5d480e4b9bc9eae9d6e050868a)
- [worker-2927-33da242e64eff8b20eddaa7ef837a1ab](#worker-2927-33da242e64eff8b20eddaa7ef837a1ab)
- [worker-2930-c1823184abb9de3696b0a4edd76950c7](#worker-2930-c1823184abb9de3696b0a4edd76950c7)
- [worker-2954-cccc29b0bdbca0c694c439b1be7ecea8](#worker-2954-cccc29b0bdbca0c694c439b1be7ecea8)
- [worker-2957-4cce21569aa6d89a2becbeab1c4bb59f](#worker-2957-4cce21569aa6d89a2becbeab1c4bb59f)
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

## coordinator-2898-39f57827d2ff4062be31a8e13164f9a3

![coordinator-2898-39f57827d2ff4062be31a8e13164f9a3](<coordinator-2898-39f57827d2ff4062be31a8e13164f9a3.png>)

[Open zoomable SVG](<coordinator-2898-39f57827d2ff4062be31a8e13164f9a3.svg>)

## worker-2913-8800af5d480e4b9bc9eae9d6e050868a

![worker-2913-8800af5d480e4b9bc9eae9d6e050868a](<worker-2913-8800af5d480e4b9bc9eae9d6e050868a.png>)

[Open zoomable SVG](<worker-2913-8800af5d480e4b9bc9eae9d6e050868a.svg>)

## worker-2927-33da242e64eff8b20eddaa7ef837a1ab

![worker-2927-33da242e64eff8b20eddaa7ef837a1ab](<worker-2927-33da242e64eff8b20eddaa7ef837a1ab.png>)

[Open zoomable SVG](<worker-2927-33da242e64eff8b20eddaa7ef837a1ab.svg>)

## worker-2930-c1823184abb9de3696b0a4edd76950c7

![worker-2930-c1823184abb9de3696b0a4edd76950c7](<worker-2930-c1823184abb9de3696b0a4edd76950c7.png>)

[Open zoomable SVG](<worker-2930-c1823184abb9de3696b0a4edd76950c7.svg>)

## worker-2954-cccc29b0bdbca0c694c439b1be7ecea8

![worker-2954-cccc29b0bdbca0c694c439b1be7ecea8](<worker-2954-cccc29b0bdbca0c694c439b1be7ecea8.png>)

[Open zoomable SVG](<worker-2954-cccc29b0bdbca0c694c439b1be7ecea8.svg>)

## worker-2957-4cce21569aa6d89a2becbeab1c4bb59f

![worker-2957-4cce21569aa6d89a2becbeab1c4bb59f](<worker-2957-4cce21569aa6d89a2becbeab1c4bb59f.png>)

[Open zoomable SVG](<worker-2957-4cce21569aa6d89a2becbeab1c4bb59f.svg>)

## workers-combined

![workers-combined](<workers-combined.png>)

[Open zoomable SVG](<workers-combined.svg>)

# Flame graphs

<!-- toc:start -->
**Table of contents**

- [coordinator-3101-eec3bb9eba0636f91b1d925ae711d6fc](#coordinator-3101-eec3bb9eba0636f91b1d925ae711d6fc)
- [worker-3116-ec1b611f2e004274d80ef8cf8d696cc1](#worker-3116-ec1b611f2e004274d80ef8cf8d696cc1)
- [worker-3130-5de9a15e89d480d3b910167bd077f120](#worker-3130-5de9a15e89d480d3b910167bd077f120)
- [worker-3133-bddbdc6b6e8e408fd0e12387e735ab73](#worker-3133-bddbdc6b6e8e408fd0e12387e735ab73)
- [worker-3157-2d1185979a986c3abb5fe6870efebf92](#worker-3157-2d1185979a986c3abb5fe6870efebf92)
- [worker-3160-abf29e5c27d44cdccdc43eef41f35973](#worker-3160-abf29e5c27d44cdccdc43eef41f35973)
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

## coordinator-3101-eec3bb9eba0636f91b1d925ae711d6fc

![coordinator-3101-eec3bb9eba0636f91b1d925ae711d6fc](coordinator-3101-eec3bb9eba0636f91b1d925ae711d6fc.png)

[Open zoomable SVG](coordinator-3101-eec3bb9eba0636f91b1d925ae711d6fc.svg)

## worker-3116-ec1b611f2e004274d80ef8cf8d696cc1

![worker-3116-ec1b611f2e004274d80ef8cf8d696cc1](worker-3116-ec1b611f2e004274d80ef8cf8d696cc1.png)

[Open zoomable SVG](worker-3116-ec1b611f2e004274d80ef8cf8d696cc1.svg)

## worker-3130-5de9a15e89d480d3b910167bd077f120

![worker-3130-5de9a15e89d480d3b910167bd077f120](worker-3130-5de9a15e89d480d3b910167bd077f120.png)

[Open zoomable SVG](worker-3130-5de9a15e89d480d3b910167bd077f120.svg)

## worker-3133-bddbdc6b6e8e408fd0e12387e735ab73

![worker-3133-bddbdc6b6e8e408fd0e12387e735ab73](worker-3133-bddbdc6b6e8e408fd0e12387e735ab73.png)

[Open zoomable SVG](worker-3133-bddbdc6b6e8e408fd0e12387e735ab73.svg)

## worker-3157-2d1185979a986c3abb5fe6870efebf92

![worker-3157-2d1185979a986c3abb5fe6870efebf92](worker-3157-2d1185979a986c3abb5fe6870efebf92.png)

[Open zoomable SVG](worker-3157-2d1185979a986c3abb5fe6870efebf92.svg)

## worker-3160-abf29e5c27d44cdccdc43eef41f35973

![worker-3160-abf29e5c27d44cdccdc43eef41f35973](worker-3160-abf29e5c27d44cdccdc43eef41f35973.png)

[Open zoomable SVG](worker-3160-abf29e5c27d44cdccdc43eef41f35973.svg)

## workers-combined

![workers-combined](workers-combined.png)

[Open zoomable SVG](workers-combined.svg)

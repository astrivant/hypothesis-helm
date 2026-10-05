# Flame graphs

<!-- toc:start -->
**Table of contents**

- [coordinator-2981-edb2e3c61df774b64813a8c1d4968398](#coordinator-2981-edb2e3c61df774b64813a8c1d4968398)
- [worker-2996-9dc25ea5c298f9baa8051501203912bd](#worker-2996-9dc25ea5c298f9baa8051501203912bd)
- [worker-3010-57d21f5128b89667796528e936cae9ca](#worker-3010-57d21f5128b89667796528e936cae9ca)
- [worker-3013-36b34e3feea18de8186587a5d2193754](#worker-3013-36b34e3feea18de8186587a5d2193754)
- [worker-3037-d6b3fa9cb2fecceab719037959375152](#worker-3037-d6b3fa9cb2fecceab719037959375152)
- [worker-3040-6a6c554ff34e2ac804960df56d36e00a](#worker-3040-6a6c554ff34e2ac804960df56d36e00a)
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

## coordinator-2981-edb2e3c61df774b64813a8c1d4968398

![coordinator-2981-edb2e3c61df774b64813a8c1d4968398](<coordinator-2981-edb2e3c61df774b64813a8c1d4968398.png>)

[Open zoomable SVG](<coordinator-2981-edb2e3c61df774b64813a8c1d4968398.svg>)

## worker-2996-9dc25ea5c298f9baa8051501203912bd

![worker-2996-9dc25ea5c298f9baa8051501203912bd](<worker-2996-9dc25ea5c298f9baa8051501203912bd.png>)

[Open zoomable SVG](<worker-2996-9dc25ea5c298f9baa8051501203912bd.svg>)

## worker-3010-57d21f5128b89667796528e936cae9ca

![worker-3010-57d21f5128b89667796528e936cae9ca](<worker-3010-57d21f5128b89667796528e936cae9ca.png>)

[Open zoomable SVG](<worker-3010-57d21f5128b89667796528e936cae9ca.svg>)

## worker-3013-36b34e3feea18de8186587a5d2193754

![worker-3013-36b34e3feea18de8186587a5d2193754](<worker-3013-36b34e3feea18de8186587a5d2193754.png>)

[Open zoomable SVG](<worker-3013-36b34e3feea18de8186587a5d2193754.svg>)

## worker-3037-d6b3fa9cb2fecceab719037959375152

![worker-3037-d6b3fa9cb2fecceab719037959375152](<worker-3037-d6b3fa9cb2fecceab719037959375152.png>)

[Open zoomable SVG](<worker-3037-d6b3fa9cb2fecceab719037959375152.svg>)

## worker-3040-6a6c554ff34e2ac804960df56d36e00a

![worker-3040-6a6c554ff34e2ac804960df56d36e00a](<worker-3040-6a6c554ff34e2ac804960df56d36e00a.png>)

[Open zoomable SVG](<worker-3040-6a6c554ff34e2ac804960df56d36e00a.svg>)

## workers-combined

![workers-combined](<workers-combined.png>)

[Open zoomable SVG](<workers-combined.svg>)

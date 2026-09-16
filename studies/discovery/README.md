# Bug discovery by interaction strength

<!-- toc:start -->
**Table of contents**

- [Bug discovery by interaction strength](#bug-discovery-by-interaction-strength)
<!-- toc:end -->

[Benchmarking](../../docs/benchmarking/README.md)

This fixed fixture contains 60 injected faults. The planner varies interaction strength from one to six, with automatic enumeration and inferred exhaustive groups disabled to isolate strength. Every selected input is rendered with Helm 4.

| Strength | Inputs tested / planned | Faults found / total | Missed faults | Seconds | Status |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 9 / 9 | 23 / 60 | 37 | 0.42 | passed |
| 2 | 37 / 37 | 40 / 60 | 20 | 1.84 | passed |
| 3 | 93 / 93 | 54 / 60 | 6 | 4.70 | passed |
| 4 | 163 / 163 | 59 / 60 | 1 | 8.69 | passed |
| 5 | 219 / 219 | 60 / 60 | 0 | 10.27 | passed |
| 6 | 247 / 247 | 60 / 60 | 0 | 11.36 | passed |

![Known faults found](bug-discovery.png)

![Discovery by fault order](bug-order.png)

[JSON ledger](results.json) · [CSV table](results.csv) · [Chart fixture](chart)

These are distinct injected faults; several input assignments can trigger the same fault. Rates describe this seeded fixture, not expected bug recall for an arbitrary chart.

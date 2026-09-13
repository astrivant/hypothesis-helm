# Bug discovery by interaction strength

[Benchmarking](../README.md)

This fixed fixture contains 261 injected faults. The planner varies interaction strength from one to six, with automatic enumeration and inferred exhaustive groups disabled to isolate strength. Every selected input is rendered with Helm 4.

| Strength | Inputs tested / planned | Faults found / total | Missed faults | Seconds | Status |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 9 / 9 | 64 / 261 | 197 | 0.61 | passed |
| 2 | 37 / 37 | 136 / 261 | 125 | 2.65 | passed |
| 3 | 93 / 93 | 208 / 261 | 53 | 6.29 | passed |
| 4 | 163 / 163 | 250 / 261 | 11 | 11.41 | passed |
| 5 | 219 / 219 | 261 / 261 | 0 | 15.33 | passed |
| 6 | 247 / 247 | 261 / 261 | 0 | 16.93 | passed |

![Known faults found](bug-discovery.png)

![Discovery by fault order](bug-order.png)

[JSON ledger](results.json) · [CSV table](results.csv) · [Chart fixture](chart)

These are distinct injected faults; several input assignments can trigger the same fault. Rates describe this seeded fixture, not expected bug recall for an arbitrary chart.

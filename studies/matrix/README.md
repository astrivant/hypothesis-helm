# Structural strategy matrix

<!-- toc:start -->
**Table of contents**

- [Structural strategy matrix](#structural-strategy-matrix)
<!-- toc:end -->

[Benchmarking](<../../docs/benchmarking/README.md>)

Helm `v4.3.0+gbec5b06`; 540s execution ceiling per run; filter level 2; seed 2026.

All strategy columns use the same complete valid input domain within each case. Planning and analysis are timed separately and excluded from the execution ceiling. Fresh caches; sequential runs.

Each filter column uses the stated level; combined enables both at that level. Exact-equivalence pruning is enabled only in its own column.

Cells show **outcome coverage / total seconds / Helm invocations**.

| Structure | Default | Exact equivalence | Random filter | Topology filter | Both filters | --filter | --filter-adaptive |
|---|---|---|---|---|---|---|---|
| constraints | 100% / 19.2s / 512 | 100% / 19.2s / 512 | 100% / 1.4s / 33 | 100% / 19.2s / 512 | 100% / 18.9s / 512 | 100% / 19.2s / 512 | 100% / 19.7s / 512 |
| control-flow | 100% / 39.2s / 1024 | 100% / 40.1s / 1024 | 100% / 2.7s / 65 | 100% / 38.9s / 1024 | 100% / 38.8s / 1024 | 100% / 39.0s / 1024 | 100% / 40.0s / 1024 |
| dependencies | 100% / 39.9s / 1024 | 100% / 2.3s / 8 | 100% / 2.6s / 65 | 100% / 2.7s / 65 | 100% / 0.5s / 9 | 100% / 2.8s / 65 | 100% / 2.8s / 65 |
| interactions | 100% / 38.6s / 1024 | 100% / 2.4s / 20 | 75% / 2.4s / 65 | 100% / 2.6s / 65 | 100% / 1.0s / 21 | 100% / 2.7s / 65 | 100% / 2.8s / 65 |
| equivalence | 100% / 38.4s / 1024 | 100% / 1.7s / 4 | 100% / 2.4s / 65 | 100% / 2.6s / 65 | 100% / 0.3s / 5 | 100% / 2.7s / 65 | 100% / 2.7s / 65 |
| boundaries | 100% / 57.9s / 1536 | 100% / 58.0s / 1536 | 100% / 3.8s / 97 | 100% / 58.6s / 1536 | 100% / 58.2s / 1536 | 100% / 58.0s / 1536 | 100% / 57.8s / 1536 |

![Measured strategy matrix](strategy-matrix.png)

Raw measurements (local run data) · CSV (local run data)

Constraints use coupled Boolean inputs; control flow includes an input-dependent loop; dependencies share a Service/Ingress port; interactions expose a four-way rare branch; equivalence varies output-irrelevant fields; boundaries cross an integer threshold.

The current compiler conservatively retains cases it cannot classify. A topology fallback records that analysis limit. Topology sampling favors diversity and may change outcome frequencies. Results describe the measured fixtures; broader recall estimates require independent chart populations.


`--filter` and `--filter-adaptive` use topology level 2 and enable failure expansion. Aggressive sampling recomputes chart complexity, protects structural regions and applies the packaged calibration. An unmatched or unsupported chart keeps the ordinary filtered selection; 70% retention is not forced. Expansion-off columns are controlled ablations of these presets.

**Aggressive sampling decisions.** Counts below exclude the always-retained default configuration and precede failure expansion. Case and field floors apply only to matched calibrations.

| Fixture | Match | Retained / eligible | Case floor | Field floor | Fallback reason |
| --- | --- | ---: | ---: | ---: | --- |
| constraints | unmatched | 511 / 511 | 1 | 0 | schema validation is outside the shared proof contract |
| control-flow | unmatched | 1023 / 1023 | 1 | 0 | opaque template construct at line 9 |
| dependencies | unmatched | 64 / 64 | 1 | 0 | chart complexity or topology is outside the measured calibration profiles |
| interactions | unmatched | 64 / 64 | 1 | 0 | chart complexity or topology is outside the measured calibration profiles |
| equivalence | unmatched | 64 / 64 | 1 | 0 | chart complexity or topology is outside the measured calibration profiles |
| boundaries | unmatched | 1535 / 1535 | 1 | 0 | default coalescing or scalar types are outside the proof contract |

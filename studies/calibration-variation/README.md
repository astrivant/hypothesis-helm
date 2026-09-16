# Aggressive sampling calibration

<!-- toc:start -->
**Table of contents**

- [Breadth and depth sweep](#breadth-and-depth-sweep)
<!-- toc:end -->

Generated-chart calibration only. No held-out validation or arbitrary-chart recall guarantee.

Every input was rendered with Helm and compared with an independent defect-trigger oracle.
Floors include protected symbolic regions. Field coverage counts changed paths separately from configurations.
Measured maximum output scores: **24, 40, 56, 60, 100, 108, 140, 180, 252**. Other scores are outside this calibration's range.
[Comparison matrix and graphs](MATRIX.md) · [Proof obligations and tests](../../docs/adaptive-filtering/TESTS.md)

![Measured sample floors and recall](calibration.png)

| Case | Max complexity | Gate depth | Fields | Eligible | Protected | Case floor | Field floor | Seeds reaching 96% bug recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fields-6-depth-1-placement-0-breadth-1-output-depth-0 | 24 | 1 | 6 | 8 | 8 | 8 | 4 | 100/100 |
| fields-6-depth-1-placement-0-breadth-1-output-depth-1 | 40 | 1 | 6 | 8 | 8 | 8 | 4 | 100/100 |
| fields-6-depth-1-placement-0-breadth-1-output-depth-2 | 56 | 1 | 6 | 8 | 8 | 8 | 4 | 100/100 |
| fields-6-depth-1-placement-0-breadth-4-output-depth-0 | 60 | 1 | 6 | 8 | 8 | 8 | 4 | 100/100 |
| fields-6-depth-1-placement-0-breadth-4-output-depth-1 | 100 | 1 | 6 | 8 | 8 | 8 | 4 | 100/100 |
| fields-6-depth-1-placement-0-breadth-4-output-depth-2 | 140 | 1 | 6 | 8 | 8 | 8 | 4 | 100/100 |
| fields-6-depth-1-placement-0-breadth-8-output-depth-0 | 108 | 1 | 6 | 8 | 8 | 8 | 4 | 100/100 |
| fields-6-depth-1-placement-0-breadth-8-output-depth-1 | 180 | 1 | 6 | 8 | 8 | 8 | 4 | 100/100 |
| fields-6-depth-1-placement-0-breadth-8-output-depth-2 | 252 | 1 | 6 | 8 | 8 | 8 | 4 | 100/100 |
| fields-6-depth-1-placement-1-breadth-1-output-depth-0 | 24 | 1 | 6 | 4 | 4 | 4 | 3 | 100/100 |
| fields-6-depth-1-placement-1-breadth-1-output-depth-1 | 40 | 1 | 6 | 4 | 4 | 4 | 3 | 100/100 |
| fields-6-depth-1-placement-1-breadth-1-output-depth-2 | 56 | 1 | 6 | 4 | 4 | 4 | 3 | 100/100 |
| fields-6-depth-1-placement-1-breadth-4-output-depth-0 | 60 | 1 | 6 | 4 | 4 | 4 | 3 | 100/100 |
| fields-6-depth-1-placement-1-breadth-4-output-depth-1 | 100 | 1 | 6 | 4 | 4 | 4 | 3 | 100/100 |
| fields-6-depth-1-placement-1-breadth-4-output-depth-2 | 140 | 1 | 6 | 4 | 4 | 4 | 3 | 100/100 |
| fields-6-depth-1-placement-1-breadth-8-output-depth-0 | 108 | 1 | 6 | 4 | 4 | 4 | 3 | 100/100 |
| fields-6-depth-1-placement-1-breadth-8-output-depth-1 | 180 | 1 | 6 | 4 | 4 | 4 | 3 | 100/100 |
| fields-6-depth-1-placement-1-breadth-8-output-depth-2 | 252 | 1 | 6 | 4 | 4 | 4 | 3 | 100/100 |
| fields-6-depth-3-placement-0-breadth-1-output-depth-0 | 24 | 3 | 6 | 29 | 29 | 29 | 6 | 100/100 |
| fields-6-depth-3-placement-0-breadth-1-output-depth-1 | 40 | 3 | 6 | 29 | 29 | 29 | 6 | 100/100 |
| fields-6-depth-3-placement-0-breadth-1-output-depth-2 | 56 | 3 | 6 | 29 | 29 | 29 | 6 | 100/100 |
| fields-6-depth-3-placement-0-breadth-4-output-depth-0 | 60 | 3 | 6 | 29 | 29 | 29 | 6 | 100/100 |
| fields-6-depth-3-placement-0-breadth-4-output-depth-1 | 100 | 3 | 6 | 29 | 29 | 29 | 6 | 100/100 |
| fields-6-depth-3-placement-0-breadth-4-output-depth-2 | 140 | 3 | 6 | 29 | 29 | 29 | 6 | 100/100 |
| fields-6-depth-3-placement-0-breadth-8-output-depth-0 | 108 | 3 | 6 | 29 | 29 | 29 | 6 | 100/100 |
| fields-6-depth-3-placement-0-breadth-8-output-depth-1 | 180 | 3 | 6 | 29 | 29 | 29 | 6 | 100/100 |
| fields-6-depth-3-placement-0-breadth-8-output-depth-2 | 252 | 3 | 6 | 29 | 29 | 29 | 6 | 100/100 |
| fields-6-depth-3-placement-1-breadth-1-output-depth-0 | 24 | 3 | 6 | 16 | 16 | 16 | 5 | 100/100 |
| fields-6-depth-3-placement-1-breadth-1-output-depth-1 | 40 | 3 | 6 | 16 | 16 | 16 | 5 | 100/100 |
| fields-6-depth-3-placement-1-breadth-1-output-depth-2 | 56 | 3 | 6 | 16 | 16 | 16 | 5 | 100/100 |
| fields-6-depth-3-placement-1-breadth-4-output-depth-0 | 60 | 3 | 6 | 16 | 16 | 16 | 5 | 100/100 |
| fields-6-depth-3-placement-1-breadth-4-output-depth-1 | 100 | 3 | 6 | 16 | 16 | 16 | 5 | 100/100 |
| fields-6-depth-3-placement-1-breadth-4-output-depth-2 | 140 | 3 | 6 | 16 | 16 | 16 | 5 | 100/100 |
| fields-6-depth-3-placement-1-breadth-8-output-depth-0 | 108 | 3 | 6 | 16 | 16 | 16 | 5 | 100/100 |
| fields-6-depth-3-placement-1-breadth-8-output-depth-1 | 180 | 3 | 6 | 16 | 16 | 16 | 5 | 100/100 |
| fields-6-depth-3-placement-1-breadth-8-output-depth-2 | 252 | 3 | 6 | 16 | 16 | 16 | 5 | 100/100 |
| fields-6-depth-5-placement-0-breadth-1-output-depth-0 | 24 | 5 | 6 | 32 | 32 | 32 | 6 | 100/100 |
| fields-6-depth-5-placement-0-breadth-1-output-depth-1 | 40 | 5 | 6 | 32 | 32 | 32 | 6 | 100/100 |
| fields-6-depth-5-placement-0-breadth-1-output-depth-2 | 56 | 5 | 6 | 32 | 32 | 32 | 6 | 100/100 |
| fields-6-depth-5-placement-0-breadth-4-output-depth-0 | 60 | 5 | 6 | 32 | 32 | 32 | 6 | 100/100 |
| fields-6-depth-5-placement-0-breadth-4-output-depth-1 | 100 | 5 | 6 | 32 | 32 | 32 | 6 | 100/100 |
| fields-6-depth-5-placement-0-breadth-4-output-depth-2 | 140 | 5 | 6 | 32 | 32 | 32 | 6 | 100/100 |
| fields-6-depth-5-placement-0-breadth-8-output-depth-0 | 108 | 5 | 6 | 32 | 32 | 32 | 6 | 100/100 |
| fields-6-depth-5-placement-0-breadth-8-output-depth-1 | 180 | 5 | 6 | 32 | 32 | 32 | 6 | 100/100 |
| fields-6-depth-5-placement-0-breadth-8-output-depth-2 | 252 | 5 | 6 | 32 | 32 | 32 | 6 | 100/100 |
| fields-6-depth-5-placement-1-breadth-1-output-depth-0 | 24 | 5 | 6 | 28 | 28 | 28 | 6 | 100/100 |
| fields-6-depth-5-placement-1-breadth-1-output-depth-1 | 40 | 5 | 6 | 28 | 28 | 28 | 6 | 100/100 |
| fields-6-depth-5-placement-1-breadth-1-output-depth-2 | 56 | 5 | 6 | 28 | 28 | 28 | 6 | 100/100 |
| fields-6-depth-5-placement-1-breadth-4-output-depth-0 | 60 | 5 | 6 | 28 | 28 | 28 | 6 | 100/100 |
| fields-6-depth-5-placement-1-breadth-4-output-depth-1 | 100 | 5 | 6 | 28 | 28 | 28 | 6 | 100/100 |
| fields-6-depth-5-placement-1-breadth-4-output-depth-2 | 140 | 5 | 6 | 28 | 28 | 28 | 6 | 100/100 |
| fields-6-depth-5-placement-1-breadth-8-output-depth-0 | 108 | 5 | 6 | 28 | 28 | 28 | 6 | 100/100 |
| fields-6-depth-5-placement-1-breadth-8-output-depth-1 | 180 | 5 | 6 | 28 | 28 | 28 | 6 | 100/100 |
| fields-6-depth-5-placement-1-breadth-8-output-depth-2 | 252 | 5 | 6 | 28 | 28 | 28 | 6 | 100/100 |

## Breadth and depth sweep

![Sample floors across output breadth and depth](complexity-sweep.png)

Sibling ConfigMap copies vary breadth; nested List envelopes vary output depth. Axis labels are measured tree dimensions.
Each panel holds input count and defect-trigger depth fixed. Every shape uses the same paired defect placements and sampling seeds.
Copies preserve the same defect triggers: a flat surface means increasing output size alone did not increase the measured floor.
Cells show mean ±1 sample standard deviation across placements, not a confidence interval or a recall guarantee.
[Sweep measurements](complexity-sweep.csv)


Complete recall here can follow from preserving every symbolic output region. It does not validate random sampling alone.

[Calibration JSON](calibration.json) · [Measurements](results.csv)

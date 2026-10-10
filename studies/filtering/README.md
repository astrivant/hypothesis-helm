# Filtering load test

<!-- toc:start -->
**Table of contents**

- [Filtering load test](#filtering-load-test)
<!-- toc:end -->

[Theory and conditions](../../docs/adaptive-filtering/README.md#computational-cost)

A gate is a template `if` condition. Depth counts nested conditions required to reach the innermost branch.

![Total runtime](<filtering-runtime.png>)

![Planning runtime](<filtering-planning.png>)

![Completed work](<filtering-completed.png>)

![Phase costs](<filtering-phases.png>)

2 paired repeats per chart and method; execution ceiling 540.0 seconds per run.
Dark bands show mean ±1 sample SD; light bands show ±2 SD, describing variation across paired repeats. Method order is seeded and shuffled for each repeat.
Input count is the full Boolean domain (2^fields); interaction strength stays at two.
The small finite domains are fully enumerated before filtering.
Gate depth changes branch rarity, fan-in and equivalent-output regions.

The engine runs real Helm checks with no shared outcome cache. Each invocation creates its own render-hash cache.
OS and Helm executable caches can remain warm. Chart generation, CLI startup and dependency preparation are excluded.
Planning and analysis are included in total engine time. The execution ceiling does not cap planning.

`sample-random` retains 70% subject to its normal 128-case floor. `filter` uses topology depth two and failure expansion.
`filter-adaptive` adds its measured floors; unmatched charts keep ordinary filtering. All methods use the same traversal seed.
The chart's injected markers change topology but are not asserted as lint failures in this successful-render load test.
Failure expansion is enabled for both filter presets; workloads with actual failing properties may expand toward the full plan.

| Fields | Depth | Repeat | Method | Selected | Completed | Total s | Planning s | Complexity s | Execution s | Status |
| ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 6 | 1 | 0 | baseline | 64 | 64 | 1.750 | 0.024 | 0.000 | 1.669 | passed |
| 6 | 1 | 0 | sample-random | 64 | 64 | 1.717 | 0.025 | 0.000 | 1.686 | passed |
| 6 | 1 | 0 | filter-adaptive | 5 | 5 | 0.250 | 0.105 | 0.023 | 0.139 | passed |
| 6 | 1 | 0 | filter | 5 | 5 | 0.198 | 0.057 | 0.000 | 0.135 | passed |
| 6 | 1 | 1 | baseline | 64 | 64 | 1.719 | 0.024 | 0.000 | 1.689 | passed |
| 6 | 1 | 1 | sample-random | 64 | 64 | 1.722 | 0.076 | 0.000 | 1.640 | passed |
| 6 | 1 | 1 | filter | 5 | 5 | 0.194 | 0.053 | 0.000 | 0.134 | passed |
| 6 | 1 | 1 | filter-adaptive | 5 | 5 | 0.217 | 0.076 | 0.020 | 0.134 | passed |
| 6 | 3 | 0 | baseline | 64 | 64 | 1.760 | 0.024 | 0.000 | 1.721 | passed |
| 6 | 3 | 0 | filter | 17 | 17 | 0.484 | 0.056 | 0.000 | 0.421 | passed |
| 6 | 3 | 0 | filter-adaptive | 17 | 17 | 0.532 | 0.098 | 0.041 | 0.428 | passed |
| 6 | 3 | 0 | sample-random | 64 | 64 | 1.681 | 0.025 | 0.000 | 1.650 | passed |
| 6 | 3 | 1 | filter-adaptive | 17 | 17 | 0.546 | 0.098 | 0.042 | 0.441 | passed |
| 6 | 3 | 1 | baseline | 64 | 64 | 1.710 | 0.024 | 0.000 | 1.679 | passed |
| 6 | 3 | 1 | sample-random | 64 | 64 | 1.682 | 0.025 | 0.000 | 1.651 | passed |
| 6 | 3 | 1 | filter | 17 | 17 | 0.510 | 0.060 | 0.000 | 0.443 | passed |
| 6 | 5 | 0 | filter | 29 | 29 | 0.811 | 0.059 | 0.000 | 0.734 | passed |
| 6 | 5 | 0 | sample-random | 64 | 64 | 1.699 | 0.026 | 0.000 | 1.667 | passed |
| 6 | 5 | 0 | filter-adaptive | 29 | 29 | 0.893 | 0.130 | 0.068 | 0.757 | passed |
| 6 | 5 | 0 | baseline | 64 | 64 | 1.692 | 0.026 | 0.000 | 1.659 | passed |
| 6 | 5 | 1 | filter | 29 | 29 | 0.815 | 0.058 | 0.000 | 0.750 | passed |
| 6 | 5 | 1 | filter-adaptive | 29 | 29 | 0.877 | 0.135 | 0.072 | 0.735 | passed |
| 6 | 5 | 1 | sample-random | 64 | 64 | 1.690 | 0.025 | 0.000 | 1.658 | passed |
| 6 | 5 | 1 | baseline | 64 | 64 | 1.743 | 0.025 | 0.000 | 1.712 | passed |
| 7 | 1 | 0 | filter | 9 | 9 | 0.338 | 0.093 | 0.000 | 0.231 | passed |
| 7 | 1 | 0 | filter-adaptive | 7 | 7 | 0.309 | 0.118 | 0.020 | 0.185 | passed |
| 7 | 1 | 0 | sample-random | 128 | 128 | 3.435 | 0.050 | 0.000 | 3.379 | passed |
| 7 | 1 | 0 | baseline | 128 | 128 | 3.412 | 0.046 | 0.000 | 3.359 | passed |
| 7 | 1 | 1 | filter-adaptive | 7 | 7 | 0.308 | 0.119 | 0.021 | 0.183 | passed |
| 7 | 1 | 1 | sample-random | 128 | 128 | 3.432 | 0.046 | 0.000 | 3.380 | passed |
| 7 | 1 | 1 | filter | 9 | 9 | 0.344 | 0.095 | 0.000 | 0.242 | passed |
| 7 | 1 | 1 | baseline | 128 | 128 | 3.547 | 0.046 | 0.000 | 3.495 | passed |
| 7 | 3 | 0 | filter-adaptive | 20 | 20 | 0.728 | 0.182 | 0.074 | 0.530 | passed |
| 7 | 3 | 0 | filter | 21 | 21 | 0.727 | 0.159 | 0.000 | 0.562 | passed |
| 7 | 3 | 0 | baseline | 128 | 128 | 3.581 | 0.049 | 0.000 | 3.527 | passed |
| 7 | 3 | 0 | sample-random | 128 | 128 | 3.657 | 0.058 | 0.000 | 3.587 | passed |
| 7 | 3 | 1 | baseline | 128 | 128 | 3.413 | 0.048 | 0.000 | 3.359 | passed |
| 7 | 3 | 1 | filter | 21 | 21 | 0.716 | 0.098 | 0.000 | 0.611 | passed |
| 7 | 3 | 1 | filter-adaptive | 20 | 20 | 0.723 | 0.183 | 0.073 | 0.533 | passed |
| 7 | 3 | 1 | sample-random | 128 | 128 | 3.527 | 0.049 | 0.000 | 3.472 | passed |
| 7 | 5 | 0 | filter-adaptive | 36 | 36 | 1.241 | 0.246 | 0.129 | 0.978 | passed |
| 7 | 5 | 0 | baseline | 128 | 128 | 3.528 | 0.050 | 0.000 | 3.472 | passed |
| 7 | 5 | 0 | filter | 37 | 37 | 1.102 | 0.103 | 0.000 | 0.992 | passed |
| 7 | 5 | 0 | sample-random | 128 | 128 | 3.554 | 0.049 | 0.000 | 3.498 | passed |
| 7 | 5 | 1 | sample-random | 128 | 128 | 3.579 | 0.049 | 0.000 | 3.524 | passed |
| 7 | 5 | 1 | filter | 37 | 37 | 1.109 | 0.104 | 0.000 | 0.997 | passed |
| 7 | 5 | 1 | filter-adaptive | 36 | 36 | 1.253 | 0.238 | 0.125 | 1.008 | passed |
| 7 | 5 | 1 | baseline | 128 | 128 | 3.554 | 0.048 | 0.000 | 3.500 | passed |
| 8 | 1 | 0 | sample-random | 180 | 180 | 4.911 | 0.095 | 0.000 | 4.801 | passed |
| 8 | 1 | 0 | filter-adaptive | 13 | 13 | 0.577 | 0.217 | 0.026 | 0.353 | passed |
| 8 | 1 | 0 | filter | 17 | 17 | 0.657 | 0.189 | 0.000 | 0.461 | passed |
| 8 | 1 | 0 | baseline | 256 | 256 | 6.953 | 0.097 | 0.000 | 6.850 | passed |
| 8 | 1 | 1 | sample-random | 180 | 180 | 4.672 | 0.097 | 0.000 | 4.569 | passed |
| 8 | 1 | 1 | filter | 17 | 17 | 0.705 | 0.254 | 0.000 | 0.443 | passed |
| 8 | 1 | 1 | baseline | 256 | 256 | 6.701 | 0.094 | 0.000 | 6.601 | passed |
| 8 | 1 | 1 | filter-adaptive | 13 | 13 | 0.565 | 0.214 | 0.025 | 0.345 | passed |
| 8 | 3 | 0 | baseline | 256 | 256 | 6.749 | 0.098 | 0.000 | 6.634 | passed |
| 8 | 3 | 0 | filter-adaptive | 34 | 34 | 1.140 | 0.273 | 0.074 | 0.860 | passed |
| 8 | 3 | 0 | sample-random | 180 | 180 | 4.787 | 0.092 | 0.000 | 4.689 | passed |
| 8 | 3 | 0 | filter | 35 | 35 | 1.089 | 0.196 | 0.000 | 0.886 | passed |
| 8 | 3 | 1 | filter | 35 | 35 | 1.043 | 0.192 | 0.000 | 0.843 | passed |
| 8 | 3 | 1 | filter-adaptive | 34 | 34 | 1.204 | 0.276 | 0.074 | 0.921 | passed |
| 8 | 3 | 1 | sample-random | 180 | 180 | 4.802 | 0.093 | 0.000 | 4.703 | passed |
| 8 | 3 | 1 | baseline | 256 | 256 | 6.804 | 0.098 | 0.000 | 6.697 | passed |
| 8 | 5 | 0 | sample-random | 180 | 180 | 4.845 | 0.093 | 0.000 | 4.734 | passed |
| 8 | 5 | 0 | filter | 58 | 58 | 1.733 | 0.206 | 0.000 | 1.520 | passed |
| 8 | 5 | 0 | baseline | 256 | 256 | 6.784 | 0.095 | 0.000 | 6.683 | passed |
| 8 | 5 | 0 | filter-adaptive | 58 | 58 | 2.073 | 0.512 | 0.300 | 1.553 | passed |
| 8 | 5 | 1 | filter-adaptive | 58 | 58 | 1.970 | 0.459 | 0.250 | 1.504 | passed |
| 8 | 5 | 1 | sample-random | 180 | 180 | 4.932 | 0.095 | 0.000 | 4.830 | passed |
| 8 | 5 | 1 | filter | 58 | 58 | 1.789 | 0.211 | 0.000 | 1.571 | passed |
| 8 | 5 | 1 | baseline | 256 | 256 | 6.786 | 0.096 | 0.000 | 6.684 | passed |
| 9 | 1 | 0 | baseline | 512 | 512 | 13.682 | 0.195 | 0.000 | 13.473 | passed |
| 9 | 1 | 0 | filter | 33 | 33 | 1.216 | 0.370 | 0.000 | 0.839 | passed |
| 9 | 1 | 0 | sample-random | 359 | 359 | 9.644 | 0.194 | 0.000 | 9.443 | passed |
| 9 | 1 | 0 | filter-adaptive | 33 | 33 | 1.294 | 0.413 | 0.026 | 0.875 | passed |
| 9 | 1 | 1 | baseline | 512 | 512 | 13.932 | 0.209 | 0.000 | 13.717 | passed |
| 9 | 1 | 1 | sample-random | 359 | 359 | 9.710 | 0.191 | 0.000 | 9.513 | passed |
| 9 | 1 | 1 | filter | 33 | 33 | 1.264 | 0.376 | 0.000 | 0.881 | passed |
| 9 | 1 | 1 | filter-adaptive | 33 | 33 | 1.317 | 0.419 | 0.027 | 0.890 | passed |
| 9 | 3 | 0 | sample-random | 359 | 359 | 10.031 | 0.201 | 0.000 | 9.814 | passed |
| 9 | 3 | 0 | filter | 75 | 75 | 2.406 | 0.392 | 0.000 | 2.007 | passed |
| 9 | 3 | 0 | baseline | 512 | 512 | 14.222 | 0.202 | 0.000 | 14.013 | passed |
| 9 | 3 | 0 | filter-adaptive | 75 | 75 | 2.745 | 0.665 | 0.256 | 2.073 | passed |
| 9 | 3 | 1 | baseline | 512 | 512 | 14.100 | 0.196 | 0.000 | 13.898 | passed |
| 9 | 3 | 1 | filter | 75 | 75 | 2.548 | 0.454 | 0.000 | 2.087 | passed |
| 9 | 3 | 1 | filter-adaptive | 75 | 75 | 2.737 | 0.658 | 0.247 | 2.071 | passed |
| 9 | 3 | 1 | sample-random | 359 | 359 | 10.214 | 0.206 | 0.000 | 10.002 | passed |
| 9 | 5 | 0 | filter | 127 | 127 | 3.813 | 0.403 | 0.000 | 3.391 | passed |
| 9 | 5 | 0 | sample-random | 359 | 359 | 10.046 | 0.192 | 0.000 | 9.848 | passed |
| 9 | 5 | 0 | baseline | 512 | 512 | 14.630 | 0.196 | 0.000 | 14.427 | passed |
| 9 | 5 | 0 | filter-adaptive | 127 | 127 | 4.407 | 0.981 | 0.556 | 3.417 | passed |
| 9 | 5 | 1 | filter-adaptive | 127 | 127 | 4.413 | 0.961 | 0.482 | 3.444 | passed |
| 9 | 5 | 1 | baseline | 512 | 512 | 14.324 | 0.204 | 0.000 | 14.113 | passed |
| 9 | 5 | 1 | sample-random | 359 | 359 | 9.857 | 0.204 | 0.000 | 9.646 | passed |
| 9 | 5 | 1 | filter | 127 | 127 | 3.857 | 0.408 | 0.000 | 3.441 | passed |

Raw timings and fallback decisions (local run data) · Full measurements (local run data) · Chart recipes (local run data)

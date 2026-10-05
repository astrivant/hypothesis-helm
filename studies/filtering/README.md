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
| 6 | 1 | 0 | baseline | 64 | 64 | 2.081 | 0.033 | 0.000 | 1.976 | passed |
| 6 | 1 | 0 | sample-random | 64 | 64 | 2.023 | 0.037 | 0.000 | 1.979 | passed |
| 6 | 1 | 0 | filter-adaptive | 5 | 5 | 0.265 | 0.102 | 0.026 | 0.156 | passed |
| 6 | 1 | 0 | filter | 5 | 5 | 0.236 | 0.074 | 0.000 | 0.156 | passed |
| 6 | 1 | 1 | baseline | 64 | 64 | 2.023 | 0.033 | 0.000 | 1.982 | passed |
| 6 | 1 | 1 | sample-random | 64 | 64 | 2.068 | 0.071 | 0.000 | 1.991 | passed |
| 6 | 1 | 1 | filter | 5 | 5 | 0.236 | 0.074 | 0.000 | 0.156 | passed |
| 6 | 1 | 1 | filter-adaptive | 5 | 5 | 0.265 | 0.102 | 0.026 | 0.157 | passed |
| 6 | 3 | 0 | baseline | 64 | 64 | 2.024 | 0.035 | 0.000 | 1.972 | passed |
| 6 | 3 | 0 | filter | 17 | 17 | 0.615 | 0.079 | 0.000 | 0.527 | passed |
| 6 | 3 | 0 | filter-adaptive | 17 | 17 | 0.685 | 0.142 | 0.061 | 0.535 | passed |
| 6 | 3 | 0 | sample-random | 64 | 64 | 2.025 | 0.034 | 0.000 | 1.983 | passed |
| 6 | 3 | 1 | filter-adaptive | 17 | 17 | 0.673 | 0.142 | 0.060 | 0.522 | passed |
| 6 | 3 | 1 | baseline | 64 | 64 | 2.033 | 0.033 | 0.000 | 1.992 | passed |
| 6 | 3 | 1 | sample-random | 64 | 64 | 2.044 | 0.036 | 0.000 | 2.001 | passed |
| 6 | 3 | 1 | filter | 17 | 17 | 0.632 | 0.077 | 0.000 | 0.548 | passed |
| 6 | 5 | 0 | filter | 29 | 29 | 1.027 | 0.082 | 0.000 | 0.925 | passed |
| 6 | 5 | 0 | sample-random | 64 | 64 | 2.084 | 0.036 | 0.000 | 2.040 | passed |
| 6 | 5 | 0 | filter-adaptive | 29 | 29 | 1.126 | 0.194 | 0.099 | 0.923 | passed |
| 6 | 5 | 0 | baseline | 64 | 64 | 2.214 | 0.037 | 0.000 | 2.170 | passed |
| 6 | 5 | 1 | filter | 29 | 29 | 0.993 | 0.080 | 0.000 | 0.905 | passed |
| 6 | 5 | 1 | filter-adaptive | 29 | 29 | 1.116 | 0.187 | 0.098 | 0.921 | passed |
| 6 | 5 | 1 | sample-random | 64 | 64 | 2.056 | 0.035 | 0.000 | 2.014 | passed |
| 6 | 5 | 1 | baseline | 64 | 64 | 2.051 | 0.036 | 0.000 | 2.008 | passed |
| 7 | 1 | 0 | filter | 9 | 9 | 0.447 | 0.132 | 0.000 | 0.299 | passed |
| 7 | 1 | 0 | filter-adaptive | 7 | 7 | 0.394 | 0.169 | 0.029 | 0.217 | passed |
| 7 | 1 | 0 | sample-random | 128 | 128 | 4.124 | 0.070 | 0.000 | 4.047 | passed |
| 7 | 1 | 0 | baseline | 128 | 128 | 4.120 | 0.071 | 0.000 | 4.041 | passed |
| 7 | 1 | 1 | filter-adaptive | 7 | 7 | 0.398 | 0.169 | 0.032 | 0.222 | passed |
| 7 | 1 | 1 | sample-random | 128 | 128 | 4.165 | 0.070 | 0.000 | 4.089 | passed |
| 7 | 1 | 1 | filter | 9 | 9 | 0.434 | 0.134 | 0.000 | 0.292 | passed |
| 7 | 1 | 1 | baseline | 128 | 128 | 4.147 | 0.067 | 0.000 | 4.072 | passed |
| 7 | 3 | 0 | filter-adaptive | 20 | 20 | 0.910 | 0.245 | 0.099 | 0.645 | passed |
| 7 | 3 | 0 | filter | 21 | 21 | 0.845 | 0.144 | 0.000 | 0.693 | passed |
| 7 | 3 | 0 | baseline | 128 | 128 | 4.133 | 0.069 | 0.000 | 4.055 | passed |
| 7 | 3 | 0 | sample-random | 128 | 128 | 4.122 | 0.071 | 0.000 | 4.044 | passed |
| 7 | 3 | 1 | baseline | 128 | 128 | 4.090 | 0.068 | 0.000 | 4.015 | passed |
| 7 | 3 | 1 | filter | 21 | 21 | 0.821 | 0.142 | 0.000 | 0.670 | passed |
| 7 | 3 | 1 | filter-adaptive | 20 | 20 | 0.889 | 0.246 | 0.100 | 0.635 | passed |
| 7 | 3 | 1 | sample-random | 128 | 128 | 4.013 | 0.066 | 0.000 | 3.940 | passed |
| 7 | 5 | 0 | filter-adaptive | 36 | 36 | 1.462 | 0.326 | 0.173 | 1.114 | passed |
| 7 | 5 | 0 | baseline | 128 | 128 | 4.028 | 0.067 | 0.000 | 3.954 | passed |
| 7 | 5 | 0 | filter | 37 | 37 | 1.299 | 0.145 | 0.000 | 1.146 | passed |
| 7 | 5 | 0 | sample-random | 128 | 128 | 4.027 | 0.069 | 0.000 | 3.951 | passed |
| 7 | 5 | 1 | sample-random | 128 | 128 | 4.139 | 0.067 | 0.000 | 4.065 | passed |
| 7 | 5 | 1 | filter | 37 | 37 | 1.293 | 0.144 | 0.000 | 1.140 | passed |
| 7 | 5 | 1 | filter-adaptive | 36 | 36 | 1.449 | 0.325 | 0.174 | 1.116 | passed |
| 7 | 5 | 1 | baseline | 128 | 128 | 3.994 | 0.070 | 0.000 | 3.917 | passed |
| 8 | 1 | 0 | sample-random | 180 | 180 | 5.898 | 0.133 | 0.000 | 5.748 | passed |
| 8 | 1 | 0 | filter-adaptive | 13 | 13 | 0.715 | 0.301 | 0.035 | 0.406 | passed |
| 8 | 1 | 0 | filter | 17 | 17 | 0.811 | 0.263 | 0.000 | 0.541 | passed |
| 8 | 1 | 0 | baseline | 256 | 256 | 8.105 | 0.136 | 0.000 | 7.963 | passed |
| 8 | 1 | 1 | sample-random | 180 | 180 | 5.705 | 0.133 | 0.000 | 5.565 | passed |
| 8 | 1 | 1 | filter | 17 | 17 | 0.854 | 0.300 | 0.000 | 0.545 | passed |
| 8 | 1 | 1 | baseline | 256 | 256 | 8.145 | 0.138 | 0.000 | 8.001 | passed |
| 8 | 1 | 1 | filter-adaptive | 13 | 13 | 0.725 | 0.301 | 0.034 | 0.416 | passed |
| 8 | 3 | 0 | baseline | 256 | 256 | 8.102 | 0.137 | 0.000 | 7.947 | passed |
| 8 | 3 | 0 | filter-adaptive | 34 | 34 | 1.470 | 0.388 | 0.106 | 1.074 | passed |
| 8 | 3 | 0 | sample-random | 180 | 180 | 5.766 | 0.133 | 0.000 | 5.625 | passed |
| 8 | 3 | 0 | filter | 35 | 35 | 1.387 | 0.277 | 0.000 | 1.102 | passed |
| 8 | 3 | 1 | filter | 35 | 35 | 1.406 | 0.272 | 0.000 | 1.126 | passed |
| 8 | 3 | 1 | filter-adaptive | 34 | 34 | 1.518 | 0.392 | 0.105 | 1.118 | passed |
| 8 | 3 | 1 | sample-random | 180 | 180 | 5.891 | 0.135 | 0.000 | 5.749 | passed |
| 8 | 3 | 1 | baseline | 256 | 256 | 8.363 | 0.150 | 0.000 | 8.204 | passed |
| 8 | 5 | 0 | sample-random | 180 | 180 | 5.782 | 0.139 | 0.000 | 5.620 | passed |
| 8 | 5 | 0 | filter | 58 | 58 | 2.142 | 0.283 | 0.000 | 1.849 | passed |
| 8 | 5 | 0 | baseline | 256 | 256 | 8.142 | 0.139 | 0.000 | 7.994 | passed |
| 8 | 5 | 0 | filter-adaptive | 58 | 58 | 2.500 | 0.687 | 0.396 | 1.805 | passed |
| 8 | 5 | 1 | filter-adaptive | 58 | 58 | 2.448 | 0.636 | 0.347 | 1.802 | passed |
| 8 | 5 | 1 | sample-random | 180 | 180 | 5.717 | 0.135 | 0.000 | 5.575 | passed |
| 8 | 5 | 1 | filter | 58 | 58 | 2.142 | 0.285 | 0.000 | 1.849 | passed |
| 8 | 5 | 1 | baseline | 256 | 256 | 8.083 | 0.138 | 0.000 | 7.937 | passed |
| 9 | 1 | 0 | baseline | 512 | 512 | 16.396 | 0.290 | 0.000 | 16.088 | passed |
| 9 | 1 | 0 | filter | 33 | 33 | 1.575 | 0.533 | 0.000 | 1.034 | passed |
| 9 | 1 | 0 | sample-random | 359 | 359 | 11.481 | 0.280 | 0.000 | 11.193 | passed |
| 9 | 1 | 0 | filter-adaptive | 33 | 33 | 1.624 | 0.576 | 0.036 | 1.041 | passed |
| 9 | 1 | 1 | baseline | 512 | 512 | 15.999 | 0.283 | 0.000 | 15.708 | passed |
| 9 | 1 | 1 | sample-random | 359 | 359 | 11.415 | 0.272 | 0.000 | 11.136 | passed |
| 9 | 1 | 1 | filter | 33 | 33 | 1.599 | 0.551 | 0.000 | 1.041 | passed |
| 9 | 1 | 1 | filter-adaptive | 33 | 33 | 1.592 | 0.559 | 0.034 | 1.025 | passed |
| 9 | 3 | 0 | sample-random | 359 | 359 | 11.490 | 0.267 | 0.000 | 11.204 | passed |
| 9 | 3 | 0 | filter | 75 | 75 | 2.871 | 0.537 | 0.000 | 2.326 | passed |
| 9 | 3 | 0 | baseline | 512 | 512 | 16.242 | 0.285 | 0.000 | 15.949 | passed |
| 9 | 3 | 0 | filter-adaptive | 75 | 75 | 3.416 | 0.941 | 0.347 | 2.467 | passed |
| 9 | 3 | 1 | baseline | 512 | 512 | 16.653 | 0.286 | 0.000 | 16.360 | passed |
| 9 | 3 | 1 | filter | 75 | 75 | 3.018 | 0.587 | 0.000 | 2.422 | passed |
| 9 | 3 | 1 | filter-adaptive | 75 | 75 | 3.299 | 0.912 | 0.349 | 2.378 | passed |
| 9 | 3 | 1 | sample-random | 359 | 359 | 11.818 | 0.276 | 0.000 | 11.535 | passed |
| 9 | 5 | 0 | filter | 127 | 127 | 4.769 | 0.624 | 0.000 | 4.116 | passed |
| 9 | 5 | 0 | sample-random | 359 | 359 | 11.785 | 0.284 | 0.000 | 11.493 | passed |
| 9 | 5 | 0 | baseline | 512 | 512 | 16.860 | 0.295 | 0.000 | 16.557 | passed |
| 9 | 5 | 0 | filter-adaptive | 127 | 127 | 5.307 | 1.302 | 0.705 | 3.995 | passed |
| 9 | 5 | 1 | filter-adaptive | 127 | 127 | 5.388 | 1.294 | 0.666 | 4.084 | passed |
| 9 | 5 | 1 | baseline | 512 | 512 | 16.673 | 0.281 | 0.000 | 16.384 | passed |
| 9 | 5 | 1 | sample-random | 359 | 359 | 11.547 | 0.272 | 0.000 | 11.267 | passed |
| 9 | 5 | 1 | filter | 127 | 127 | 4.585 | 0.560 | 0.000 | 4.016 | passed |

Raw timings and fallback decisions (local run data) · Full measurements (local run data) · Chart recipes (local run data)

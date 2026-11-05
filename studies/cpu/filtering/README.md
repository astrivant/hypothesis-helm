# Filtering load test

<!-- toc:start -->
**Table of contents**

- [Filtering load test](#filtering-load-test)
<!-- toc:end -->

[Theory and conditions](<../../../docs/adaptive-filtering/README.md#computational-cost>)

A gate is a template `if` condition. Depth counts nested conditions required to reach the innermost branch.

![Total runtime](filtering-runtime.png)

![Planning runtime](filtering-planning.png)

![Completed work](filtering-completed.png)

![Phase costs](filtering-phases.png)

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
| 6 | 1 | 0 | baseline | 64 | 64 | 2.785 | 0.041 | 0.000 | 2.660 | passed |
| 6 | 1 | 0 | sample-random | 64 | 64 | 2.713 | 0.042 | 0.000 | 2.664 | passed |
| 6 | 1 | 0 | filter-adaptive | 5 | 5 | 0.349 | 0.126 | 0.034 | 0.214 | passed |
| 6 | 1 | 0 | filter | 5 | 5 | 0.310 | 0.089 | 0.000 | 0.213 | passed |
| 6 | 1 | 1 | baseline | 64 | 64 | 2.740 | 0.041 | 0.000 | 2.691 | passed |
| 6 | 1 | 1 | sample-random | 64 | 64 | 2.798 | 0.087 | 0.000 | 2.703 | passed |
| 6 | 1 | 1 | filter | 5 | 5 | 0.308 | 0.089 | 0.000 | 0.210 | passed |
| 6 | 1 | 1 | filter-adaptive | 5 | 5 | 0.352 | 0.124 | 0.032 | 0.219 | passed |
| 6 | 3 | 0 | baseline | 64 | 64 | 2.819 | 0.042 | 0.000 | 2.755 | passed |
| 6 | 3 | 0 | filter | 17 | 17 | 0.830 | 0.095 | 0.000 | 0.724 | passed |
| 6 | 3 | 0 | filter-adaptive | 17 | 17 | 0.930 | 0.173 | 0.072 | 0.748 | passed |
| 6 | 3 | 0 | sample-random | 64 | 64 | 2.762 | 0.043 | 0.000 | 2.711 | passed |
| 6 | 3 | 1 | filter-adaptive | 17 | 17 | 0.936 | 0.175 | 0.074 | 0.753 | passed |
| 6 | 3 | 1 | baseline | 64 | 64 | 2.751 | 0.042 | 0.000 | 2.699 | passed |
| 6 | 3 | 1 | sample-random | 64 | 64 | 2.758 | 0.043 | 0.000 | 2.707 | passed |
| 6 | 3 | 1 | filter | 17 | 17 | 0.831 | 0.094 | 0.000 | 0.725 | passed |
| 6 | 5 | 0 | filter | 29 | 29 | 1.343 | 0.099 | 0.000 | 1.217 | passed |
| 6 | 5 | 0 | sample-random | 64 | 64 | 2.788 | 0.044 | 0.000 | 2.735 | passed |
| 6 | 5 | 0 | filter-adaptive | 29 | 29 | 1.480 | 0.229 | 0.122 | 1.241 | passed |
| 6 | 5 | 0 | baseline | 64 | 64 | 2.789 | 0.044 | 0.000 | 2.736 | passed |
| 6 | 5 | 1 | filter | 29 | 29 | 1.361 | 0.100 | 0.000 | 1.252 | passed |
| 6 | 5 | 1 | filter-adaptive | 29 | 29 | 1.468 | 0.226 | 0.119 | 1.231 | passed |
| 6 | 5 | 1 | sample-random | 64 | 64 | 2.752 | 0.044 | 0.000 | 2.700 | passed |
| 6 | 5 | 1 | baseline | 64 | 64 | 2.731 | 0.045 | 0.000 | 2.678 | passed |
| 7 | 1 | 0 | filter | 9 | 9 | 0.571 | 0.164 | 0.000 | 0.386 | passed |
| 7 | 1 | 0 | filter-adaptive | 7 | 7 | 0.510 | 0.200 | 0.033 | 0.299 | passed |
| 7 | 1 | 0 | sample-random | 128 | 128 | 5.458 | 0.082 | 0.000 | 5.367 | passed |
| 7 | 1 | 0 | baseline | 128 | 128 | 5.562 | 0.081 | 0.000 | 5.471 | passed |
| 7 | 1 | 1 | filter-adaptive | 7 | 7 | 0.511 | 0.203 | 0.034 | 0.299 | passed |
| 7 | 1 | 1 | sample-random | 128 | 128 | 5.540 | 0.083 | 0.000 | 5.449 | passed |
| 7 | 1 | 1 | filter | 9 | 9 | 0.557 | 0.163 | 0.000 | 0.385 | passed |
| 7 | 1 | 1 | baseline | 128 | 128 | 5.522 | 0.081 | 0.000 | 5.433 | passed |
| 7 | 3 | 0 | filter-adaptive | 20 | 20 | 1.195 | 0.302 | 0.119 | 0.867 | passed |
| 7 | 3 | 0 | filter | 21 | 21 | 1.152 | 0.231 | 0.000 | 0.911 | passed |
| 7 | 3 | 0 | baseline | 128 | 128 | 5.541 | 0.083 | 0.000 | 5.450 | passed |
| 7 | 3 | 0 | sample-random | 128 | 128 | 5.509 | 0.084 | 0.000 | 5.417 | passed |
| 7 | 3 | 1 | baseline | 128 | 128 | 5.574 | 0.081 | 0.000 | 5.484 | passed |
| 7 | 3 | 1 | filter | 21 | 21 | 1.101 | 0.170 | 0.000 | 0.920 | passed |
| 7 | 3 | 1 | filter-adaptive | 20 | 20 | 1.179 | 0.301 | 0.121 | 0.867 | passed |
| 7 | 3 | 1 | sample-random | 128 | 128 | 5.520 | 0.082 | 0.000 | 5.429 | passed |
| 7 | 5 | 0 | filter-adaptive | 36 | 36 | 1.960 | 0.403 | 0.212 | 1.530 | passed |
| 7 | 5 | 0 | baseline | 128 | 128 | 5.523 | 0.084 | 0.000 | 5.431 | passed |
| 7 | 5 | 0 | filter | 37 | 37 | 1.770 | 0.177 | 0.000 | 1.583 | passed |
| 7 | 5 | 0 | sample-random | 128 | 128 | 5.625 | 0.084 | 0.000 | 5.533 | passed |
| 7 | 5 | 1 | sample-random | 128 | 128 | 5.563 | 0.084 | 0.000 | 5.470 | passed |
| 7 | 5 | 1 | filter | 37 | 37 | 1.784 | 0.177 | 0.000 | 1.596 | passed |
| 7 | 5 | 1 | filter-adaptive | 36 | 36 | 1.974 | 0.406 | 0.215 | 1.557 | passed |
| 7 | 5 | 1 | baseline | 128 | 128 | 5.597 | 0.084 | 0.000 | 5.504 | passed |
| 8 | 1 | 0 | sample-random | 180 | 180 | 7.990 | 0.162 | 0.000 | 7.806 | passed |
| 8 | 1 | 0 | filter-adaptive | 13 | 13 | 0.929 | 0.369 | 0.041 | 0.551 | passed |
| 8 | 1 | 0 | filter | 17 | 17 | 1.069 | 0.326 | 0.000 | 0.734 | passed |
| 8 | 1 | 0 | baseline | 256 | 256 | 11.110 | 0.166 | 0.000 | 10.935 | passed |
| 8 | 1 | 1 | sample-random | 180 | 180 | 7.849 | 0.163 | 0.000 | 7.676 | passed |
| 8 | 1 | 1 | filter | 17 | 17 | 1.083 | 0.322 | 0.000 | 0.750 | passed |
| 8 | 1 | 1 | baseline | 256 | 256 | 11.086 | 0.168 | 0.000 | 10.909 | passed |
| 8 | 1 | 1 | filter-adaptive | 13 | 13 | 0.925 | 0.366 | 0.041 | 0.548 | passed |
| 8 | 3 | 0 | baseline | 256 | 256 | 11.217 | 0.167 | 0.000 | 11.025 | passed |
| 8 | 3 | 0 | filter-adaptive | 34 | 34 | 1.954 | 0.480 | 0.129 | 1.464 | passed |
| 8 | 3 | 0 | sample-random | 180 | 180 | 7.952 | 0.170 | 0.000 | 7.772 | passed |
| 8 | 3 | 0 | filter | 35 | 35 | 1.915 | 0.339 | 0.000 | 1.565 | passed |
| 8 | 3 | 1 | filter | 35 | 35 | 1.858 | 0.339 | 0.000 | 1.508 | passed |
| 8 | 3 | 1 | filter-adaptive | 34 | 34 | 1.940 | 0.481 | 0.129 | 1.450 | passed |
| 8 | 3 | 1 | sample-random | 180 | 180 | 7.872 | 0.163 | 0.000 | 7.699 | passed |
| 8 | 3 | 1 | baseline | 256 | 256 | 11.202 | 0.168 | 0.000 | 11.025 | passed |
| 8 | 5 | 0 | sample-random | 180 | 180 | 7.971 | 0.173 | 0.000 | 7.769 | passed |
| 8 | 5 | 0 | filter | 58 | 58 | 2.921 | 0.405 | 0.000 | 2.506 | passed |
| 8 | 5 | 0 | baseline | 256 | 256 | 11.179 | 0.168 | 0.000 | 11.001 | passed |
| 8 | 5 | 0 | filter-adaptive | 58 | 58 | 3.304 | 0.790 | 0.429 | 2.503 | passed |
| 8 | 5 | 1 | filter-adaptive | 58 | 58 | 3.346 | 0.789 | 0.428 | 2.545 | passed |
| 8 | 5 | 1 | sample-random | 180 | 180 | 7.883 | 0.164 | 0.000 | 7.709 | passed |
| 8 | 5 | 1 | filter | 58 | 58 | 2.855 | 0.349 | 0.000 | 2.495 | passed |
| 8 | 5 | 1 | baseline | 256 | 256 | 11.325 | 0.168 | 0.000 | 11.147 | passed |
| 9 | 1 | 0 | baseline | 512 | 512 | 22.404 | 0.353 | 0.000 | 22.027 | passed |
| 9 | 1 | 0 | filter | 33 | 33 | 2.076 | 0.647 | 0.000 | 1.419 | passed |
| 9 | 1 | 0 | sample-random | 359 | 359 | 15.674 | 0.336 | 0.000 | 15.329 | passed |
| 9 | 1 | 0 | filter-adaptive | 33 | 33 | 2.124 | 0.717 | 0.043 | 1.398 | passed |
| 9 | 1 | 1 | baseline | 512 | 512 | 21.999 | 0.345 | 0.000 | 21.645 | passed |
| 9 | 1 | 1 | sample-random | 359 | 359 | 15.700 | 0.337 | 0.000 | 15.354 | passed |
| 9 | 1 | 1 | filter | 33 | 33 | 2.094 | 0.654 | 0.000 | 1.430 | passed |
| 9 | 1 | 1 | filter-adaptive | 33 | 33 | 2.122 | 0.698 | 0.043 | 1.415 | passed |
| 9 | 3 | 0 | sample-random | 359 | 359 | 15.721 | 0.337 | 0.000 | 15.358 | passed |
| 9 | 3 | 0 | filter | 75 | 75 | 3.902 | 0.682 | 0.000 | 3.209 | passed |
| 9 | 3 | 0 | baseline | 512 | 512 | 22.237 | 0.345 | 0.000 | 21.882 | passed |
| 9 | 3 | 0 | filter-adaptive | 75 | 75 | 4.436 | 1.192 | 0.440 | 3.234 | passed |
| 9 | 3 | 1 | baseline | 512 | 512 | 22.062 | 0.344 | 0.000 | 21.707 | passed |
| 9 | 3 | 1 | filter | 75 | 75 | 3.855 | 0.682 | 0.000 | 3.163 | passed |
| 9 | 3 | 1 | filter-adaptive | 75 | 75 | 4.394 | 1.126 | 0.429 | 3.258 | passed |
| 9 | 3 | 1 | sample-random | 359 | 359 | 15.628 | 0.337 | 0.000 | 15.281 | passed |
| 9 | 5 | 0 | filter | 127 | 127 | 6.142 | 0.711 | 0.000 | 5.401 | passed |
| 9 | 5 | 0 | sample-random | 359 | 359 | 15.695 | 0.339 | 0.000 | 15.347 | passed |
| 9 | 5 | 0 | baseline | 512 | 512 | 22.132 | 0.346 | 0.000 | 21.776 | passed |
| 9 | 5 | 0 | filter-adaptive | 127 | 127 | 7.017 | 1.553 | 0.827 | 5.453 | passed |
| 9 | 5 | 1 | filter-adaptive | 127 | 127 | 6.979 | 1.621 | 0.893 | 5.346 | passed |
| 9 | 5 | 1 | baseline | 512 | 512 | 22.118 | 0.346 | 0.000 | 21.762 | passed |
| 9 | 5 | 1 | sample-random | 359 | 359 | 15.466 | 0.346 | 0.000 | 15.111 | passed |
| 9 | 5 | 1 | filter | 127 | 127 | 6.085 | 0.701 | 0.000 | 5.372 | passed |

Raw timings and fallback decisions (local run data) · Full measurements (local run data) · Chart recipes (local run data)

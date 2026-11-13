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
| 6 | 1 | 0 | baseline | 64 | 64 | 2.925 | 0.043 | 0.000 | 2.795 | passed |
| 6 | 1 | 0 | sample-random | 64 | 64 | 2.821 | 0.042 | 0.000 | 2.771 | passed |
| 6 | 1 | 0 | filter-adaptive | 5 | 5 | 0.358 | 0.128 | 0.035 | 0.221 | passed |
| 6 | 1 | 0 | filter | 5 | 5 | 0.318 | 0.091 | 0.000 | 0.219 | passed |
| 6 | 1 | 1 | baseline | 64 | 64 | 2.833 | 0.041 | 0.000 | 2.783 | passed |
| 6 | 1 | 1 | sample-random | 64 | 64 | 2.929 | 0.109 | 0.000 | 2.812 | passed |
| 6 | 1 | 1 | filter | 5 | 5 | 0.318 | 0.090 | 0.000 | 0.220 | passed |
| 6 | 1 | 1 | filter-adaptive | 5 | 5 | 0.358 | 0.126 | 0.032 | 0.223 | passed |
| 6 | 3 | 0 | baseline | 64 | 64 | 2.848 | 0.043 | 0.000 | 2.781 | passed |
| 6 | 3 | 0 | filter | 17 | 17 | 0.850 | 0.095 | 0.000 | 0.746 | passed |
| 6 | 3 | 0 | filter-adaptive | 17 | 17 | 0.958 | 0.175 | 0.074 | 0.773 | passed |
| 6 | 3 | 0 | sample-random | 64 | 64 | 2.819 | 0.044 | 0.000 | 2.766 | passed |
| 6 | 3 | 1 | filter-adaptive | 17 | 17 | 0.913 | 0.174 | 0.073 | 0.730 | passed |
| 6 | 3 | 1 | baseline | 64 | 64 | 2.803 | 0.043 | 0.000 | 2.751 | passed |
| 6 | 3 | 1 | sample-random | 64 | 64 | 2.820 | 0.043 | 0.000 | 2.769 | passed |
| 6 | 3 | 1 | filter | 17 | 17 | 0.856 | 0.095 | 0.000 | 0.751 | passed |
| 6 | 5 | 0 | filter | 29 | 29 | 1.403 | 0.101 | 0.000 | 1.273 | passed |
| 6 | 5 | 0 | sample-random | 64 | 64 | 2.872 | 0.044 | 0.000 | 2.820 | passed |
| 6 | 5 | 0 | filter-adaptive | 29 | 29 | 1.513 | 0.230 | 0.121 | 1.274 | passed |
| 6 | 5 | 0 | baseline | 64 | 64 | 2.845 | 0.044 | 0.000 | 2.792 | passed |
| 6 | 5 | 1 | filter | 29 | 29 | 1.401 | 0.100 | 0.000 | 1.291 | passed |
| 6 | 5 | 1 | filter-adaptive | 29 | 29 | 1.530 | 0.229 | 0.122 | 1.290 | passed |
| 6 | 5 | 1 | sample-random | 64 | 64 | 2.864 | 0.044 | 0.000 | 2.811 | passed |
| 6 | 5 | 1 | baseline | 64 | 64 | 2.877 | 0.044 | 0.000 | 2.823 | passed |
| 7 | 1 | 0 | filter | 9 | 9 | 0.586 | 0.166 | 0.000 | 0.398 | passed |
| 7 | 1 | 0 | filter-adaptive | 7 | 7 | 0.526 | 0.203 | 0.033 | 0.312 | passed |
| 7 | 1 | 0 | sample-random | 128 | 128 | 5.667 | 0.082 | 0.000 | 5.576 | passed |
| 7 | 1 | 0 | baseline | 128 | 128 | 5.714 | 0.082 | 0.000 | 5.623 | passed |
| 7 | 1 | 1 | filter-adaptive | 7 | 7 | 0.534 | 0.221 | 0.049 | 0.303 | passed |
| 7 | 1 | 1 | sample-random | 128 | 128 | 5.601 | 0.082 | 0.000 | 5.511 | passed |
| 7 | 1 | 1 | filter | 9 | 9 | 0.577 | 0.165 | 0.000 | 0.401 | passed |
| 7 | 1 | 1 | baseline | 128 | 128 | 5.739 | 0.082 | 0.000 | 5.649 | passed |
| 7 | 3 | 0 | filter-adaptive | 20 | 20 | 1.213 | 0.303 | 0.120 | 0.885 | passed |
| 7 | 3 | 0 | filter | 21 | 21 | 1.155 | 0.235 | 0.000 | 0.911 | passed |
| 7 | 3 | 0 | baseline | 128 | 128 | 5.726 | 0.083 | 0.000 | 5.634 | passed |
| 7 | 3 | 0 | sample-random | 128 | 128 | 5.762 | 0.086 | 0.000 | 5.663 | passed |
| 7 | 3 | 1 | baseline | 128 | 128 | 5.741 | 0.084 | 0.000 | 5.649 | passed |
| 7 | 3 | 1 | filter | 21 | 21 | 1.142 | 0.172 | 0.000 | 0.958 | passed |
| 7 | 3 | 1 | filter-adaptive | 20 | 20 | 1.201 | 0.303 | 0.122 | 0.887 | passed |
| 7 | 3 | 1 | sample-random | 128 | 128 | 5.699 | 0.083 | 0.000 | 5.606 | passed |
| 7 | 5 | 0 | filter-adaptive | 36 | 36 | 2.004 | 0.410 | 0.216 | 1.567 | passed |
| 7 | 5 | 0 | baseline | 128 | 128 | 5.693 | 0.085 | 0.000 | 5.599 | passed |
| 7 | 5 | 0 | filter | 37 | 37 | 1.791 | 0.179 | 0.000 | 1.602 | passed |
| 7 | 5 | 0 | sample-random | 128 | 128 | 5.701 | 0.085 | 0.000 | 5.607 | passed |
| 7 | 5 | 1 | sample-random | 128 | 128 | 5.704 | 0.085 | 0.000 | 5.609 | passed |
| 7 | 5 | 1 | filter | 37 | 37 | 1.804 | 0.179 | 0.000 | 1.614 | passed |
| 7 | 5 | 1 | filter-adaptive | 36 | 36 | 1.999 | 0.408 | 0.216 | 1.581 | passed |
| 7 | 5 | 1 | baseline | 128 | 128 | 5.727 | 0.084 | 0.000 | 5.633 | passed |
| 8 | 1 | 0 | sample-random | 180 | 180 | 8.270 | 0.163 | 0.000 | 8.084 | passed |
| 8 | 1 | 0 | filter-adaptive | 13 | 13 | 0.970 | 0.373 | 0.044 | 0.587 | passed |
| 8 | 1 | 0 | filter | 17 | 17 | 1.085 | 0.328 | 0.000 | 0.747 | passed |
| 8 | 1 | 0 | baseline | 256 | 256 | 11.586 | 0.168 | 0.000 | 11.408 | passed |
| 8 | 1 | 1 | sample-random | 180 | 180 | 8.109 | 0.165 | 0.000 | 7.935 | passed |
| 8 | 1 | 1 | filter | 17 | 17 | 1.091 | 0.329 | 0.000 | 0.751 | passed |
| 8 | 1 | 1 | baseline | 256 | 256 | 11.491 | 0.167 | 0.000 | 11.315 | passed |
| 8 | 1 | 1 | filter-adaptive | 13 | 13 | 0.951 | 0.371 | 0.042 | 0.569 | passed |
| 8 | 3 | 0 | baseline | 256 | 256 | 11.285 | 0.168 | 0.000 | 11.091 | passed |
| 8 | 3 | 0 | filter-adaptive | 34 | 34 | 1.950 | 0.482 | 0.131 | 1.458 | passed |
| 8 | 3 | 0 | sample-random | 180 | 180 | 8.005 | 0.164 | 0.000 | 7.832 | passed |
| 8 | 3 | 0 | filter | 35 | 35 | 1.874 | 0.340 | 0.000 | 1.524 | passed |
| 8 | 3 | 1 | filter | 35 | 35 | 1.901 | 0.344 | 0.000 | 1.545 | passed |
| 8 | 3 | 1 | filter-adaptive | 34 | 34 | 1.985 | 0.488 | 0.132 | 1.487 | passed |
| 8 | 3 | 1 | sample-random | 180 | 180 | 8.175 | 0.164 | 0.000 | 8.002 | passed |
| 8 | 3 | 1 | baseline | 256 | 256 | 11.430 | 0.169 | 0.000 | 11.252 | passed |
| 8 | 5 | 0 | sample-random | 180 | 180 | 8.170 | 0.165 | 0.000 | 7.976 | passed |
| 8 | 5 | 0 | filter | 58 | 58 | 2.998 | 0.411 | 0.000 | 2.577 | passed |
| 8 | 5 | 0 | baseline | 256 | 256 | 11.368 | 0.169 | 0.000 | 11.189 | passed |
| 8 | 5 | 0 | filter-adaptive | 58 | 58 | 3.435 | 0.798 | 0.432 | 2.626 | passed |
| 8 | 5 | 1 | filter-adaptive | 58 | 58 | 3.445 | 0.806 | 0.438 | 2.627 | passed |
| 8 | 5 | 1 | sample-random | 180 | 180 | 8.115 | 0.167 | 0.000 | 7.938 | passed |
| 8 | 5 | 1 | filter | 58 | 58 | 2.958 | 0.353 | 0.000 | 2.594 | passed |
| 8 | 5 | 1 | baseline | 256 | 256 | 11.343 | 0.174 | 0.000 | 11.160 | passed |
| 9 | 1 | 0 | baseline | 512 | 512 | 22.541 | 0.346 | 0.000 | 22.172 | passed |
| 9 | 1 | 0 | filter | 33 | 33 | 2.108 | 0.661 | 0.000 | 1.437 | passed |
| 9 | 1 | 0 | sample-random | 359 | 359 | 15.852 | 0.338 | 0.000 | 15.505 | passed |
| 9 | 1 | 0 | filter-adaptive | 33 | 33 | 2.149 | 0.708 | 0.043 | 1.431 | passed |
| 9 | 1 | 1 | baseline | 512 | 512 | 22.858 | 0.350 | 0.000 | 22.498 | passed |
| 9 | 1 | 1 | sample-random | 359 | 359 | 16.019 | 0.348 | 0.000 | 15.662 | passed |
| 9 | 1 | 1 | filter | 33 | 33 | 2.123 | 0.653 | 0.000 | 1.459 | passed |
| 9 | 1 | 1 | filter-adaptive | 33 | 33 | 2.145 | 0.704 | 0.043 | 1.431 | passed |
| 9 | 3 | 0 | sample-random | 359 | 359 | 16.151 | 0.339 | 0.000 | 15.786 | passed |
| 9 | 3 | 0 | filter | 75 | 75 | 4.000 | 0.688 | 0.000 | 3.300 | passed |
| 9 | 3 | 0 | baseline | 512 | 512 | 23.053 | 0.349 | 0.000 | 22.694 | passed |
| 9 | 3 | 0 | filter-adaptive | 75 | 75 | 4.541 | 1.190 | 0.435 | 3.340 | passed |
| 9 | 3 | 1 | baseline | 512 | 512 | 22.854 | 0.347 | 0.000 | 22.497 | passed |
| 9 | 3 | 1 | filter | 75 | 75 | 3.953 | 0.687 | 0.000 | 3.256 | passed |
| 9 | 3 | 1 | filter-adaptive | 75 | 75 | 4.346 | 1.139 | 0.432 | 3.197 | passed |
| 9 | 3 | 1 | sample-random | 359 | 359 | 15.872 | 0.340 | 0.000 | 15.523 | passed |
| 9 | 5 | 0 | filter | 127 | 127 | 6.273 | 0.705 | 0.000 | 5.537 | passed |
| 9 | 5 | 0 | sample-random | 359 | 359 | 16.018 | 0.338 | 0.000 | 15.670 | passed |
| 9 | 5 | 0 | baseline | 512 | 512 | 22.698 | 0.350 | 0.000 | 22.337 | passed |
| 9 | 5 | 0 | filter-adaptive | 127 | 127 | 7.183 | 1.579 | 0.850 | 5.592 | passed |
| 9 | 5 | 1 | filter-adaptive | 127 | 127 | 7.291 | 1.648 | 0.899 | 5.631 | passed |
| 9 | 5 | 1 | baseline | 512 | 512 | 22.648 | 0.351 | 0.000 | 22.288 | passed |
| 9 | 5 | 1 | sample-random | 359 | 359 | 16.022 | 0.342 | 0.000 | 15.670 | passed |
| 9 | 5 | 1 | filter | 127 | 127 | 6.302 | 0.712 | 0.000 | 5.578 | passed |

Raw timings and fallback decisions (local run data) · Full measurements (local run data) · Chart recipes (local run data)

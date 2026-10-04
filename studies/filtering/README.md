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
| 6 | 1 | 0 | baseline | 64 | 64 | 2.760 | 0.051 | 0.000 | 2.621 | passed |
| 6 | 1 | 0 | sample-random | 64 | 64 | 2.556 | 0.050 | 0.000 | 2.497 | passed |
| 6 | 1 | 0 | filter-adaptive | 5 | 5 | 0.351 | 0.145 | 0.036 | 0.197 | passed |
| 6 | 1 | 0 | filter | 5 | 5 | 0.310 | 0.103 | 0.000 | 0.198 | passed |
| 6 | 1 | 1 | baseline | 64 | 64 | 2.544 | 0.049 | 0.000 | 2.486 | passed |
| 6 | 1 | 1 | sample-random | 64 | 64 | 2.588 | 0.093 | 0.000 | 2.487 | passed |
| 6 | 1 | 1 | filter | 5 | 5 | 0.311 | 0.104 | 0.000 | 0.198 | passed |
| 6 | 1 | 1 | filter-adaptive | 5 | 5 | 0.352 | 0.144 | 0.036 | 0.199 | passed |
| 6 | 3 | 0 | baseline | 64 | 64 | 2.550 | 0.050 | 0.000 | 2.476 | passed |
| 6 | 3 | 0 | filter | 17 | 17 | 0.789 | 0.111 | 0.000 | 0.668 | passed |
| 6 | 3 | 0 | filter-adaptive | 17 | 17 | 0.873 | 0.198 | 0.080 | 0.665 | passed |
| 6 | 3 | 0 | sample-random | 64 | 64 | 2.557 | 0.050 | 0.000 | 2.497 | passed |
| 6 | 3 | 1 | filter-adaptive | 17 | 17 | 0.879 | 0.199 | 0.082 | 0.670 | passed |
| 6 | 3 | 1 | baseline | 64 | 64 | 2.583 | 0.050 | 0.000 | 2.523 | passed |
| 6 | 3 | 1 | sample-random | 64 | 64 | 2.580 | 0.058 | 0.000 | 2.513 | passed |
| 6 | 3 | 1 | filter | 17 | 17 | 0.784 | 0.110 | 0.000 | 0.664 | passed |
| 6 | 5 | 0 | filter | 29 | 29 | 1.278 | 0.115 | 0.000 | 1.135 | passed |
| 6 | 5 | 0 | sample-random | 64 | 64 | 2.565 | 0.052 | 0.000 | 2.504 | passed |
| 6 | 5 | 0 | filter-adaptive | 29 | 29 | 1.398 | 0.256 | 0.132 | 1.132 | passed |
| 6 | 5 | 0 | baseline | 64 | 64 | 2.574 | 0.052 | 0.000 | 2.514 | passed |
| 6 | 5 | 1 | filter | 29 | 29 | 1.262 | 0.115 | 0.000 | 1.137 | passed |
| 6 | 5 | 1 | filter-adaptive | 29 | 29 | 1.398 | 0.256 | 0.133 | 1.132 | passed |
| 6 | 5 | 1 | sample-random | 64 | 64 | 2.560 | 0.052 | 0.000 | 2.499 | passed |
| 6 | 5 | 1 | baseline | 64 | 64 | 2.554 | 0.051 | 0.000 | 2.493 | passed |
| 7 | 1 | 0 | filter | 9 | 9 | 0.575 | 0.193 | 0.000 | 0.358 | passed |
| 7 | 1 | 0 | filter-adaptive | 7 | 7 | 0.520 | 0.235 | 0.037 | 0.275 | passed |
| 7 | 1 | 0 | sample-random | 128 | 128 | 5.075 | 0.098 | 0.000 | 4.968 | passed |
| 7 | 1 | 0 | baseline | 128 | 128 | 5.087 | 0.097 | 0.000 | 4.981 | passed |
| 7 | 1 | 1 | filter-adaptive | 7 | 7 | 0.524 | 0.237 | 0.038 | 0.277 | passed |
| 7 | 1 | 1 | sample-random | 128 | 128 | 5.150 | 0.099 | 0.000 | 5.042 | passed |
| 7 | 1 | 1 | filter | 9 | 9 | 0.560 | 0.192 | 0.000 | 0.357 | passed |
| 7 | 1 | 1 | baseline | 128 | 128 | 5.143 | 0.098 | 0.000 | 5.035 | passed |
| 7 | 3 | 0 | filter-adaptive | 20 | 20 | 1.152 | 0.343 | 0.132 | 0.783 | passed |
| 7 | 3 | 0 | filter | 21 | 21 | 1.030 | 0.201 | 0.000 | 0.819 | passed |
| 7 | 3 | 0 | baseline | 128 | 128 | 5.082 | 0.099 | 0.000 | 4.974 | passed |
| 7 | 3 | 0 | sample-random | 128 | 128 | 5.135 | 0.100 | 0.000 | 5.026 | passed |
| 7 | 3 | 1 | baseline | 128 | 128 | 5.088 | 0.099 | 0.000 | 4.979 | passed |
| 7 | 3 | 1 | filter | 21 | 21 | 1.043 | 0.201 | 0.000 | 0.832 | passed |
| 7 | 3 | 1 | filter-adaptive | 20 | 20 | 1.137 | 0.344 | 0.132 | 0.783 | passed |
| 7 | 3 | 1 | sample-random | 128 | 128 | 5.087 | 0.098 | 0.000 | 4.980 | passed |
| 7 | 5 | 0 | filter-adaptive | 36 | 36 | 1.907 | 0.458 | 0.236 | 1.420 | passed |
| 7 | 5 | 0 | baseline | 128 | 128 | 5.107 | 0.100 | 0.000 | 4.997 | passed |
| 7 | 5 | 0 | filter | 37 | 37 | 1.658 | 0.209 | 0.000 | 1.438 | passed |
| 7 | 5 | 0 | sample-random | 128 | 128 | 5.119 | 0.099 | 0.000 | 5.010 | passed |
| 7 | 5 | 1 | sample-random | 128 | 128 | 5.129 | 0.099 | 0.000 | 5.021 | passed |
| 7 | 5 | 1 | filter | 37 | 37 | 1.675 | 0.209 | 0.000 | 1.455 | passed |
| 7 | 5 | 1 | filter-adaptive | 36 | 36 | 1.874 | 0.460 | 0.236 | 1.404 | passed |
| 7 | 5 | 1 | baseline | 128 | 128 | 5.097 | 0.100 | 0.000 | 4.988 | passed |
| 8 | 1 | 0 | sample-random | 180 | 180 | 7.273 | 0.193 | 0.000 | 7.056 | passed |
| 8 | 1 | 0 | filter-adaptive | 13 | 13 | 0.960 | 0.435 | 0.046 | 0.514 | passed |
| 8 | 1 | 0 | filter | 17 | 17 | 1.058 | 0.382 | 0.000 | 0.666 | passed |
| 8 | 1 | 0 | baseline | 256 | 256 | 10.220 | 0.200 | 0.000 | 10.011 | passed |
| 8 | 1 | 1 | sample-random | 180 | 180 | 7.212 | 0.194 | 0.000 | 7.009 | passed |
| 8 | 1 | 1 | filter | 17 | 17 | 1.093 | 0.416 | 0.000 | 0.666 | passed |
| 8 | 1 | 1 | baseline | 256 | 256 | 10.203 | 0.198 | 0.000 | 9.996 | passed |
| 8 | 1 | 1 | filter-adaptive | 13 | 13 | 0.981 | 0.460 | 0.048 | 0.512 | passed |
| 8 | 3 | 0 | baseline | 256 | 256 | 10.237 | 0.198 | 0.000 | 10.012 | passed |
| 8 | 3 | 0 | filter-adaptive | 34 | 34 | 1.898 | 0.553 | 0.142 | 1.334 | passed |
| 8 | 3 | 0 | sample-random | 180 | 180 | 7.228 | 0.193 | 0.000 | 7.026 | passed |
| 8 | 3 | 0 | filter | 35 | 35 | 1.785 | 0.391 | 0.000 | 1.383 | passed |
| 8 | 3 | 1 | filter | 35 | 35 | 1.773 | 0.396 | 0.000 | 1.366 | passed |
| 8 | 3 | 1 | filter-adaptive | 34 | 34 | 1.901 | 0.547 | 0.140 | 1.344 | passed |
| 8 | 3 | 1 | sample-random | 180 | 180 | 7.302 | 0.195 | 0.000 | 7.098 | passed |
| 8 | 3 | 1 | baseline | 256 | 256 | 10.241 | 0.199 | 0.000 | 10.033 | passed |
| 8 | 5 | 0 | sample-random | 180 | 180 | 7.242 | 0.193 | 0.000 | 7.018 | passed |
| 8 | 5 | 0 | filter | 58 | 58 | 2.674 | 0.404 | 0.000 | 2.258 | passed |
| 8 | 5 | 0 | baseline | 256 | 256 | 10.268 | 0.197 | 0.000 | 10.061 | passed |
| 8 | 5 | 0 | filter-adaptive | 58 | 58 | 3.226 | 0.941 | 0.523 | 2.274 | passed |
| 8 | 5 | 1 | filter-adaptive | 58 | 58 | 3.185 | 0.902 | 0.467 | 2.271 | passed |
| 8 | 5 | 1 | sample-random | 180 | 180 | 7.260 | 0.192 | 0.000 | 7.058 | passed |
| 8 | 5 | 1 | filter | 58 | 58 | 2.713 | 0.409 | 0.000 | 2.293 | passed |
| 8 | 5 | 1 | baseline | 256 | 256 | 10.289 | 0.204 | 0.000 | 10.075 | passed |
| 9 | 1 | 0 | baseline | 512 | 512 | 20.567 | 0.411 | 0.000 | 20.131 | passed |
| 9 | 1 | 0 | filter | 33 | 33 | 2.068 | 0.760 | 0.000 | 1.298 | passed |
| 9 | 1 | 0 | sample-random | 359 | 359 | 14.448 | 0.396 | 0.000 | 14.043 | passed |
| 9 | 1 | 0 | filter-adaptive | 33 | 33 | 2.136 | 0.819 | 0.047 | 1.307 | passed |
| 9 | 1 | 1 | baseline | 512 | 512 | 20.368 | 0.406 | 0.000 | 19.953 | passed |
| 9 | 1 | 1 | sample-random | 359 | 359 | 14.404 | 0.395 | 0.000 | 14.000 | passed |
| 9 | 1 | 1 | filter | 33 | 33 | 2.086 | 0.795 | 0.000 | 1.281 | passed |
| 9 | 1 | 1 | filter-adaptive | 33 | 33 | 2.139 | 0.818 | 0.046 | 1.311 | passed |
| 9 | 3 | 0 | sample-random | 359 | 359 | 14.464 | 0.393 | 0.000 | 14.043 | passed |
| 9 | 3 | 0 | filter | 75 | 75 | 3.787 | 0.799 | 0.000 | 2.977 | passed |
| 9 | 3 | 0 | baseline | 512 | 512 | 20.426 | 0.408 | 0.000 | 20.009 | passed |
| 9 | 3 | 0 | filter-adaptive | 75 | 75 | 4.227 | 1.285 | 0.468 | 2.932 | passed |
| 9 | 3 | 1 | baseline | 512 | 512 | 20.367 | 0.413 | 0.000 | 19.944 | passed |
| 9 | 3 | 1 | filter | 75 | 75 | 3.799 | 0.847 | 0.000 | 2.942 | passed |
| 9 | 3 | 1 | filter-adaptive | 75 | 75 | 4.254 | 1.280 | 0.465 | 2.963 | passed |
| 9 | 3 | 1 | sample-random | 359 | 359 | 14.547 | 0.399 | 0.000 | 14.138 | passed |
| 9 | 5 | 0 | filter | 127 | 127 | 5.817 | 0.822 | 0.000 | 4.962 | passed |
| 9 | 5 | 0 | sample-random | 359 | 359 | 14.393 | 0.400 | 0.000 | 13.983 | passed |
| 9 | 5 | 0 | baseline | 512 | 512 | 20.423 | 0.412 | 0.000 | 20.001 | passed |
| 9 | 5 | 0 | filter-adaptive | 127 | 127 | 6.796 | 1.791 | 0.940 | 4.994 | passed |
| 9 | 5 | 1 | filter-adaptive | 127 | 127 | 6.757 | 1.803 | 0.907 | 4.942 | passed |
| 9 | 5 | 1 | baseline | 512 | 512 | 20.418 | 0.417 | 0.000 | 19.991 | passed |
| 9 | 5 | 1 | sample-random | 359 | 359 | 14.446 | 0.403 | 0.000 | 14.033 | passed |
| 9 | 5 | 1 | filter | 127 | 127 | 5.818 | 0.823 | 0.000 | 4.984 | passed |

Raw timings and fallback decisions (local run data) · Full measurements (local run data) · Chart recipes (local run data)

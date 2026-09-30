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
| 6 | 1 | 0 | baseline | 64 | 64 | 2.106 | 0.033 | 0.000 | 2.002 | passed |
| 6 | 1 | 0 | sample-random | 64 | 64 | 2.021 | 0.033 | 0.000 | 1.981 | passed |
| 6 | 1 | 0 | filter-adaptive | 5 | 5 | 0.266 | 0.099 | 0.027 | 0.159 | passed |
| 6 | 1 | 0 | filter | 5 | 5 | 0.232 | 0.069 | 0.000 | 0.155 | passed |
| 6 | 1 | 1 | baseline | 64 | 64 | 1.959 | 0.032 | 0.000 | 1.919 | passed |
| 6 | 1 | 1 | sample-random | 64 | 64 | 2.016 | 0.071 | 0.000 | 1.939 | passed |
| 6 | 1 | 1 | filter | 5 | 5 | 0.228 | 0.068 | 0.000 | 0.153 | passed |
| 6 | 1 | 1 | filter-adaptive | 5 | 5 | 0.262 | 0.098 | 0.026 | 0.157 | passed |
| 6 | 3 | 0 | baseline | 64 | 64 | 2.051 | 0.033 | 0.000 | 1.999 | passed |
| 6 | 3 | 0 | filter | 17 | 17 | 0.606 | 0.075 | 0.000 | 0.522 | passed |
| 6 | 3 | 0 | filter-adaptive | 17 | 17 | 0.657 | 0.133 | 0.056 | 0.516 | passed |
| 6 | 3 | 0 | sample-random | 64 | 64 | 2.007 | 0.034 | 0.000 | 1.966 | passed |
| 6 | 3 | 1 | filter-adaptive | 17 | 17 | 0.695 | 0.136 | 0.058 | 0.552 | passed |
| 6 | 3 | 1 | baseline | 64 | 64 | 2.021 | 0.043 | 0.000 | 1.964 | passed |
| 6 | 3 | 1 | sample-random | 64 | 64 | 2.049 | 0.034 | 0.000 | 2.009 | passed |
| 6 | 3 | 1 | filter | 17 | 17 | 0.619 | 0.075 | 0.000 | 0.536 | passed |
| 6 | 5 | 0 | filter | 29 | 29 | 0.977 | 0.077 | 0.000 | 0.878 | passed |
| 6 | 5 | 0 | sample-random | 64 | 64 | 1.985 | 0.034 | 0.000 | 1.944 | passed |
| 6 | 5 | 0 | filter-adaptive | 29 | 29 | 1.047 | 0.174 | 0.092 | 0.866 | passed |
| 6 | 5 | 0 | baseline | 64 | 64 | 2.068 | 0.035 | 0.000 | 2.027 | passed |
| 6 | 5 | 1 | filter | 29 | 29 | 0.962 | 0.077 | 0.000 | 0.878 | passed |
| 6 | 5 | 1 | filter-adaptive | 29 | 29 | 1.062 | 0.175 | 0.094 | 0.878 | passed |
| 6 | 5 | 1 | sample-random | 64 | 64 | 2.025 | 0.034 | 0.000 | 1.984 | passed |
| 6 | 5 | 1 | baseline | 64 | 64 | 2.000 | 0.034 | 0.000 | 1.959 | passed |
| 7 | 1 | 0 | filter | 9 | 9 | 0.429 | 0.127 | 0.000 | 0.285 | passed |
| 7 | 1 | 0 | filter-adaptive | 7 | 7 | 0.381 | 0.156 | 0.027 | 0.217 | passed |
| 7 | 1 | 0 | sample-random | 128 | 128 | 3.942 | 0.065 | 0.000 | 3.871 | passed |
| 7 | 1 | 0 | baseline | 128 | 128 | 3.923 | 0.063 | 0.000 | 3.852 | passed |
| 7 | 1 | 1 | filter-adaptive | 7 | 7 | 0.374 | 0.155 | 0.026 | 0.212 | passed |
| 7 | 1 | 1 | sample-random | 128 | 128 | 3.929 | 0.064 | 0.000 | 3.858 | passed |
| 7 | 1 | 1 | filter | 9 | 9 | 0.398 | 0.125 | 0.000 | 0.267 | passed |
| 7 | 1 | 1 | baseline | 128 | 128 | 3.900 | 0.064 | 0.000 | 3.829 | passed |
| 7 | 3 | 0 | filter-adaptive | 20 | 20 | 0.860 | 0.247 | 0.094 | 0.593 | passed |
| 7 | 3 | 0 | filter | 21 | 21 | 0.809 | 0.175 | 0.000 | 0.627 | passed |
| 7 | 3 | 0 | baseline | 128 | 128 | 3.971 | 0.064 | 0.000 | 3.900 | passed |
| 7 | 3 | 0 | sample-random | 128 | 128 | 3.900 | 0.064 | 0.000 | 3.829 | passed |
| 7 | 3 | 1 | baseline | 128 | 128 | 3.904 | 0.064 | 0.000 | 3.833 | passed |
| 7 | 3 | 1 | filter | 21 | 21 | 0.768 | 0.131 | 0.000 | 0.629 | passed |
| 7 | 3 | 1 | filter-adaptive | 20 | 20 | 0.839 | 0.231 | 0.092 | 0.598 | passed |
| 7 | 3 | 1 | sample-random | 128 | 128 | 3.891 | 0.064 | 0.000 | 3.820 | passed |
| 7 | 5 | 0 | filter-adaptive | 36 | 36 | 1.402 | 0.311 | 0.164 | 1.069 | passed |
| 7 | 5 | 0 | baseline | 128 | 128 | 4.072 | 0.065 | 0.000 | 3.999 | passed |
| 7 | 5 | 0 | filter | 37 | 37 | 1.339 | 0.160 | 0.000 | 1.170 | passed |
| 7 | 5 | 0 | sample-random | 128 | 128 | 4.122 | 0.065 | 0.000 | 4.049 | passed |
| 7 | 5 | 1 | sample-random | 128 | 128 | 3.897 | 0.065 | 0.000 | 3.825 | passed |
| 7 | 5 | 1 | filter | 37 | 37 | 1.253 | 0.137 | 0.000 | 1.107 | passed |
| 7 | 5 | 1 | filter-adaptive | 36 | 36 | 1.408 | 0.310 | 0.164 | 1.089 | passed |
| 7 | 5 | 1 | baseline | 128 | 128 | 3.896 | 0.065 | 0.000 | 3.824 | passed |
| 8 | 1 | 0 | sample-random | 180 | 180 | 5.575 | 0.128 | 0.000 | 5.430 | passed |
| 8 | 1 | 0 | filter-adaptive | 13 | 13 | 0.686 | 0.286 | 0.033 | 0.392 | passed |
| 8 | 1 | 0 | filter | 17 | 17 | 0.795 | 0.265 | 0.000 | 0.523 | passed |
| 8 | 1 | 0 | baseline | 256 | 256 | 7.808 | 0.130 | 0.000 | 7.671 | passed |
| 8 | 1 | 1 | sample-random | 180 | 180 | 5.585 | 0.126 | 0.000 | 5.452 | passed |
| 8 | 1 | 1 | filter | 17 | 17 | 0.808 | 0.289 | 0.000 | 0.511 | passed |
| 8 | 1 | 1 | baseline | 256 | 256 | 7.907 | 0.130 | 0.000 | 7.770 | passed |
| 8 | 1 | 1 | filter-adaptive | 13 | 13 | 0.691 | 0.285 | 0.033 | 0.398 | passed |
| 8 | 3 | 0 | baseline | 256 | 256 | 7.899 | 0.131 | 0.000 | 7.747 | passed |
| 8 | 3 | 0 | filter-adaptive | 34 | 34 | 1.422 | 0.376 | 0.102 | 1.038 | passed |
| 8 | 3 | 0 | sample-random | 180 | 180 | 5.582 | 0.127 | 0.000 | 5.448 | passed |
| 8 | 3 | 0 | filter | 35 | 35 | 1.331 | 0.257 | 0.000 | 1.066 | passed |
| 8 | 3 | 1 | filter | 35 | 35 | 1.338 | 0.259 | 0.000 | 1.071 | passed |
| 8 | 3 | 1 | filter-adaptive | 34 | 34 | 1.414 | 0.369 | 0.100 | 1.036 | passed |
| 8 | 3 | 1 | sample-random | 180 | 180 | 5.606 | 0.128 | 0.000 | 5.471 | passed |
| 8 | 3 | 1 | baseline | 256 | 256 | 7.791 | 0.130 | 0.000 | 7.654 | passed |
| 8 | 5 | 0 | sample-random | 180 | 180 | 5.547 | 0.127 | 0.000 | 5.397 | passed |
| 8 | 5 | 0 | filter | 58 | 58 | 2.019 | 0.265 | 0.000 | 1.745 | passed |
| 8 | 5 | 0 | baseline | 256 | 256 | 7.879 | 0.131 | 0.000 | 7.741 | passed |
| 8 | 5 | 0 | filter-adaptive | 58 | 58 | 2.491 | 0.673 | 0.393 | 1.809 | passed |
| 8 | 5 | 1 | filter-adaptive | 58 | 58 | 2.351 | 0.600 | 0.325 | 1.741 | passed |
| 8 | 5 | 1 | sample-random | 180 | 180 | 5.671 | 0.127 | 0.000 | 5.536 | passed |
| 8 | 5 | 1 | filter | 58 | 58 | 2.062 | 0.268 | 0.000 | 1.786 | passed |
| 8 | 5 | 1 | baseline | 256 | 256 | 7.958 | 0.131 | 0.000 | 7.819 | passed |
| 9 | 1 | 0 | baseline | 512 | 512 | 15.679 | 0.271 | 0.000 | 15.390 | passed |
| 9 | 1 | 0 | filter | 33 | 33 | 1.507 | 0.511 | 0.000 | 0.987 | passed |
| 9 | 1 | 0 | sample-random | 359 | 359 | 10.973 | 0.263 | 0.000 | 10.702 | passed |
| 9 | 1 | 0 | filter-adaptive | 33 | 33 | 1.548 | 0.539 | 0.034 | 1.000 | passed |
| 9 | 1 | 1 | baseline | 512 | 512 | 15.455 | 0.271 | 0.000 | 15.177 | passed |
| 9 | 1 | 1 | sample-random | 359 | 359 | 10.985 | 0.266 | 0.000 | 10.711 | passed |
| 9 | 1 | 1 | filter | 33 | 33 | 1.486 | 0.495 | 0.000 | 0.982 | passed |
| 9 | 1 | 1 | filter-adaptive | 33 | 33 | 1.522 | 0.538 | 0.033 | 0.975 | passed |
| 9 | 3 | 0 | sample-random | 359 | 359 | 10.847 | 0.262 | 0.000 | 10.565 | passed |
| 9 | 3 | 0 | filter | 75 | 75 | 2.757 | 0.534 | 0.000 | 2.214 | passed |
| 9 | 3 | 0 | baseline | 512 | 512 | 15.364 | 0.269 | 0.000 | 15.087 | passed |
| 9 | 3 | 0 | filter-adaptive | 75 | 75 | 3.095 | 0.860 | 0.327 | 2.226 | passed |
| 9 | 3 | 1 | baseline | 512 | 512 | 15.642 | 0.271 | 0.000 | 15.364 | passed |
| 9 | 3 | 1 | filter | 75 | 75 | 2.888 | 0.575 | 0.000 | 2.304 | passed |
| 9 | 3 | 1 | filter-adaptive | 75 | 75 | 3.126 | 0.869 | 0.329 | 2.248 | passed |
| 9 | 3 | 1 | sample-random | 359 | 359 | 11.091 | 0.266 | 0.000 | 10.817 | passed |
| 9 | 5 | 0 | filter | 127 | 127 | 4.403 | 0.542 | 0.000 | 3.835 | passed |
| 9 | 5 | 0 | sample-random | 359 | 359 | 10.979 | 0.265 | 0.000 | 10.706 | passed |
| 9 | 5 | 0 | baseline | 512 | 512 | 15.701 | 0.272 | 0.000 | 15.421 | passed |
| 9 | 5 | 0 | filter-adaptive | 127 | 127 | 5.038 | 1.229 | 0.671 | 3.799 | passed |
| 9 | 5 | 1 | filter-adaptive | 127 | 127 | 5.222 | 1.245 | 0.642 | 3.968 | passed |
| 9 | 5 | 1 | baseline | 512 | 512 | 15.838 | 0.272 | 0.000 | 15.558 | passed |
| 9 | 5 | 1 | sample-random | 359 | 359 | 11.128 | 0.261 | 0.000 | 10.859 | passed |
| 9 | 5 | 1 | filter | 127 | 127 | 4.532 | 0.542 | 0.000 | 3.981 | passed |

Raw timings and fallback decisions (local run data) · Full measurements (local run data) · Chart recipes (local run data)

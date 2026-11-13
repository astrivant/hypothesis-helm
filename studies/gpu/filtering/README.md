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
| 6 | 1 | 0 | baseline | 64 | 64 | 8.601 | 6.072 | 0.000 | 2.437 | passed |
| 6 | 1 | 0 | sample-random | 64 | 64 | 4.797 | 2.337 | 0.000 | 2.451 | passed |
| 6 | 1 | 0 | filter-adaptive | 5 | 5 | 2.649 | 2.445 | 0.040 | 0.195 | passed |
| 6 | 1 | 0 | filter | 5 | 5 | 2.580 | 2.376 | 0.000 | 0.194 | passed |
| 6 | 1 | 1 | baseline | 64 | 64 | 4.766 | 2.275 | 0.000 | 2.482 | passed |
| 6 | 1 | 1 | sample-random | 64 | 64 | 4.781 | 2.329 | 0.000 | 2.443 | passed |
| 6 | 1 | 1 | filter | 5 | 5 | 2.596 | 2.393 | 0.000 | 0.193 | passed |
| 6 | 1 | 1 | filter-adaptive | 5 | 5 | 2.640 | 2.436 | 0.038 | 0.194 | passed |
| 6 | 3 | 0 | baseline | 64 | 64 | 4.796 | 2.324 | 0.000 | 2.446 | passed |
| 6 | 3 | 0 | filter | 17 | 17 | 3.056 | 2.392 | 0.000 | 0.654 | passed |
| 6 | 3 | 0 | filter-adaptive | 17 | 17 | 3.154 | 2.490 | 0.086 | 0.653 | passed |
| 6 | 3 | 0 | sample-random | 64 | 64 | 4.791 | 2.330 | 0.000 | 2.452 | passed |
| 6 | 3 | 1 | filter-adaptive | 17 | 17 | 3.162 | 2.500 | 0.087 | 0.653 | passed |
| 6 | 3 | 1 | baseline | 64 | 64 | 4.799 | 2.338 | 0.000 | 2.451 | passed |
| 6 | 3 | 1 | sample-random | 64 | 64 | 4.807 | 2.348 | 0.000 | 2.449 | passed |
| 6 | 3 | 1 | filter | 17 | 17 | 3.071 | 2.407 | 0.000 | 0.653 | passed |
| 6 | 5 | 0 | filter | 29 | 29 | 3.549 | 2.402 | 0.000 | 1.117 | passed |
| 6 | 5 | 0 | sample-random | 64 | 64 | 4.812 | 2.349 | 0.000 | 2.453 | passed |
| 6 | 5 | 0 | filter-adaptive | 29 | 29 | 3.690 | 2.565 | 0.144 | 1.115 | passed |
| 6 | 5 | 0 | baseline | 64 | 64 | 4.800 | 2.333 | 0.000 | 2.457 | passed |
| 6 | 5 | 1 | filter | 29 | 29 | 3.523 | 2.397 | 0.000 | 1.115 | passed |
| 6 | 5 | 1 | filter-adaptive | 29 | 29 | 3.694 | 2.569 | 0.146 | 1.114 | passed |
| 6 | 5 | 1 | sample-random | 64 | 64 | 4.811 | 2.356 | 0.000 | 2.445 | passed |
| 6 | 5 | 1 | baseline | 64 | 64 | 4.771 | 2.319 | 0.000 | 2.443 | passed |
| 7 | 1 | 0 | filter | 9 | 9 | 2.857 | 2.486 | 0.000 | 0.346 | passed |
| 7 | 1 | 0 | filter-adaptive | 7 | 7 | 2.819 | 2.537 | 0.039 | 0.271 | passed |
| 7 | 1 | 0 | sample-random | 128 | 128 | 7.290 | 2.390 | 0.000 | 4.890 | passed |
| 7 | 1 | 0 | baseline | 128 | 128 | 7.288 | 2.394 | 0.000 | 4.885 | passed |
| 7 | 1 | 1 | filter-adaptive | 7 | 7 | 2.815 | 2.535 | 0.039 | 0.270 | passed |
| 7 | 1 | 1 | sample-random | 128 | 128 | 7.284 | 2.374 | 0.000 | 4.900 | passed |
| 7 | 1 | 1 | filter | 9 | 9 | 2.868 | 2.508 | 0.000 | 0.350 | passed |
| 7 | 1 | 1 | baseline | 128 | 128 | 7.331 | 2.386 | 0.000 | 4.935 | passed |
| 7 | 3 | 0 | filter-adaptive | 20 | 20 | 3.467 | 2.669 | 0.146 | 0.770 | passed |
| 7 | 3 | 0 | filter | 21 | 21 | 3.359 | 2.540 | 0.000 | 0.808 | passed |
| 7 | 3 | 0 | baseline | 128 | 128 | 7.309 | 2.395 | 0.000 | 4.903 | passed |
| 7 | 3 | 0 | sample-random | 128 | 128 | 7.284 | 2.387 | 0.000 | 4.887 | passed |
| 7 | 3 | 1 | baseline | 128 | 128 | 7.308 | 2.395 | 0.000 | 4.902 | passed |
| 7 | 3 | 1 | filter | 21 | 21 | 3.321 | 2.500 | 0.000 | 0.810 | passed |
| 7 | 3 | 1 | filter-adaptive | 20 | 20 | 3.455 | 2.674 | 0.144 | 0.771 | passed |
| 7 | 3 | 1 | sample-random | 128 | 128 | 7.300 | 2.388 | 0.000 | 4.902 | passed |
| 7 | 5 | 0 | filter-adaptive | 36 | 36 | 4.202 | 2.784 | 0.256 | 1.385 | passed |
| 7 | 5 | 0 | baseline | 128 | 128 | 7.305 | 2.394 | 0.000 | 4.900 | passed |
| 7 | 5 | 0 | filter | 37 | 37 | 3.924 | 2.493 | 0.000 | 1.420 | passed |
| 7 | 5 | 0 | sample-random | 128 | 128 | 7.301 | 2.388 | 0.000 | 4.903 | passed |
| 7 | 5 | 1 | sample-random | 128 | 128 | 7.303 | 2.381 | 0.000 | 4.912 | passed |
| 7 | 5 | 1 | filter | 37 | 37 | 3.948 | 2.519 | 0.000 | 1.418 | passed |
| 7 | 5 | 1 | filter-adaptive | 36 | 36 | 4.182 | 2.788 | 0.256 | 1.383 | passed |
| 7 | 5 | 1 | baseline | 128 | 128 | 7.287 | 2.379 | 0.000 | 4.899 | passed |
| 8 | 1 | 0 | sample-random | 180 | 180 | 9.412 | 2.490 | 0.000 | 6.897 | passed |
| 8 | 1 | 0 | filter-adaptive | 13 | 13 | 3.270 | 2.755 | 0.048 | 0.504 | passed |
| 8 | 1 | 0 | filter | 17 | 17 | 3.377 | 2.709 | 0.000 | 0.658 | passed |
| 8 | 1 | 0 | baseline | 256 | 256 | 12.319 | 2.497 | 0.000 | 9.811 | passed |
| 8 | 1 | 1 | sample-random | 180 | 180 | 9.397 | 2.485 | 0.000 | 6.903 | passed |
| 8 | 1 | 1 | filter | 17 | 17 | 3.407 | 2.739 | 0.000 | 0.657 | passed |
| 8 | 1 | 1 | baseline | 256 | 256 | 12.311 | 2.488 | 0.000 | 9.813 | passed |
| 8 | 1 | 1 | filter-adaptive | 13 | 13 | 3.268 | 2.756 | 0.049 | 0.502 | passed |
| 8 | 3 | 0 | baseline | 256 | 256 | 12.340 | 2.493 | 0.000 | 9.818 | passed |
| 8 | 3 | 0 | filter-adaptive | 34 | 34 | 4.217 | 2.893 | 0.157 | 1.312 | passed |
| 8 | 3 | 0 | sample-random | 180 | 180 | 9.401 | 2.491 | 0.000 | 6.900 | passed |
| 8 | 3 | 0 | filter | 35 | 35 | 4.089 | 2.725 | 0.000 | 1.353 | passed |
| 8 | 3 | 1 | filter | 35 | 35 | 4.083 | 2.715 | 0.000 | 1.356 | passed |
| 8 | 3 | 1 | filter-adaptive | 34 | 34 | 4.217 | 2.891 | 0.155 | 1.315 | passed |
| 8 | 3 | 1 | sample-random | 180 | 180 | 9.443 | 2.500 | 0.000 | 6.933 | passed |
| 8 | 3 | 1 | baseline | 256 | 256 | 12.347 | 2.498 | 0.000 | 9.839 | passed |
| 8 | 5 | 0 | sample-random | 180 | 180 | 9.459 | 2.491 | 0.000 | 6.934 | passed |
| 8 | 5 | 0 | filter | 58 | 58 | 5.000 | 2.746 | 0.000 | 2.241 | passed |
| 8 | 5 | 0 | baseline | 256 | 256 | 12.365 | 2.506 | 0.000 | 9.849 | passed |
| 8 | 5 | 0 | filter-adaptive | 58 | 58 | 5.586 | 3.325 | 0.570 | 2.249 | passed |
| 8 | 5 | 1 | filter-adaptive | 58 | 58 | 5.516 | 3.266 | 0.517 | 2.238 | passed |
| 8 | 5 | 1 | sample-random | 180 | 180 | 9.421 | 2.491 | 0.000 | 6.919 | passed |
| 8 | 5 | 1 | filter | 58 | 58 | 4.977 | 2.732 | 0.000 | 2.233 | passed |
| 8 | 5 | 1 | baseline | 256 | 256 | 12.369 | 2.494 | 0.000 | 9.864 | passed |
| 9 | 1 | 0 | baseline | 512 | 512 | 22.399 | 2.721 | 0.000 | 19.653 | passed |
| 9 | 1 | 0 | filter | 33 | 33 | 4.424 | 3.139 | 0.000 | 1.274 | passed |
| 9 | 1 | 0 | sample-random | 359 | 359 | 16.482 | 2.712 | 0.000 | 13.759 | passed |
| 9 | 1 | 0 | filter-adaptive | 33 | 33 | 4.459 | 3.176 | 0.050 | 1.271 | passed |
| 9 | 1 | 1 | baseline | 512 | 512 | 22.343 | 2.708 | 0.000 | 19.625 | passed |
| 9 | 1 | 1 | sample-random | 359 | 359 | 16.547 | 2.711 | 0.000 | 13.826 | passed |
| 9 | 1 | 1 | filter | 33 | 33 | 4.414 | 3.134 | 0.000 | 1.269 | passed |
| 9 | 1 | 1 | filter-adaptive | 33 | 33 | 4.471 | 3.191 | 0.051 | 1.270 | passed |
| 9 | 3 | 0 | sample-random | 359 | 359 | 16.545 | 2.701 | 0.000 | 13.814 | passed |
| 9 | 3 | 0 | filter | 75 | 75 | 6.080 | 3.170 | 0.000 | 2.898 | passed |
| 9 | 3 | 0 | baseline | 512 | 512 | 22.412 | 2.713 | 0.000 | 19.688 | passed |
| 9 | 3 | 0 | filter-adaptive | 75 | 75 | 6.621 | 3.712 | 0.518 | 2.897 | passed |
| 9 | 3 | 1 | baseline | 512 | 512 | 22.409 | 2.735 | 0.000 | 19.664 | passed |
| 9 | 3 | 1 | filter | 75 | 75 | 6.132 | 3.225 | 0.000 | 2.896 | passed |
| 9 | 3 | 1 | filter-adaptive | 75 | 75 | 6.617 | 3.712 | 0.520 | 2.893 | passed |
| 9 | 3 | 1 | sample-random | 359 | 359 | 16.490 | 2.702 | 0.000 | 13.777 | passed |
| 9 | 5 | 0 | filter | 127 | 127 | 8.140 | 3.194 | 0.000 | 4.909 | passed |
| 9 | 5 | 0 | sample-random | 359 | 359 | 16.566 | 2.718 | 0.000 | 13.837 | passed |
| 9 | 5 | 0 | baseline | 512 | 512 | 22.437 | 2.713 | 0.000 | 19.713 | passed |
| 9 | 5 | 0 | filter-adaptive | 127 | 127 | 9.201 | 4.288 | 1.053 | 4.901 | passed |
| 9 | 5 | 1 | filter-adaptive | 127 | 127 | 9.196 | 4.218 | 1.000 | 4.964 | passed |
| 9 | 5 | 1 | baseline | 512 | 512 | 22.424 | 2.711 | 0.000 | 19.702 | passed |
| 9 | 5 | 1 | sample-random | 359 | 359 | 16.521 | 2.705 | 0.000 | 13.804 | passed |
| 9 | 5 | 1 | filter | 127 | 127 | 8.107 | 3.202 | 0.000 | 4.892 | passed |

Raw timings and fallback decisions (local run data) · Full measurements (local run data) · Chart recipes (local run data)

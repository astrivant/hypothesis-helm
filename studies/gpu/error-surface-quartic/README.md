# Quadratic versus quartic

<!-- toc:start -->
**Table of contents**

- [Comparisons](#comparisons)
<!-- toc:end -->

Both models train on the same cells, excluding 25% of settings and the last repeat. Corners remain in training.
Outlined cells are held out in both setting and repeat. All observed panels show the reserved repeat.
Scores compare unmodified predictions: lower RMSE is better. A quartic is not assumed to improve prediction.
Timing reflects the host's load during collection; this small comparison does not establish a general model ranking.
A full quartic needs 15 identifiable coefficients and more than 15 training cells, including at least five settings per axis.
Unavailable fits remain blank. No extra measurements are inferred, and existing quadratic and symbolic results are unchanged.

Splits, coefficients and scores (local run data)

| Surface / method / response | Model | Held-out cells RMSE | Held-out repeat RMSE | Both held out RMSE |
| --- | --- | ---: | ---: | ---: |
| clustering / combined / total_seconds | quadratic | 0.006725 | 0.01191 | 0.01139 |
| clustering / combined / total_seconds | quartic | 0.007555 | 0.01207 | 0.01193 |
| clustering / combined / errors_missed | quadratic | 0.4792 | 1.034 | 0.907 |
| clustering / combined / errors_missed | quartic | 0.4493 | 0.9882 | 0.8811 |
| clustering / default / total_seconds | quadratic | 0.02487 | 0.04941 | 0.04445 |
| clustering / default / total_seconds | quartic | 0.02469 | 0.05028 | 0.04502 |
| clustering / default / errors_missed | quadratic | 0 | 0 | 0 |
| clustering / default / errors_missed | quartic | 0 | 0 | 0 |
| clustering / exact-equivalence / total_seconds | quadratic | 0.01664 | 0.02251 | 0.02098 |
| clustering / exact-equivalence / total_seconds | quartic | 0.0168 | 0.02263 | 0.02177 |
| clustering / exact-equivalence / errors_missed | quadratic | 0 | 0 | 0 |
| clustering / exact-equivalence / errors_missed | quartic | 0 | 0 | 0 |
| clustering / filter / total_seconds | quadratic | 0.7769 | 1.441 | 1.514 |
| clustering / filter / total_seconds | quartic | 0.5671 | 1.457 | 1.489 |
| clustering / filter / errors_missed | quadratic | 6.111 | 9.39 | 8.98 |
| clustering / filter / errors_missed | quartic | 4.286 | 8.581 | 7.502 |
| clustering / filter-adaptive / total_seconds | quadratic | 0.7782 | 1.446 | 1.515 |
| clustering / filter-adaptive / total_seconds | quartic | 0.5651 | 1.463 | 1.494 |
| clustering / filter-adaptive / errors_missed | quadratic | 6.111 | 9.39 | 8.98 |
| clustering / filter-adaptive / errors_missed | quartic | 4.286 | 8.581 | 7.502 |
| clustering / random / total_seconds | quadratic | 0.01175 | 0.01358 | 0.01553 |
| clustering / random / total_seconds | quartic | 0.01151 | 0.01367 | 0.01562 |
| clustering / random / errors_missed | quadratic | 0.6055 | 1.685 | 1.679 |
| clustering / random / errors_missed | quartic | 0.563 | 1.718 | 1.759 |
| clustering / sample-random / total_seconds | quadratic | 0.02129 | 0.0342 | 0.02616 |
| clustering / sample-random / total_seconds | quartic | 0.02155 | 0.03481 | 0.02673 |
| clustering / sample-random / errors_missed | quadratic | 1.253 | 3.12 | 2.781 |
| clustering / sample-random / errors_missed | quartic | 1.039 | 3.29 | 3.129 |
| clustering / topology / total_seconds | quadratic | 0.009031 | 0.01445 | 0.01913 |
| clustering / topology / total_seconds | quartic | 0.009792 | 0.01462 | 0.01947 |
| clustering / topology / errors_missed | quadratic | 0.7333 | 1.439 | 1.278 |
| clustering / topology / errors_missed | quartic | 0.6799 | 1.38 | 1.224 |
| depth / combined / total_seconds | quadratic | 0.01085 | 0.01541 | 0.01522 |
| depth / combined / total_seconds | quartic | 0.013 | 0.0177 | 0.01625 |
| depth / combined / errors_missed | quadratic | 1.075 | 1.341 | 1.73 |
| depth / combined / errors_missed | quartic | 0.9815 | 1.514 | 1.792 |
| depth / default / total_seconds | quadratic | 0.03634 | 0.05356 | 0.06907 |
| depth / default / total_seconds | quartic | 0.03172 | 0.05729 | 0.06711 |
| depth / default / errors_missed | quadratic | 0 | 0 | 0 |
| depth / default / errors_missed | quartic | 0 | 0 | 0 |
| depth / exact-equivalence / total_seconds | quadratic | 0.8803 | 0.03028 | 0.01912 |
| depth / exact-equivalence / total_seconds | quartic | 0.8777 | 0.03759 | 0.03505 |
| depth / exact-equivalence / errors_missed | quadratic | 0 | 0 | 0 |
| depth / exact-equivalence / errors_missed | quartic | 0 | 0 | 0 |
| depth / filter / total_seconds | quadratic | 0.5961 | 1.164 | 0.7298 |
| depth / filter / total_seconds | quartic | 0.474 | 1.098 | 0.6613 |
| depth / filter / errors_missed | quadratic | 7.455 | 15.71 | 12.2 |
| depth / filter / errors_missed | quartic | 4.148 | 14.46 | 12.61 |
| depth / filter-adaptive / total_seconds | quadratic | 0.5643 | 1.177 | 0.7187 |
| depth / filter-adaptive / total_seconds | quartic | 0.414 | 1.088 | 0.6714 |
| depth / filter-adaptive / errors_missed | quadratic | 7.455 | 15.71 | 12.2 |
| depth / filter-adaptive / errors_missed | quartic | 4.148 | 14.46 | 12.61 |
| depth / random / total_seconds | quadratic | 0.06803 | 0.1084 | 0.06887 |
| depth / random / total_seconds | quartic | 0.08555 | 0.1384 | 0.08802 |
| depth / random / errors_missed | quadratic | 0.8064 | 1.332 | 1.551 |
| depth / random / errors_missed | quartic | 0.7278 | 1.542 | 1.893 |
| depth / sample-random / total_seconds | quadratic | 0.1756 | 0.2837 | 0.1766 |
| depth / sample-random / total_seconds | quartic | 0.1597 | 0.3413 | 0.1547 |
| depth / sample-random / errors_missed | quadratic | 2.168 | 3.144 | 2.45 |
| depth / sample-random / errors_missed | quartic | 1.794 | 3.517 | 2.943 |
| depth / topology / total_seconds | quadratic | 0.1532 | 0.1655 | 0.1573 |
| depth / topology / total_seconds | quartic | 0.1931 | 0.2401 | 0.1973 |
| depth / topology / errors_missed | quadratic | 1.025 | 2.141 | 2.354 |
| depth / topology / errors_missed | quartic | 0.8299 | 2.196 | 2.164 |
| redundancy / combined / total_seconds | quadratic | 0.7335 | 0.6955 | 0.7239 |
| redundancy / combined / total_seconds | quartic | 0.05007 | 0.2042 | 0.0481 |
| redundancy / combined / errors_missed | quadratic | 17.3 | 16.15 | 17.8 |
| redundancy / combined / errors_missed | quartic | 2.128 | 1.843 | 2.677 |
| redundancy / default / total_seconds | quadratic | 0.0305 | 0.05513 | 0.04652 |
| redundancy / default / total_seconds | quartic | 0.02331 | 0.05201 | 0.04477 |
| redundancy / default / errors_missed | quadratic | 0 | 0 | 0 |
| redundancy / default / errors_missed | quartic | 0 | 0 | 0 |
| redundancy / exact-equivalence / total_seconds | quadratic | 0.7341 | 0.6295 | 0.7164 |
| redundancy / exact-equivalence / total_seconds | quartic | 0.05162 | 0.04827 | 0.05901 |
| redundancy / exact-equivalence / errors_missed | quadratic | 0 | 0 | 0 |
| redundancy / exact-equivalence / errors_missed | quartic | 0 | 0 | 0 |
| redundancy / filter / total_seconds | quadratic | 1.307 | 1.176 | 1.269 |
| redundancy / filter / total_seconds | quartic | 0.6703 | 0.574 | 1.041 |
| redundancy / filter / errors_missed | quadratic | 11.71 | 12.56 | 13.88 |
| redundancy / filter / errors_missed | quartic | 4.011 | 7.922 | 7.315 |
| redundancy / filter-adaptive / total_seconds | quadratic | 1.307 | 1.189 | 1.28 |
| redundancy / filter-adaptive / total_seconds | quartic | 0.6774 | 0.5831 | 1.047 |
| redundancy / filter-adaptive / errors_missed | quadratic | 11.71 | 12.56 | 13.88 |
| redundancy / filter-adaptive / errors_missed | quartic | 4.011 | 7.922 | 7.315 |
| redundancy / random / total_seconds | quadratic | 0.01225 | 0.01244 | 0.01055 |
| redundancy / random / total_seconds | quartic | 0.01504 | 0.01335 | 0.01252 |
| redundancy / random / errors_missed | quadratic | 0.7103 | 1.422 | 1.55 |
| redundancy / random / errors_missed | quartic | 0.5355 | 1.643 | 1.778 |
| redundancy / sample-random / total_seconds | quadratic | 0.04001 | 0.05923 | 0.03601 |
| redundancy / sample-random / total_seconds | quartic | 0.06065 | 0.07909 | 0.07165 |
| redundancy / sample-random / errors_missed | quadratic | 2.022 | 2.982 | 2.874 |
| redundancy / sample-random / errors_missed | quartic | 1.358 | 3.365 | 3.845 |
| redundancy / topology / total_seconds | quadratic | 0.7467 | 0.6276 | 0.7458 |
| redundancy / topology / total_seconds | quartic | 0.06908 | 0.06678 | 0.07251 |
| redundancy / topology / errors_missed | quadratic | 18.19 | 16.88 | 18.37 |
| redundancy / topology / errors_missed | quartic | 1.862 | 1.626 | 2.26 |

## Comparisons

![Held-out observations and model predictions](comparison-1.png)

![Held-out observations and model predictions](comparison-2.png)

![Held-out observations and model predictions](comparison-3.png)

![Held-out observations and model predictions](comparison-4.png)

![Held-out observations and model predictions](comparison-5.png)

![Held-out observations and model predictions](comparison-6.png)

![Held-out observations and model predictions](comparison-7.png)

![Held-out observations and model predictions](comparison-8.png)

![Held-out observations and model predictions](comparison-9.png)

![Held-out observations and model predictions](comparison-10.png)

![Held-out observations and model predictions](comparison-11.png)

![Held-out observations and model predictions](comparison-12.png)

![Held-out observations and model predictions](comparison-13.png)

![Held-out observations and model predictions](comparison-14.png)

![Held-out observations and model predictions](comparison-15.png)

![Held-out observations and model predictions](comparison-16.png)

![Held-out observations and model predictions](comparison-17.png)

![Held-out observations and model predictions](comparison-18.png)

![Held-out observations and model predictions](comparison-19.png)

![Held-out observations and model predictions](comparison-20.png)

![Held-out observations and model predictions](comparison-21.png)

![Held-out observations and model predictions](comparison-22.png)

![Held-out observations and model predictions](comparison-23.png)

![Held-out observations and model predictions](comparison-24.png)

![Held-out observations and model predictions](comparison-25.png)

![Held-out observations and model predictions](comparison-26.png)

![Held-out observations and model predictions](comparison-27.png)

![Held-out observations and model predictions](comparison-28.png)

![Held-out observations and model predictions](comparison-29.png)

![Held-out observations and model predictions](comparison-30.png)

![Held-out observations and model predictions](comparison-31.png)

![Held-out observations and model predictions](comparison-32.png)

![Held-out observations and model predictions](comparison-33.png)

![Held-out observations and model predictions](comparison-34.png)

![Held-out observations and model predictions](comparison-35.png)

![Held-out observations and model predictions](comparison-36.png)

![Held-out observations and model predictions](comparison-37.png)

![Held-out observations and model predictions](comparison-38.png)

![Held-out observations and model predictions](comparison-39.png)

![Held-out observations and model predictions](comparison-40.png)

![Held-out observations and model predictions](comparison-41.png)

![Held-out observations and model predictions](comparison-42.png)

![Held-out observations and model predictions](comparison-43.png)

![Held-out observations and model predictions](comparison-44.png)

![Held-out observations and model predictions](comparison-45.png)

![Held-out observations and model predictions](comparison-46.png)

![Held-out observations and model predictions](comparison-47.png)

![Held-out observations and model predictions](comparison-48.png)


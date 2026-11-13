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
| clustering / combined / total_seconds | quadratic | 0.02068 | 0.03834 | 0.02164 |
| clustering / combined / total_seconds | quartic | 0.0211 | 0.0386 | 0.0227 |
| clustering / combined / errors_missed | quadratic | 0.4792 | 1.034 | 0.907 |
| clustering / combined / errors_missed | quartic | 0.4493 | 0.9882 | 0.8811 |
| clustering / default / total_seconds | quadratic | 0.713 | 1.312 | 0.7037 |
| clustering / default / total_seconds | quartic | 0.7332 | 1.319 | 0.7391 |
| clustering / default / errors_missed | quadratic | 0 | 0 | 0 |
| clustering / default / errors_missed | quartic | 0 | 0 | 0 |
| clustering / exact-equivalence / total_seconds | quadratic | 0.08877 | 0.2002 | 0.1211 |
| clustering / exact-equivalence / total_seconds | quartic | 0.091 | 0.2007 | 0.1231 |
| clustering / exact-equivalence / errors_missed | quadratic | 0 | 0 | 0 |
| clustering / exact-equivalence / errors_missed | quartic | 0 | 0 | 0 |
| clustering / filter / total_seconds | quadratic | 1.168 | 1.98 | 1.948 |
| clustering / filter / total_seconds | quartic | 1.023 | 1.984 | 1.958 |
| clustering / filter / errors_missed | quadratic | 6.111 | 9.39 | 8.98 |
| clustering / filter / errors_missed | quartic | 4.286 | 8.581 | 7.502 |
| clustering / filter-adaptive / total_seconds | quadratic | 1.183 | 1.982 | 1.958 |
| clustering / filter-adaptive / total_seconds | quartic | 1.046 | 1.99 | 1.963 |
| clustering / filter-adaptive / errors_missed | quadratic | 6.111 | 9.39 | 8.98 |
| clustering / filter-adaptive / errors_missed | quartic | 4.286 | 8.581 | 7.502 |
| clustering / random / total_seconds | quadratic | 0.05258 | 0.08943 | 0.05043 |
| clustering / random / total_seconds | quartic | 0.05349 | 0.09002 | 0.05431 |
| clustering / random / errors_missed | quadratic | 0.6055 | 1.685 | 1.679 |
| clustering / random / errors_missed | quartic | 0.563 | 1.718 | 1.759 |
| clustering / sample-random / total_seconds | quadratic | 0.4932 | 0.9044 | 0.4975 |
| clustering / sample-random / total_seconds | quartic | 0.5068 | 0.9097 | 0.5298 |
| clustering / sample-random / errors_missed | quadratic | 1.253 | 3.12 | 2.781 |
| clustering / sample-random / errors_missed | quartic | 1.039 | 3.29 | 3.129 |
| clustering / topology / total_seconds | quadratic | 0.05464 | 0.09753 | 0.05491 |
| clustering / topology / total_seconds | quartic | 0.0554 | 0.09808 | 0.05788 |
| clustering / topology / errors_missed | quadratic | 0.7333 | 1.439 | 1.278 |
| clustering / topology / errors_missed | quartic | 0.6799 | 1.38 | 1.224 |
| depth / combined / total_seconds | quadratic | 0.06387 | 0.07567 | 0.06615 |
| depth / combined / total_seconds | quartic | 0.07464 | 0.08262 | 0.076 |
| depth / combined / errors_missed | quadratic | 1.075 | 1.341 | 1.73 |
| depth / combined / errors_missed | quartic | 0.9815 | 1.514 | 1.792 |
| depth / default / total_seconds | quadratic | 0.8146 | 1.216 | 0.942 |
| depth / default / total_seconds | quartic | 0.9758 | 1.314 | 1.048 |
| depth / default / errors_missed | quadratic | 0 | 0 | 0 |
| depth / default / errors_missed | quartic | 0 | 0 | 0 |
| depth / exact-equivalence / total_seconds | quadratic | 0.1241 | 0.214 | 0.1752 |
| depth / exact-equivalence / total_seconds | quartic | 0.1484 | 0.2275 | 0.1876 |
| depth / exact-equivalence / errors_missed | quadratic | 0 | 0 | 0 |
| depth / exact-equivalence / errors_missed | quartic | 0 | 0 | 0 |
| depth / filter / total_seconds | quadratic | 0.8707 | 1.65 | 0.902 |
| depth / filter / total_seconds | quartic | 0.9377 | 1.625 | 1.037 |
| depth / filter / errors_missed | quadratic | 7.455 | 15.71 | 12.2 |
| depth / filter / errors_missed | quartic | 4.148 | 14.46 | 12.61 |
| depth / filter-adaptive / total_seconds | quadratic | 0.8667 | 1.644 | 0.9261 |
| depth / filter-adaptive / total_seconds | quartic | 0.9104 | 1.615 | 1.078 |
| depth / filter-adaptive / errors_missed | quadratic | 7.455 | 15.71 | 12.2 |
| depth / filter-adaptive / errors_missed | quartic | 4.148 | 14.46 | 12.61 |
| depth / random / total_seconds | quadratic | 0.06114 | 0.09071 | 0.06511 |
| depth / random / total_seconds | quartic | 0.0747 | 0.0972 | 0.07333 |
| depth / random / errors_missed | quadratic | 0.8064 | 1.332 | 1.551 |
| depth / random / errors_missed | quartic | 0.7278 | 1.542 | 1.893 |
| depth / sample-random / total_seconds | quadratic | 0.6168 | 0.8685 | 0.6562 |
| depth / sample-random / total_seconds | quartic | 0.728 | 0.9336 | 0.7286 |
| depth / sample-random / errors_missed | quadratic | 2.168 | 3.144 | 2.45 |
| depth / sample-random / errors_missed | quartic | 1.794 | 3.517 | 2.943 |
| depth / topology / total_seconds | quadratic | 0.09143 | 0.1085 | 0.09131 |
| depth / topology / total_seconds | quartic | 0.09602 | 0.1168 | 0.0885 |
| depth / topology / errors_missed | quadratic | 1.025 | 2.141 | 2.354 |
| depth / topology / errors_missed | quartic | 0.8299 | 2.196 | 2.164 |
| redundancy / combined / total_seconds | quadratic | 1.003 | 0.8453 | 1.074 |
| redundancy / combined / total_seconds | quartic | 0.4028 | 0.6089 | 0.4458 |
| redundancy / combined / errors_missed | quadratic | 17.3 | 16.15 | 17.8 |
| redundancy / combined / errors_missed | quartic | 2.128 | 1.843 | 2.677 |
| redundancy / default / total_seconds | quadratic | 0.7388 | 1.195 | 0.6926 |
| redundancy / default / total_seconds | quartic | 0.7717 | 1.233 | 0.6944 |
| redundancy / default / errors_missed | quadratic | 0 | 0 | 0 |
| redundancy / default / errors_missed | quartic | 0 | 0 | 0 |
| redundancy / exact-equivalence / total_seconds | quadratic | 1.003 | 0.8807 | 1.094 |
| redundancy / exact-equivalence / total_seconds | quartic | 0.4398 | 0.6376 | 0.4577 |
| redundancy / exact-equivalence / errors_missed | quadratic | 0 | 0 | 0 |
| redundancy / exact-equivalence / errors_missed | quartic | 0 | 0 | 0 |
| redundancy / filter / total_seconds | quadratic | 1.735 | 1.558 | 1.744 |
| redundancy / filter / total_seconds | quartic | 1.124 | 1.217 | 1.425 |
| redundancy / filter / errors_missed | quadratic | 11.71 | 12.56 | 13.88 |
| redundancy / filter / errors_missed | quartic | 4.011 | 7.922 | 7.315 |
| redundancy / filter-adaptive / total_seconds | quadratic | 1.726 | 1.6 | 1.702 |
| redundancy / filter-adaptive / total_seconds | quartic | 1.1 | 1.259 | 1.413 |
| redundancy / filter-adaptive / errors_missed | quadratic | 11.71 | 12.56 | 13.88 |
| redundancy / filter-adaptive / errors_missed | quartic | 4.011 | 7.922 | 7.315 |
| redundancy / random / total_seconds | quadratic | 0.05438 | 0.08616 | 0.05199 |
| redundancy / random / total_seconds | quartic | 0.05829 | 0.0892 | 0.053 |
| redundancy / random / errors_missed | quadratic | 0.7103 | 1.422 | 1.55 |
| redundancy / random / errors_missed | quartic | 0.5355 | 1.643 | 1.778 |
| redundancy / sample-random / total_seconds | quadratic | 0.486 | 0.8201 | 0.4963 |
| redundancy / sample-random / total_seconds | quartic | 0.5185 | 0.8456 | 0.4982 |
| redundancy / sample-random / errors_missed | quadratic | 2.022 | 2.982 | 2.874 |
| redundancy / sample-random / errors_missed | quartic | 1.358 | 3.365 | 3.845 |
| redundancy / topology / total_seconds | quadratic | 1.013 | 0.8318 | 1.07 |
| redundancy / topology / total_seconds | quartic | 0.4434 | 0.5642 | 0.437 |
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


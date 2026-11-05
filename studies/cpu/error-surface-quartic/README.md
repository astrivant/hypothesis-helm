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
| clustering / combined / total_seconds | quadratic | 0.02628 | 0.03636 | 0.02662 |
| clustering / combined / total_seconds | quartic | 0.02761 | 0.03761 | 0.02628 |
| clustering / combined / errors_missed | quadratic | 0.4792 | 1.034 | 0.907 |
| clustering / combined / errors_missed | quartic | 0.4493 | 0.9882 | 0.8811 |
| clustering / default / total_seconds | quadratic | 0.8784 | 1.22 | 0.9609 |
| clustering / default / total_seconds | quartic | 0.9427 | 1.251 | 0.9678 |
| clustering / default / errors_missed | quadratic | 0 | 0 | 0 |
| clustering / default / errors_missed | quartic | 0 | 0 | 0 |
| clustering / exact-equivalence / total_seconds | quadratic | 0.1174 | 0.1873 | 0.1404 |
| clustering / exact-equivalence / total_seconds | quartic | 0.1212 | 0.1935 | 0.1398 |
| clustering / exact-equivalence / errors_missed | quadratic | 0 | 0 | 0 |
| clustering / exact-equivalence / errors_missed | quartic | 0 | 0 | 0 |
| clustering / filter / total_seconds | quadratic | 1.086 | 1.874 | 2.068 |
| clustering / filter / total_seconds | quartic | 0.8495 | 2.001 | 1.945 |
| clustering / filter / errors_missed | quadratic | 6.111 | 9.39 | 8.98 |
| clustering / filter / errors_missed | quartic | 4.286 | 8.581 | 7.502 |
| clustering / filter-adaptive / total_seconds | quadratic | 1.076 | 1.887 | 2.087 |
| clustering / filter-adaptive / total_seconds | quartic | 0.8518 | 2.006 | 1.955 |
| clustering / filter-adaptive / errors_missed | quadratic | 6.111 | 9.39 | 8.98 |
| clustering / filter-adaptive / errors_missed | quartic | 4.286 | 8.581 | 7.502 |
| clustering / random / total_seconds | quadratic | 0.06615 | 0.09115 | 0.06657 |
| clustering / random / total_seconds | quartic | 0.06945 | 0.0937 | 0.06578 |
| clustering / random / errors_missed | quadratic | 0.6055 | 1.685 | 1.679 |
| clustering / random / errors_missed | quartic | 0.563 | 1.718 | 1.759 |
| clustering / sample-random / total_seconds | quadratic | 0.6211 | 0.8523 | 0.6849 |
| clustering / sample-random / total_seconds | quartic | 0.6662 | 0.8803 | 0.6792 |
| clustering / sample-random / errors_missed | quadratic | 1.253 | 3.12 | 2.781 |
| clustering / sample-random / errors_missed | quartic | 1.039 | 3.29 | 3.129 |
| clustering / topology / total_seconds | quadratic | 0.0647 | 0.09226 | 0.06959 |
| clustering / topology / total_seconds | quartic | 0.06915 | 0.09546 | 0.06921 |
| clustering / topology / errors_missed | quadratic | 0.7333 | 1.439 | 1.278 |
| clustering / topology / errors_missed | quartic | 0.6799 | 1.38 | 1.224 |
| depth / combined / total_seconds | quadratic | 0.05285 | 0.08392 | 0.06529 |
| depth / combined / total_seconds | quartic | 0.05759 | 0.08827 | 0.06877 |
| depth / combined / errors_missed | quadratic | 1.075 | 1.341 | 1.73 |
| depth / combined / errors_missed | quartic | 0.9815 | 1.514 | 1.792 |
| depth / default / total_seconds | quadratic | 0.7522 | 1.147 | 0.761 |
| depth / default / total_seconds | quartic | 0.8124 | 1.201 | 0.808 |
| depth / default / errors_missed | quadratic | 0 | 0 | 0 |
| depth / default / errors_missed | quartic | 0 | 0 | 0 |
| depth / exact-equivalence / total_seconds | quadratic | 0.1307 | 0.2098 | 0.1585 |
| depth / exact-equivalence / total_seconds | quartic | 0.1366 | 0.2261 | 0.1774 |
| depth / exact-equivalence / errors_missed | quadratic | 0 | 0 | 0 |
| depth / exact-equivalence / errors_missed | quartic | 0 | 0 | 0 |
| depth / filter / total_seconds | quadratic | 0.975 | 1.607 | 1.037 |
| depth / filter / total_seconds | quartic | 0.751 | 1.588 | 1.015 |
| depth / filter / errors_missed | quadratic | 7.455 | 15.71 | 12.2 |
| depth / filter / errors_missed | quartic | 4.148 | 14.46 | 12.61 |
| depth / filter-adaptive / total_seconds | quadratic | 1.004 | 1.618 | 1.036 |
| depth / filter-adaptive / total_seconds | quartic | 0.7912 | 1.596 | 1.007 |
| depth / filter-adaptive / errors_missed | quadratic | 7.455 | 15.71 | 12.2 |
| depth / filter-adaptive / errors_missed | quartic | 4.148 | 14.46 | 12.61 |
| depth / random / total_seconds | quadratic | 0.05719 | 0.08718 | 0.05784 |
| depth / random / total_seconds | quartic | 0.06083 | 0.09089 | 0.06008 |
| depth / random / errors_missed | quadratic | 0.8064 | 1.332 | 1.551 |
| depth / random / errors_missed | quartic | 0.7278 | 1.542 | 1.893 |
| depth / sample-random / total_seconds | quadratic | 0.5499 | 0.8082 | 0.523 |
| depth / sample-random / total_seconds | quartic | 0.6045 | 0.8481 | 0.5625 |
| depth / sample-random / errors_missed | quadratic | 2.168 | 3.144 | 2.45 |
| depth / sample-random / errors_missed | quartic | 1.794 | 3.517 | 2.943 |
| depth / topology / total_seconds | quadratic | 0.07427 | 0.111 | 0.08708 |
| depth / topology / total_seconds | quartic | 0.08064 | 0.1146 | 0.08916 |
| depth / topology / errors_missed | quadratic | 1.025 | 2.141 | 2.354 |
| depth / topology / errors_missed | quartic | 0.8299 | 2.196 | 2.164 |
| redundancy / combined / total_seconds | quadratic | 0.9798 | 0.8778 | 0.983 |
| redundancy / combined / total_seconds | quartic | 0.4564 | 0.4865 | 0.6166 |
| redundancy / combined / errors_missed | quadratic | 17.3 | 16.15 | 17.8 |
| redundancy / combined / errors_missed | quartic | 2.128 | 1.843 | 2.677 |
| redundancy / default / total_seconds | quadratic | 0.8189 | 1.198 | 1.214 |
| redundancy / default / total_seconds | quartic | 0.8763 | 1.249 | 1.205 |
| redundancy / default / errors_missed | quadratic | 0 | 0 | 0 |
| redundancy / default / errors_missed | quartic | 0 | 0 | 0 |
| redundancy / exact-equivalence / total_seconds | quadratic | 1.007 | 0.9163 | 1.044 |
| redundancy / exact-equivalence / total_seconds | quartic | 0.513 | 0.5841 | 0.6658 |
| redundancy / exact-equivalence / errors_missed | quadratic | 0 | 0 | 0 |
| redundancy / exact-equivalence / errors_missed | quartic | 0 | 0 | 0 |
| redundancy / filter / total_seconds | quadratic | 1.462 | 1.682 | 1.94 |
| redundancy / filter / total_seconds | quartic | 0.8629 | 1.111 | 1.533 |
| redundancy / filter / errors_missed | quadratic | 11.71 | 12.56 | 13.88 |
| redundancy / filter / errors_missed | quartic | 4.011 | 7.922 | 7.315 |
| redundancy / filter-adaptive / total_seconds | quadratic | 1.466 | 1.699 | 1.925 |
| redundancy / filter-adaptive / total_seconds | quartic | 0.8643 | 1.124 | 1.531 |
| redundancy / filter-adaptive / errors_missed | quadratic | 11.71 | 12.56 | 13.88 |
| redundancy / filter-adaptive / errors_missed | quartic | 4.011 | 7.922 | 7.315 |
| redundancy / random / total_seconds | quadratic | 0.06224 | 0.08921 | 0.08805 |
| redundancy / random / total_seconds | quartic | 0.06411 | 0.09333 | 0.08718 |
| redundancy / random / errors_missed | quadratic | 0.7103 | 1.422 | 1.55 |
| redundancy / random / errors_missed | quartic | 0.5355 | 1.643 | 1.778 |
| redundancy / sample-random / total_seconds | quadratic | 0.5998 | 0.8476 | 0.824 |
| redundancy / sample-random / total_seconds | quartic | 0.6358 | 0.8805 | 0.8097 |
| redundancy / sample-random / errors_missed | quadratic | 2.022 | 2.982 | 2.874 |
| redundancy / sample-random / errors_missed | quartic | 1.358 | 3.365 | 3.845 |
| redundancy / topology / total_seconds | quadratic | 0.9837 | 0.86 | 1.019 |
| redundancy / topology / total_seconds | quartic | 0.4641 | 0.4771 | 0.5824 |
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


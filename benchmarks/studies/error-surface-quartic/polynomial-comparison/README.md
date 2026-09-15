# Quadratic versus quartic

Both models train on the same cells, excluding 25% of settings and the last repeat. Corners remain in training.
Outlined cells are held out in both setting and repeat. All observed panels show the reserved repeat.
Scores compare unmodified predictions: lower RMSE is better. A quartic is not assumed to improve prediction.
Timing reflects the host's load during collection; this small comparison does not establish a general model ranking.
A full quartic needs 15 identifiable coefficients and more than 15 training cells, including at least five settings per axis.
Unavailable fits remain blank. No extra measurements are inferred, and existing quadratic and symbolic results are unchanged.

[Splits, coefficients and scores](results.json)

| Surface / method / response | Model | Held-out cells RMSE | Held-out repeat RMSE | Both held out RMSE |
| --- | --- | ---: | ---: | ---: |
| clustering / combined / total_seconds | quadratic | 0.0826 | 0.0498 | 0.0873 |
| clustering / combined / total_seconds | quartic | 0.08242 | 0.05492 | 0.07108 |
| clustering / combined / errors_missed | quadratic | 0.4532 | 0.7991 | 1.521 |
| clustering / combined / errors_missed | quartic | 1.183 | 0.7955 | 1.143 |

## Comparisons

![Held-out observations and model predictions](comparison-1.png)

![Held-out observations and model predictions](comparison-2.png)


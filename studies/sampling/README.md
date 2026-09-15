# Random sampling and defect discovery

[Benchmarking](../../benchmarks/README.md)

The shared stress chart has 1024 valid inputs and six known defect families. Every input was rendered with Helm; 500 seeded samples were evaluated at each size.

![Sample size and defect recall](sampling-recall.png)

| Random inputs + defaults | Retained | Mean defects found | 5th percentile recall | Seeds reaching 96% recall | Erroneous inputs tested |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 + 1 | 0.1% | 1.42 / 6 | 0.0% | 1.4% | 0.1% |
| 2 + 1 | 0.2% | 2.44 / 6 | 0.0% | 5.6% | 0.2% |
| 4 + 1 | 0.4% | 3.70 / 6 | 16.7% | 16.4% | 0.4% |
| 8 + 1 | 0.8% | 5.05 / 6 | 50.0% | 53.8% | 0.8% |
| 16 + 1 | 1.6% | 5.73 / 6 | 66.7% | 85.8% | 1.6% |
| 32 + 1 | 3.1% | 5.98 / 6 | 100.0% | 99.0% | 3.1% |
| 64 + 1 | 6.3% | 6.00 / 6 | 100.0% | 100.0% | 6.3% |
| 128 + 1 | 12.5% | 6.00 / 6 | 100.0% | 100.0% | 12.5% |
| 256 + 1 | 25.0% | 6.00 / 6 | 100.0% | 100.0% | 25.0% |
| 512 + 1 | 50.0% | 6.00 / 6 | 100.0% | 100.0% | 50.0% |
| 717 + 1 | 70.1% | 6.00 / 6 | 100.0% | 100.0% | 70.1% |
| 1023 + 1 | 100.0% | 6.00 / 6 | 100.0% | 100.0% | 100.0% |

The first measured sample size reaching 96% defect recall in at least 95% of these seeds is **32**.
This is a fixture-specific observation, not a confidence bound or a minimum valid for arbitrary charts.

With uniform sampling, a defect triggered by only one eligible input is found with probability sample_size / population_size. Testing 70% gives a 70% chance of finding that defect, regardless of how large the population is.

The CLI policy is opt-in: `--sample-random 70 --sample-min-cases 128` keeps at least 128 eligible cases, or all of them when fewer exist. Defaults and protected topology representatives are additional safeguards. The default floor is a conservative policy choice, not a derived 96% guarantee.

Timing covers the complete reference render, not separate executions of every sampled subset. Samples use the production selector and preserve the same ranking as sample size increases.

[Measurements](results.csv) · [Reference and provenance](results.json) · [Chart recipe](chart-parameters.yaml)

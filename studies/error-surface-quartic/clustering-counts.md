# Failure clustering: measured counts

[Graphs and methodology](README.md)

Compare rows with the same rate: the erroneous-input count and chart stay fixed while placement changes.
Detected counts below are paired means followed by the observed range; they count inputs, not distinct bugs.
Neighbour fraction measures actual clustering: neighbours differ in one Boolean switch.
Expansion follows symbolic output/branch regions, which need not match these input neighbourhoods.

| Rate | Clustering | Failing neighbours | Method | Found / errors (range) | Mean added checks |
| ---: | ---: | ---: | --- | --- | ---: |
| 0% | 0 | N/A | combined | 0 / 0 (0-0) | 0 |
| 0% | 0.25 | N/A | combined | 0 / 0 (0-0) | 0 |
| 0% | 0.5 | N/A | combined | 0 / 0 (0-0) | 0 |
| 0% | 0.75 | N/A | combined | 0 / 0 (0-0) | 0 |
| 0% | 1 | N/A | combined | 0 / 0 (0-0) | 0 |
| 25% | 0 | 25.8% | combined | 1.5 / 64 (1-2) | 0 |
| 25% | 0.25 | 26.0% | combined | 2 / 64 (1-3) | 0 |
| 25% | 0.5 | 33.8% | combined | 1.5 / 64 (1-2) | 0 |
| 25% | 0.75 | 51.4% | combined | 1.5 / 64 (1-2) | 0 |
| 25% | 1 | 56.6% | combined | 3 / 64 (3-3) | 0 |
| 50% | 0 | 50.1% | combined | 3 / 128 (2-4) | 0 |
| 50% | 0.25 | 52.1% | combined | 3 / 128 (2-4) | 0 |
| 50% | 0.5 | 54.8% | combined | 3 / 128 (2-4) | 0 |
| 50% | 0.75 | 70.9% | combined | 4 / 128 (4-4) | 0 |
| 50% | 1 | 72.7% | combined | 4.5 / 128 (4-5) | 0 |
| 75% | 0 | 75.0% | combined | 3.5 / 192 (3-4) | 0 |
| 75% | 0.25 | 75.3% | combined | 4 / 192 (3-5) | 0 |
| 75% | 0.5 | 78.3% | combined | 5 / 192 (5-5) | 0 |
| 75% | 0.75 | 83.0% | combined | 5 / 192 (5-5) | 0 |
| 75% | 1 | 85.5% | combined | 4.5 / 192 (4-5) | 0 |
| 100% | 0 | 100.0% | combined | 5 / 256 (5-5) | 0 |
| 100% | 0.25 | 100.0% | combined | 5 / 256 (5-5) | 0 |
| 100% | 0.5 | 100.0% | combined | 5 / 256 (5-5) | 0 |
| 100% | 0.75 | 100.0% | combined | 5 / 256 (5-5) | 0 |
| 100% | 1 | 100.0% | combined | 5 / 256 (5-5) | 0 |

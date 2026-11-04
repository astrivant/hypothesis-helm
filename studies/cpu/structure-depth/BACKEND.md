# Backend execution evidence

Requested engine: `reference`. Observed engines: reference. Status: **complete**.
Observed device types: none recorded.

Compiled work evaluates finite schema predicates. Helm rendering, template specialization, seeded selection, failure callbacks and reporting remain on the host. No end-to-end GPU speedup is implied.

| Counter | Observed |
| --- | ---: |
| physical cases | 0 |
| logical cases | 9216 |
| committed cases | 7552 |
| unknown cases | 9216 |
| batches | 0 |

Physical evaluations include speculative work; committed cases are planner selections, not completed chart tests.

Exact run receipt (local run data)

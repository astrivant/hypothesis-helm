# Repository refresh helpers

[Full refresh command](../README.md#reproduce-the-full-project-run) · [Benchmark results](../../studies/README.md)

These scripts prepare charts, run measurements, generate plots and publish reports.
The operation inventory lives in `pkg/hypothesis_helm/benchmarking/refresh/plan.py`.

Refresh workspaces and internal records live under `.cache/refresh/refresh-<epoch>/`.
That includes logs, timestamps, process journals, verification results, source snapshots and checksum inventories.
They are generated when needed and are not required in a fresh checkout.

Published measurements, plots and chart recipes remain under `studies/` and `benchmarks/fixture/`.
Repository scan reports remain under `docs/reports/`.

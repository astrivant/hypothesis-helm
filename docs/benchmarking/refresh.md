# Repository refresh helpers

<!-- toc:start -->
**Table of contents**

- [Parallel refresh on GitHub Actions](#parallel-refresh-on-github-actions)
<!-- toc:end -->

[Full refresh command](README.md#reproduce-the-full-project-run) · [Benchmark results](../../studies/README.md)

These scripts prepare charts, run measurements, generate plots and publish reports.
The operation inventory lives in `pkg/hypothesis_helm/benchmarking/refresh/plan.py`.

Refresh workspaces and internal records live under `.cache/refresh/refresh-<epoch>/`.
That includes logs, timestamps, process journals, verification results, source snapshots and checksum inventories.
They are generated when needed and are not required in a fresh checkout.

Published measurements, plots and chart recipes remain under `studies/` and `pkg/hypothesis_helm/benchmarking/assets/fixture/`.
Repository scan reports remain under `docs/reports/`.

## Parallel refresh on GitHub Actions

Run the **Benchmarks** workflow manually with **full-refresh** enabled. Preparation checks the project and snapshots its
inputs once. GitHub then runs each declared study on a separate runner, using the same source snapshot and parameters.
The matrix comes from the Python study inventory, so adding a study also adds its CI job.
There is no `max-parallel` setting: GitHub schedules as many jobs as the account's capacity and runner availability permit.
See [GitHub's matrix concurrency documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idstrategymax-parallel).

Each study owns its output directory, status file and process journal. A failed study retains diagnostics without cancelling
other studies. The final job requires every study to succeed, verifies the merged measurements, publishes plots under `studies/`,
then runs Bitnami followed by Prometheus. Reports and logs are retained as workflow artifacts for 30 days.
Set `HH_CI_RUNNER` to override the default `ubuntu-latest-8-cores` runner label.

After pushing the workflow changes, launch it with:

```sh
gh workflow run benchmarks.yml -f full-refresh=true
```

Local `bash scripts/project-run.sh hypothesis-helm-refresh` still runs timing studies sequentially on one machine to avoid CPU contention affecting
measurements. Its `--workers` option controls independent operations within that machine; the GitHub matrix supplies separate
machines for concurrent studies. Each GitHub study job has a six-hour execution limit.

Sensitivity measures 48 input changes and all 1,128 pairs on the shared benchmark chart, with 64 structural components and a nine-minute budget.
It retains the chart sources and mutation inputs, before publication and repository scans.
Publication updates studies/sensitivity/ while preserving personal runs in studies/sensitivity/runs/.
The standalone `hypothesis-helm-benchmark sensitivity` command also updates that study automatically after a successful run.
Supplying `--output` keeps its results separate; refresh uses this option and publishes after verification.

# Documentation

[Project README](../README.md)

Run repository command examples from the checkout root unless stated otherwise.

- [Getting started](getting-started/README.md): installation, chart testing, and saved suites.
- [Bitnami scan report](reports/bitnami.md): combined PDF, per-chart findings, and retained data.
- [Prometheus Community scan report](reports/prometheus.md): combined PDF, per-chart findings, and retained data.
- [Repository scanning](scanning/README.md): recursive discovery and Markdown/PDF reports.
- [Input inventory](inputs/README.md): missing fields, coverage measurements, and minimal-values dumps.
- [Architecture](architecture/README.md): the testing pipeline and a worked example.
- [Execution](execution/README.md): parallelism, sharding, dry runs, and execution budgets.
- [CI examples](ci/README.md): GitHub Action, CircleCI, and GitLab configuration.
- [Benchmarking](benchmarks/README.md): local shards, generated charts, and plots.
- [CLI reference](cli/README.md): generated command help.
- [Development](development.md): environment, checks, and repository layout.

## Detailed reference

- [Testing behavior](usage.md): schemas, coverage, validation, caching, and output.
- [CI integration](ci.md): provider detection, action inputs, artifacts, and publishing.
- [Safe pruning](safe-pruning.md): supported templates and exact-equivalence proofs.
- [Generated suite](../examples/generated-workload/test_chart_values.py): emitted Python tests.
- [Astrivant observation](../examples/astrivant-observation.md): a schema/template mismatch.

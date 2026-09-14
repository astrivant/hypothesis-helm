# Documentation

[Project README](../README.md)

Run repository command examples from the checkout root unless stated otherwise.

- [Getting started](getting-started/README.md): installation, chart testing, and saved suites.
- [Bitnami scan report](reports/bitnami.md): combined PDF, per-chart findings, and retained data.
- [Prometheus Community scan report](reports/prometheus.md): combined PDF, per-chart findings, and retained data.
- [Repository scanning](scanning/README.md): local testing, remote fetching, recursive discovery, and Markdown/PDF reports.
- [Input inventory](inputs/README.md): missing fields, minimal values, input-to-output graphs, and output complexity scores.
- [Architecture](architecture/README.md): input discovery, test generation, rendering, and validation.
- [Compiler](compiler/README.md): syntax trees, analysis passes, and diagrams explaining selection decisions.
- [Execution](execution/README.md): parallelism, sharding, dry runs, and execution budgets.
- [Adaptive filtering](adaptive-filtering/README.md): how benchmark evidence determines which tests can be sampled and how many to keep.
- [CI examples](ci/README.md): GitHub Action, CircleCI, and GitLab configuration.
- [Benchmarking](../benchmarks/README.md): local shards, generated charts, and plots.
- [Check codes](rules/README.md): built-in checks and per-project opt-outs.
- [CLI reference](cli/README.md): generated command help.
- [Development](development.md): environment, checks, and repository layout.

## Detailed reference

- [Testing behavior](usage.md): schemas, coverage, validation, caching, and output.
- [CI integration](ci.md): provider detection, action inputs, artifacts, and publishing.
- [Safe pruning](safe-pruning.md): supported templates and exact-equivalence proofs.
- [Generated suite](../examples/generated-workload/test_chart_values.py): emitted Python tests.

# Hypothesis

<img src="img/logos/logo-transparent.png" alt="Astrivant logo" width="25%" />

Property-based testing for Helm charts. Hypothesis generates typed inputs from
values schemas and template references, renders your chart, and reduces failures
from combinations of Helm chart inputs to reproducible examples.

- Audit template references, values schemas, and missing defaults.
- Inspect conservative minimal values and measure variation across identified input fields.
- Generate typed property tests and shrink failures to reproducible inputs.
- Choose permutation coverage, with exhaustive testing for small finite spaces.
- Skip provably equivalent renders or opt into sampling to reduce test volume.
- Preview coverage and runtime estimates; set execution budgets and shard tests across workers.
- Scan local, Git, and authenticated Helm repositories; build dependencies and export Markdown/PDF reports.
- Integrate Kubernetes schema validation and optional security checks into CI.
- Generate benchmark charts and compare coverage, bug discovery, and scaling with plots.

We recommend a **manual CI check on trunk before tagging a service release**, to
exercise the sprint's accumulated changes. Run fresh tests, review the report,
and tag the tested commit. See the [release-check workflow and cache retention](docs/ci/README.md).

## Table of contents

- [Install](#install)
- [Audit, test, or scan?](#audit-test-or-scan)
- [Quick start](#quick-start)
- [Guides](#guides)
- [Test case: Bitnami charts](#test-case-bitnami-charts)
- [Test case: Prometheus Community charts](#test-case-prometheus-community-charts)
- [Development](#development)
- [License](#license)

## Install

Requires Helm 4 and Python 3.13+.

```sh
PYTHON=python3.13 helm plugin install https://github.com/astrivant/hypothesis-helm
```

For a local checkout, replace the repository URL with `.`.

Install the optional benchmark tools with:

```sh
pip install "hypothesis-helm[benchmarking]"
hypothesis-helm-benchmark --help
```

See [Benchmarking](docs/benchmarks/README.md) for chart generation and plot commands.

## Audit, test, or scan?

| Command | Use it for | What it does |
| --- | --- | --- |
| `audit ./chart` | Understanding one chart's input contract. | Statically compares values, schema, and template references. Reports missing defaults, undocumented fields, and unresolved access as JSON. Renders only when an export option requests verification or output observation. |
| `test ./chart` | Finding failures in one chart. | Generates inputs, renders them with Helm, checks the manifests, and shrinks failures into reproducible examples. Saves test results and failing values. |
| `scan SOURCE` | Reviewing charts from local, Git, or Helm repositories. | Discovers charts, builds dependencies in isolated copies, runs Helm lint and chart tests, and records each chart's outcome. `--report` adds combined Markdown/PDF reports. Also accepts individual repository/OCI charts and public Helm indexes. |

`test` requires a values schema and dependencies already available in the chart.
`audit` also works without a schema. For schema-less charts, `scan` runs baseline
checks; adding `--filter` enables inferred-input testing and deferred robustness
sampling. Skipped charts and incomplete coverage remain explicit in scan results.

Use `--export-minimal-values` to save example values with validation status, or
`--export-topological-graph` to inspect the input-to-output map. See
[verification and field inventory](docs/inputs/README.md).

### Quick start

```sh
helm hypothesis test ./chart
```

Audit values, choose interaction coverage, or preview a run:

```sh
helm hypothesis audit ./chart
helm hypothesis test ./chart --permutations 2
helm hypothesis test ./chart --dry-run
```

Small supported finite spaces are enumerated automatically. Larger finite spaces
use pairwise coverage; unsupported domains use per-path property tests. Reports
and generated artifacts go to `reports/hypothesis-helm/`.

See [Getting started](docs/getting-started/README.md) for saved suites, validation,
and coverage options.

Scan a repository and write Markdown/PDF summaries:

```sh
helm hypothesis scan ./charts --report
helm hypothesis scan https://github.com/bitnami/charts.git --filter --report
helm hypothesis scan prometheus-community/prometheus --filter --report
helm hypothesis scan prometheus-community --filter --report
```

See [Repository scanning](docs/scanning/README.md) for authentication, public indexes, version selection, and dependency handling.

## Guides

| Guide | Contents |
| --- | --- |
| [Architecture](docs/architecture/README.md) | How chart values become tests, with a worked example. |
| [Execution](docs/execution/README.md) | Parallel workers, sharding, estimates, and time limits. |
| [CI examples](docs/ci/README.md) | GitHub Action, CircleCI, and GitLab setup. |
| [Benchmarking](docs/benchmarks/README.md) | Local shard commands, chart generation, and measured plots. |
| [CLI reference](docs/cli/README.md) | Generated command and option reference. |
| [Development](docs/development.md) | Contributor setup, checks, and repository map. |

[All documentation](docs/README.md) includes detailed behavior and the
[exact-equivalence pruning contract](docs/safe-pruning.md).

## Test case: Bitnami charts

We scanned **115 Bitnami charts**, recording **19,612 test attempts** with filtering
and a five-minute budget per chart. The results include render failures, chart
validation rejections, and tooling limitations; confirmed chart bugs require triage.

Read the [scan results](docs/reports/bitnami.md) for per-chart findings and
reproducing inputs, download the [combined PDF](docs/reports/bitnami.pdf), or inspect
the [retained logs and data](docs/reports/bitnami-runs/bitnami-charts_1789260948/README.md).
The [chart topology catalog](docs/benchmarks/chart-topologies/README.md) includes
directed dependency graphs and their mathematical measurements.

## Test case: Prometheus Community charts

We scanned **46 Prometheus Community charts**, recording **6,515 test attempts**
with the same filtering and five-minute budget per chart. Results include input-test
failures, a baseline configuration failure, missing values, and incomplete coverage.

Read the [scan results](docs/reports/prometheus.md), download the
[combined PDF](docs/reports/prometheus.pdf), or inspect the
[retained logs and data](docs/reports/prometheus-runs/prometheus-charts_1789260855/README.md).
Its dependency graphs are also in the [topology catalog](docs/benchmarks/chart-topologies/README.md).

## Development

```sh
env -u VIRTUAL_ENV -u PYENV_VERSION -u PYENV_VIRTUAL_ENV poetry install
bash scripts/check.sh
```

## License

[GNU General Public License v3.0 only](LICENSE).

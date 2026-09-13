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
- Scan chart repositories, build dependencies, and export Markdown/PDF reports.
- Integrate Kubernetes schema validation and optional security checks into CI.
- Generate benchmark charts and compare coverage, bug discovery, and scaling with plots.

## Use case: Bitnami charts

We scanned **115 Bitnami charts**, recording **19,846 test attempts** with filtering
and a five-minute budget per chart. The results include render failures, chart
validation rejections, and tooling limitations; confirmed chart bugs require triage.

Read the [scan results](docs/reports/bitnami.md) for per-chart findings and
reproducing inputs, download the [combined PDF](docs/reports/bitnami.pdf), or inspect
the [retained logs and data](docs/reports/bitnami-runs/bitnami-charts_1789251211/README.md).

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
| `scan SOURCE` | Reviewing every chart in a repository. | Recursively discovers charts, builds dependencies in isolated copies, runs Helm lint and chart tests, and records each chart's outcome. `--report` adds combined Markdown/PDF reports. Accepts local directories and HTTPS/SSH Git URLs. |

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
```

See [Repository scanning](docs/scanning/README.md) for values files and dependency handling.

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

## Development

```sh
env -u VIRTUAL_ENV -u PYENV_VERSION -u PYENV_VIRTUAL_ENV poetry install
bash scripts/check.sh
```

## License

[GNU General Public License v3.0 only](LICENSE).

# Hypothesis

<img src="img/logos/logo-transparent.png" alt="Astrivant logo" width="25%" />

Test Helm charts with automatically generated `values.yaml` inputs. Built on Python's
Hypothesis<sup>[\[1\]](https://github.com/HypothesisWorks/hypothesis/)</sup> testing framework, this tool
generates inputs from declared or inferred types, renders your charts with Helm, and
checks for failures. When a property-based test fails, Hypothesis simplifies the input
to a small example you can reproduce. Filtering skips redundant renders, while optional
sampling reduces the number of inputs tested so you can cover more charts within your
time budget.

- Audit templates, values schemas, and missing defaults.
- Generate a minimal values schema.
- Choose permutation coverage, with exhaustive testing for small finite spaces.
- Traverse unique value paths randomly with a reproducible seed, or choose linear, shallow, or deep order.
- Skip provably equivalent renders or opt into sampling to reduce test volume.
- Preview coverage and runtime estimates; set execution budgets and shard tests across workers.
- Test local chart trees or scan remote Git and authenticated Helm repositories; build dependencies and export Markdown/PDF reports.
- Integrate Kubernetes schema validation and optional security checks into CI with [kubesec](https://github.com/controlplaneio/kubesec) and [kubeconform](https://github.com/yannh/kubeconform).

We recommend a **manual CI check on trunk before tagging a service release**, to
exercise the sprint's accumulated changes. Run fresh tests, review the report,
and tag the tested commit. See the [release-check workflow and cache retention](docs/ci/README.md).

## Table of contents

- [Hypothesis](#hypothesis)
  - [Table of contents](#table-of-contents)
  - [Install](#install)
  - [Example: catch a failure hidden by defaults](#example-catch-a-failure-hidden-by-defaults)
  - [Audit, test, or scan?](#audit-test-or-scan)
    - [Quick start](#quick-start)
  - [Guides](#guides)
  - [Test case: Bitnami charts](#test-case-bitnami-charts)
  - [Test case: Prometheus Community charts](#test-case-prometheus-community-charts)
  - [Development](#development)
  - [License](#license)
  - [Acknowledgements and citation](#acknowledgements-and-citation)

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
To rerun all project checks, benchmarks, plots, and repository reports, see the
[full refresh command](docs/benchmarks/README.md#reproduce-the-full-project-run).

## Example: catch a failure hidden by defaults

The [broken example chart](examples/broken) renders successfully with its default
`replicas: 1`. Its values schema also permits `replicas: 0`, but its template rejects
that value. Testing only the defaults would miss this mismatch.

From this repository's root, run:

```sh
helm hypothesis test examples/broken --match replicas --max-examples 4 \
  --seed 0 --shard none --rerun all --artifact-dir reports/example
```

Hypothesis generates values allowed by the schema and finds this failing input:

```yaml
replicas: 0
```

Helm reports `replicas=0 is documented but unsupported`, and the command exits
with a failure. You now have a concrete input to reproduce the problem and decide
whether to fix the template or narrow the schema. Results are saved in `reports/example/`.

Another common bug is an unquoted ConfigMap value. A default of `banner: Ready`
works with the template `banner: {{ .Values.banner }}`. But the equally valid input
`banner: "Release: ready"` makes that template emit `banner: Release: ready`, which
is invalid YAML. Hypothesis can expose this by varying values and rendering the
chart locally, without a Kubernetes cluster. The fix is to quote the template value:
`banner: {{ .Values.banner | quote }}`.

## Audit, test, or scan?

| Command | Use it for | What it does |
| --- | --- | --- |
| `audit ./chart` | Understanding one chart's input contract. | Statically compares values, schema, and template references. Reports missing defaults, undocumented fields, and unresolved access as JSON. Renders only when an export option requests verification or output observation. |
| `test PATH` | Testing a local chart or directory of charts. | Discovers local charts recursively, generates inputs, renders them with Helm, and records failures. `--report` writes combined Markdown/PDF results. |
| `scan SOURCE` | Testing charts fetched from remote repositories. | Fetches a Git repository, Helm repository/chart, public Helm index, or OCI chart, then discovers and tests its charts. Local paths use `test`. |

`test` and `scan` infer input-generation strategies when a chart has no values schema.
Recursive testing builds dependencies in isolated copies; single-chart suite controls
use dependencies already available in the chart. `audit` also works without a schema. `--filter` restricts
generation before traversal. Skipped charts and incomplete coverage remain explicit.

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

Test local charts or fetch remote charts, with Markdown/PDF summaries:

```sh
helm hypothesis test ./charts --report
helm hypothesis scan https://github.com/bitnami/charts.git --filter --report
helm hypothesis scan prometheus-community/prometheus --filter --report
helm hypothesis scan prometheus-community --filter --report
```

See [Repository scanning](docs/scanning/README.md) for authentication, public indexes, version selection, and dependency handling.

## Guides

| Guide | Contents |
| --- | --- |
| [Architecture](docs/architecture/README.md) | Input discovery, test generation, rendering, and validation. |
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

## Acknowledgements and citation

This project builds on [Hypothesis](https://github.com/HypothesisWorks/hypothesis/),
the property-based testing framework for Python. Its authors recommend the following
paper in their [citation guidance](https://github.com/HypothesisWorks/hypothesis/blob/master/CITATION.cff):

MacIver et al. (2019). [Hypothesis: A new approach to property-based testing](https://doi.org/10.21105/joss.01891).
*Journal of Open Source Software*, 4(43), 1891.

# Hypothesis

<img src="img/logos/logo-transparent.png" alt="Astrivant logo" width="25%" />

Test Helm charts with automatically generated `values.yaml` inputs. Built on Python's
Hypothesis<sup>[\[1\]](https://github.com/HypothesisWorks/hypothesis/)</sup> testing framework, this tool
generates inputs from declared or inferred types<sup>[\[2\]](docs/inputs/README.md#declared-and-inferred-types)</sup>,
renders your charts with Helm, and
checks for failures. When a property-based test fails, Hypothesis simplifies the input
to a small example you can reproduce. Filtering skips redundant renders, while optional
sampling techniques reduce the number of inputs tested so you can cover more charts within your
time budget.

- Audit templates, values schemas, and missing defaults.
- Generate a minimal values schema.
- Choose permutation coverage, with exhaustive testing for small finite spaces.
- Traverse unique value paths randomly with a reproducible seed, or choose linear, root-first, or leaf-first order.
- Skip provably equivalent renders or opt into [calibrated sampling](docs/adaptive-filtering/README.md) to reduce test volume.
- Recognize explicit configuration requirements with `--filter`, test dependent settings together, and report rejections separately.
- Discover dependency activation controls and exercise child settings with their subchart enabled, including aliases and nested dependencies.
- Show changed values and manifest fields in failure reports, with verified JSON replay of saved changes.
- Preview coverage and runtime estimates; set execution budgets and shard tests across workers.
- Test local chart trees or scan remote Git and authenticated Helm repositories; build dependencies and export Markdown/PDF reports.
- Integrate Kubernetes schema validation and optional security checks into CI with [kubesec](https://github.com/controlplaneio/kubesec) and [kubeconform](https://github.com/yannh/kubeconform).

Choose coverage for each stage of development:

| When | Recommended mode | Starting CPU / RAM per CI job | Local workers | CI shards |
| --- | --- | --- | ---: | ---: |
| MR / PR | `--filter-adaptive` | 2 vCPU / 4 GiB | `--jobs 2` | 1 |
| Changes on `main` | `--filter` | 2 vCPU / 4 GiB | `--jobs 2` | 1 |
| Before tagging a release | `--exhaustive` | 2 vCPU / 4 GiB | `--jobs 2` | 2 |

These are starting estimates for one chart at a time, not measured minimum requirements.
Start with 2 vCPU / 4 GiB and two workers per job, including for large dependency-heavy charts; increase resources after measuring throughput.
The two-job release allocation totals 4 vCPU / 8 GiB and four workers, with different charts assigned to each job.
Exhaustive runs use parallel Helm processes; finite interaction execution remains serial. Repository path queues are local to one CI job;
distributed shards apply to the separate generated-suite workflow.<sup>[\[3\]](docs/ci/resources.md)</sup>

Run the pre-tag check manually on the release commit and review its coverage report before tagging.
Exhaustive coverage requires a finite domain and a completed run; time-limited runs remain incomplete.
See the [CI workflow and release-check requirements](docs/ci/README.md#recommended-workflow).

## Table of contents

- [Hypothesis](#hypothesis)
  - [Table of contents](#table-of-contents)
  - [Install](#install)
  - [Examples: failures hidden by defaults](#examples-failures-hidden-by-defaults)
  - [Audit, test, or scan?](#audit-test-or-scan)
    - [Quick start](#quick-start)
  - [Guides](#guides)
  - [Test case: Bitnami charts](#test-case-bitnami-charts)
  - [Test case: Prometheus Community charts](#test-case-prometheus-community-charts)
  - [Development](#development)
  - [License](#license)
  - [Citation](#citation)

## Install

Requires Helm 4 and Python 3.13+.

Install the Helm plugin and verify that it is available:

```sh
PYTHON=python3.13 helm plugin install https://github.com/astrivant/hypothesis-helm
helm hypothesis --help
```

To install from a local checkout instead, run these commands from the project root:

```sh
PYTHON=python3.13 helm plugin install .
helm hypothesis --help
```

Then, if you want the optional benchmark tools, install them with pip:

```sh
pip install "hypothesis-helm[benchmarking]"
hypothesis-helm-benchmark --help
```

See [Benchmarking](benchmarks/README.md) for chart generation and plot commands.
Browse the [flame graphs](studies/flamegraphs/README.md) to see time spent in Python calls during a scaling smoke test.
The [configurable stress chart](benchmarks/chart) combines known defects and topology
controls in one fixture; its [guide](benchmarks/fixture/README.md) explains how to reduce them one step at a time.
See [random sampling results](studies/sampling/README.md) for the measured
tradeoff between sample size and known defect discovery.
To rerun all project checks, benchmarks, plots, and repository reports, see the
[full refresh command](benchmarks/README.md#reproduce-the-full-project-run).

## Examples: failures hidden by defaults

A ConfigMap template containing `banner: {{ .Values.banner }}` works with the default
`banner: Ready`. But `banner: "Release: ready"` produces `banner: Release: ready`,
which is invalid YAML. Hypothesis can find this by generating inputs and rendering
the chart locally. Fix it with `banner: {{ .Values.banner | quote }}`.

The same idea applies beyond quoting:

- **Optional branches:** A feature is disabled by default. Enabling it reaches a template
  branch that reads a missing nested value and fails. Disabled subcharts can hide failures this way too.
- **Boundary values:** The schema allows an empty list, but the template always reads its
  first item. The populated default works; an empty list causes rendering to fail.
- **Interacting settings:** Two switches each work on their own. Enabling both reaches a
  shared branch that passes the wrong type to a template function. Testing each switch
  separately misses it.

## Audit, test, or scan?

| Command | Use it for | What it does |
| --- | --- | --- |
| `audit ./chart` | Understanding one chart's input contract. | Statically compares values, schema, and template references. Reports missing defaults, undocumented fields, unresolved access, and potential output complexity as JSON. Renders only when an export option requests verification or output observation. |
| `test PATH` | Testing a local chart or directory of charts. | Discovers local charts recursively, generates inputs, renders them with Helm, and records failures. `--report` writes combined Markdown/PDF results. |
| `scan SOURCE` | Testing charts fetched from remote repositories. | Fetches a Git repository, Helm repository/chart, public Helm index, or OCI chart, then discovers and tests its charts. Local paths use `test`. |

`test` and `scan` infer input-generation strategies when a chart has no values schema.
Recursive testing builds dependencies in isolated copies; single-chart suite controls
use dependencies already available in the chart. `audit` also works without a schema. `--filter` restricts
generation before traversal. Skipped charts and incomplete coverage remain explicit.

The audit's [complexity score](docs/inputs/README.md#potential-output-complexity) describes the largest
manifest tree across the allowed values, including resources disabled by defaults. Unsupported or oversized
input spaces have an unknown maximum, with any supported evidence reported separately.

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

Disable selected checks with [stable rule codes and an ignore file](docs/rules/README.md).
The [root configuration](.hypothesis-helm.yaml) lists every code commented out.

| Guide | Contents |
| --- | --- |
| [Architecture](docs/architecture/README.md) | Input discovery, test generation, rendering, and validation. |
| [Compiler](docs/compiler/README.md) | Pass flow, syntax trees, and illustrated compiler decisions. |
| [Execution](docs/execution/README.md) | Parallel workers, sharding, estimates, and time limits. |
| [CI examples](docs/ci/README.md) | GitHub Action, CircleCI, and GitLab setup. |
| [Benchmarking](benchmarks/README.md) | Local shard commands, chart generation, and measured plots. |
| [CLI reference](docs/cli/README.md) | Generated command and option reference. |
| [Development](docs/development.md) | Contributor setup, checks, and repository map. |

[All documentation](docs/README.md) includes detailed behavior and the
[exact-equivalence pruning contract](docs/safe-pruning.md).

## Test case: Bitnami charts

<!-- refresh:bitnami:start -->
We scanned **115 Bitnami charts**, recording **101,799 test attempts** with filtering
and a five-minute budget per chart. The results include render failures, chart
validation rejections, and tooling limitations; confirmed chart bugs require triage.

Read the [scan results](docs/reports/bitnami.md) for per-chart findings and
reproducing inputs, download the [combined PDF](docs/reports/bitnami.pdf), or inspect
the [retained logs and data](docs/reports/bitnami-runs/bitnami-charts_1789311940/README.md).
<!-- refresh:bitnami:end -->
The [chart topology catalog](studies/chart-topologies/README.md) includes
directed dependency graphs and their mathematical measurements.

## Test case: Prometheus Community charts

<!-- refresh:prometheus:start -->
We scanned **46 Prometheus Community charts**, recording **94,833 test attempts**
with the same filtering and five-minute budget per chart. The report distinguishes
observed input failures, blocked checks, and incomplete coverage.

Read the [scan results](docs/reports/prometheus.md), download the
[combined PDF](docs/reports/prometheus.pdf), or inspect the
[retained logs and data](docs/reports/prometheus-runs/prometheus-charts_1789311940/README.md).
<!-- refresh:prometheus:end -->
Its dependency graphs are also in the [topology catalog](studies/chart-topologies/README.md).

## Development

```sh
env -u VIRTUAL_ENV -u PYENV_VERSION -u PYENV_VIRTUAL_ENV poetry install
bash scripts/check.sh
```

The check command runs pytest in parallel, automatically choosing the worker count from
the runner's CPU count. CI and the full benchmark refresh use the same command.
Set `PYTEST_WORKERS=2` to choose a fixed count, or use
`bash scripts/check.sh -n 0` for serial execution. To run only tests in parallel:

```sh
bash scripts/project-run.sh pytest -n auto --dist worksteal
```

Development dependencies include shfmt. Pre-commit formats maintained shell scripts;
`scripts/check.sh` checks their formatting in CI. Shell indentation is configured in
`.editorconfig`. To format them manually:

```sh
bash scripts/project-run.sh shfmt -w scripts pkg/hypothesis_helm/integrations
```

## License

[GNU General Public License v3.0 only](LICENSE).

## Citation

This project builds on [Hypothesis](https://github.com/HypothesisWorks/hypothesis/),
the property-based testing framework for Python. Its authors recommend the following
paper in their [citation guidance](https://github.com/HypothesisWorks/hypothesis/blob/master/CITATION.cff):

MacIver et al. (2019). [Hypothesis: A new approach to property-based testing](https://doi.org/10.21105/joss.01891).
*Journal of Open Source Software*, 4(43), 1891.

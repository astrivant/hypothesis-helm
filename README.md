# Hypothesis

<img src="img/logos/logo-transparent.png" alt="Astrivant logo" width="25%" />

Property-based testing for Helm charts. Hypothesis generates typed inputs from
values schemas and template references, renders your chart, and reduces failures
from combinations of Helm chart inputs to reproducible examples.

- Audit template references, values schemas, and missing defaults.
- Generate typed property tests and shrink failures to reproducible inputs.
- Choose permutation coverage, with exhaustive testing for small finite spaces.
- Skip provably equivalent renders or opt into sampling to reduce test volume.
- Preview coverage and runtime estimates; set execution budgets and shard tests across workers.
- Scan chart repositories, build dependencies, and export Markdown/PDF reports.
- Integrate Kubernetes schema validation and optional security checks into CI.
- Generate benchmark charts and compare coverage, bug discovery, and scaling with plots.

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

## Quick start

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

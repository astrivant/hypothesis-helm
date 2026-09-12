# Hypothesis

<img src="img/logos/logo-transparent.png" alt="Astrivant logo" width="25%" />

Property-based testing for Helm charts. Hypothesis generates typed inputs from
values schemas and template references, renders your chart, and reduces failures
from combinations of Helm chart inputs to reproducible examples.

## Install

Requires Helm 3 and Python 3.13+.

```sh
PYTHON=python3.13 helm plugin install https://github.com/astrivant/hypothesis-helm
```

For a local checkout, replace the repository URL with `.`.

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

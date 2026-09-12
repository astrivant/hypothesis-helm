# Development

This document is for contributors modifying the framework. End-user chart testing
is entirely through [Helm commands](usage.md).

## Environment

The project follows Astrivant's Python 3.13, Poetry and package-local test layout.
`.python-version` selects the interpreter and `poetry.toml` keeps the virtualenv
inside the checkout. Preserve an older environment elsewhere before recreating it
when upgrading from Python 3.10.

```sh
python3.13 -m venv .venv
env -u VIRTUAL_ENV -u PYENV_VERSION -u PYENV_VIRTUAL_ENV poetry install
bash scripts/project-python.sh -m pre_commit install
```

`scripts/project-python.sh` uses this checkout's interpreter even when another
virtual environment is active. Pytest is a runtime dependency because Helm runs
generated suites inside the plugin environment; linting tools remain development
dependencies. The Poetry lock pins contributor/CI dependencies. Plugin installation
resolves the package's runtime constraints.

## Checks

```sh
bash scripts/check.sh
poetry build
```

The validation command runs Ruff lint/format, strict mypy, pydocstyle, pydoclint,
the generated CLI reference check, and the package's pytest suite. Source and test docstrings follow Astrivant's
Google-style convention. No type-checking exclusions weaken the source checks.

After changing CLI arguments, regenerate the [CLI reference](cli/README.md):

```sh
bash scripts/project-python.sh -m cogapp -r docs/cli/README.md
```

Unit and integration tests live under `pkg/hypothesis_helm/tests`. Helm must be
available for render tests; the neighboring Astrivant audit skips when absent.
`ASTRIVANT_CHART=<path>` opts into the full whole-chart Astrivant integration gate.
Fixture schemas deliberately containing documentation gaps are not processed by
a Helm README/schema generator.

## Plugin verification

```sh
PYTHON=python3.13 helm plugin install .
helm hypothesis test examples/workload --max-examples 5
helm hypothesis generate examples/workload --output /tmp/generated-workload
helm hypothesis run /tmp/generated-workload
```

CircleCI checks the framework and the end-user plugin workflow, then builds the
wheel and source distribution. Generated-suite execution uses the plugin's
interpreter, with unrelated pytest configuration and auto-loaded plugins disabled.
The saved suite's own code and conftest remain editable.

Publishing and remote repository-setting changes are not automated by local checks.

## Pre-commit hook

The repository publishes `helm-hypothesis` in `.pre-commit-hooks.yaml`. It runs
`helm hypothesis test` with `language: system`, so Helm and the Hypothesis Helm
plugin must already be installed. Set `args` to the chart directory; filenames
are not passed to the command, and execution is serial.

For a neighboring checkout such as Astrivant, install the plugin from that
checkout and use a local hook (no remote revision or committed plugin changes
are required):

```sh
# From the Astrivant repository:
helm plugin install ../hypothesis-helm
# After changing Python code in the plugin checkout:
helm plugin update hypothesis
pre-commit run helm-hypothesis --all-files
```

```yaml
- repo: local
  hooks:
    - id: helm-hypothesis
      name: Test Astrivant Helm values with Hypothesis
      entry: helm hypothesis test
      language: system
      args: [helm/astrivant, --max-examples, '10', --seed, '0']
      files: ^(helm/astrivant/|helm/vendor/|\.pre-commit-config\.yaml$)
      pass_filenames: false
      require_serial: true
```

Pre-commit local hooks repeat the manifest fields rather than importing another
checkout's manifest. Chart or vendored dependency changes trigger the hook.
A failing property blocks the commit; the generated suite and results are saved
under `reports/hypothesis-helm`. Ten examples per property keeps the default
sampling budget modest; this does not guarantee complete branch coverage.

## Package organization

The package root contains the CLI and the lazy public API (`Chart`, `check_chart`,
`coalesce`, and `generate_tests`). Related implementation modules live together:

| Subpackage | Responsibility |
| --- | --- |
| `charts/` | Template discovery, YAML handling, property generation, and chart rendering. |
| `schemas/` | Value contracts, finite schema enumeration, and Kubernetes API conformity. |
| `execution/` | Suite execution, worker scheduling, PID feedback, process cleanup, and result caching. |
| `reporting/` | Progress display, path logging, and JSON manifest streaming. |
| `integrations/` | CI provider configuration, shard detection, and the GitHub Action adapter. |
| `tests/` | Package-local unit and integration tests. |

Generated suites import runtime helpers from `hypothesis_helm.charts.generated`.
Regenerate previously saved suites with `helm hypothesis generate` after upgrading
from the flat module layout, or update that import in a manually maintained suite.
Helm commands and the public package exports retain their existing names. Result
cache fingerprints cover implementation modules recursively across all subpackages.

## Repository map

| Location | Responsibility |
| --- | --- |
| [`pkg/hypothesis_helm/`](../pkg/hypothesis_helm) | CLI and public API; implementation grouped under charts, schemas, execution, reporting, and integrations. |
| [`pkg/hypothesis_helm/tests/`](../pkg/hypothesis_helm/tests) | Unit tests and real Helm integration tests. |
| [`examples/`](../examples) | Small charts and a checked-in generated workload suite. |
| [`scripts/`](../scripts) | Project interpreter, validation command and Helm plugin hooks. |
| [`action.yml`](../action.yml) | GitHub Action with automatic CI sharding and artifact uploads. |
| [`plugin.yaml`](../plugin.yaml) | Installable Helm plugin manifest. |
| [`.circleci/`](../.circleci) | Python checks, Helm integration and package build verification. |
| [`.github/settings.yml`](../.github/settings.yml) | Declarative repository settings. |
| [`docs/`](.) | Development setup, CLI behavior and testing limitations. |

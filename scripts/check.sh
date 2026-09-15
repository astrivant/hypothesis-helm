#!/usr/bin/env bash
# Run the same shell and Python checks locally and in CI.
set -euo pipefail
cd "$(dirname "$0")/.."
for script in scripts/*.sh benchmarks/*.sh benchmarks/refresh/*.sh pkg/hypothesis_helm/integrations/*.sh; do
  bash -n "$script"
done
bash scripts/project-run.sh shfmt -d scripts benchmarks/*.sh benchmarks/refresh/*.sh pkg/hypothesis_helm/integrations
bash scripts/project-run.sh ruff check pkg examples/generated-workload
bash scripts/project-run.sh ruff format --check pkg examples/generated-workload
bash scripts/project-run.sh mypy
bash scripts/project-run.sh pydocstyle --config=pyproject.toml pkg
bash scripts/project-run.sh pydoclint --config=pyproject.toml pkg
bash scripts/project-run.sh cog --check docs/cli/README.md docs/rules/README.md
# Keep these flags here so generated chart suites do not inherit another worker pool.
bash scripts/project-run.sh pytest -n "${PYTEST_WORKERS:-auto}" --dist worksteal "$@"

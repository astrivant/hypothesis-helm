#!/usr/bin/env bash
# Run the same Python checks locally and in CircleCI.
set -euo pipefail
cd "$(dirname "$0")/.."
for script in scripts/*.sh; do
  bash -n "$script"
done
bash scripts/project-run.sh ruff check pkg examples/generated-workload
bash scripts/project-run.sh ruff format --check pkg examples/generated-workload
bash scripts/project-run.sh mypy
bash scripts/project-run.sh pydocstyle --config=pyproject.toml pkg
bash scripts/project-run.sh pydoclint --config=pyproject.toml pkg
bash scripts/project-run.sh cog --check docs/cli/README.md
bash scripts/project-run.sh pytest "$@"

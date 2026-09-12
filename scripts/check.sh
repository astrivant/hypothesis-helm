#!/usr/bin/env bash
# Run the same Python checks locally and in CircleCI.
set -euo pipefail
cd "$(dirname "$0")/.."
bash scripts/project-python.sh -m ruff check pkg scripts examples/generated-workload
bash scripts/project-python.sh -m ruff format --check pkg scripts examples/generated-workload
bash scripts/project-python.sh -m mypy
bash scripts/project-python.sh -m pydocstyle --config=pyproject.toml pkg scripts
bash scripts/project-python.sh -m pydoclint.main --config=pyproject.toml pkg scripts
bash scripts/project-python.sh -m cogapp --check docs/cli/README.md
bash scripts/project-python.sh -m pytest "$@"

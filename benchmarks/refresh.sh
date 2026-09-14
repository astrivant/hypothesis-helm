#!/usr/bin/env bash
# Run the installed operation coordinator from this checkout.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$PWD/.venv/bin:$PATH"
export PYTHONPATH="$PWD/pkg"
exec hypothesis-helm-refresh "$@"

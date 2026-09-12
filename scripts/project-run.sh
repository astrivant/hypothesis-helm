#!/usr/bin/env bash
# Resolve installed commands from this checkout, ignoring unrelated virtual environments.
set -euo pipefail
cd "$(dirname "$0")/.."
if (($# == 0)); then
  echo "Usage: bash scripts/project-run.sh COMMAND [ARGS...]" >&2
  exit 2
fi
if [[ -d .venv/bin ]]; then
  executable="$(pwd)/.venv/bin/$1"
  shift
  exec "$executable" "$@"
fi
unset VIRTUAL_ENV PYENV_VERSION PYENV_VIRTUAL_ENV
exec poetry run "$@"

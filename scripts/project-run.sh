#!/usr/bin/env bash
# Resolve installed commands from this checkout, ignoring unrelated virtual environments.
set -euo pipefail
cd "$(dirname "$0")/.."
if (($# == 0)); then
    echo "Usage: bash scripts/project-run.sh COMMAND [ARGS...]" >&2
    exit 2
fi
if [[ -d .venv/bin ]]; then
    # Nested tools must resolve from this environment too (for example ci-shell invoking shfmt).
    VIRTUAL_ENV="$(pwd)/.venv"
    export VIRTUAL_ENV
    export PATH="$VIRTUAL_ENV/bin:$PATH"
    executable="$VIRTUAL_ENV/bin/$1"
    shift
    exec "$executable" "$@"
fi
unset VIRTUAL_ENV PYENV_VERSION PYENV_VIRTUAL_ENV
exec poetry run "$@"

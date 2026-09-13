#!/usr/bin/env bash
# Reproduce the complete project checks, measurements, plots, and repository reports.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "${1:-}" == --help ]]; then
  echo 'Usage: poetry run bash scripts/refresh.sh'
  echo 'Requires Helm 4, GNU Parallel, Git, and the project development/benchmark dependencies.'
  echo 'Runs all checks, ten benchmark studies (9m ceilings), topology exports, and both repository tests (5m/chart).'
  exit 0
fi
if (($#)); then
  echo 'Unexpected arguments; use --help.' >&2
  exit 2
fi
export PATH="$PWD/.venv/bin:$PATH"
export PYTHONPATH="$PWD/pkg"
export MPLBACKEND=Agg
for binary in python helm parallel git hypothesis-helm hypothesis-helm-benchmark; do
  command -v "$binary" >/dev/null
done
if [[ "$(helm version --short)" != v4.* ]]; then
  echo 'Put Helm 4 on PATH before running the refresh.' >&2
  exit 2
fi
mkdir -p .cache
if [[ -f .cache/latest-refresh.txt ]]; then
  previous="$(cat .cache/latest-refresh.txt)"
  if [[ -d "$previous" && ! -f "$previous/publication-finished-epoch.txt" ]]; then
    echo "An active or unfinished refresh is recorded at $previous. Inspect it before starting another." >&2
    echo 'After a stopped run has been investigated, remove .cache/latest-refresh.txt to start fresh.' >&2
    exit 2
  fi
fi
if ! mkdir .cache/full-refresh.lock 2>/dev/null; then
  echo 'Another full refresh holds .cache/full-refresh.lock.' >&2
  exit 2
fi
trap 'rmdir .cache/full-refresh.lock' EXIT
printf '%s\n' 'Running project checks and tests.'
bash scripts/check.sh
git submodule update --init --recursive
root=".cache/benchmark-refresh-$(date +%s)"
python docs/benchmarks/refresh/initialize.py "$root"
export PYTHONPATH="$PWD/$root/frozen-source/pkg"
export MPLCONFIGDIR="$PWD/$root/matplotlib"
printf 'Refresh: %s\nProgress and logs: %s/current.txt, %s/postprocess-current.txt, %s/logs/\n' "$root" "$root" "$root" "$root"
bash "$root/run.sh" "$root"
bash "$root/finish-refresh.sh" "$root"
python "$root/update-documentation.py" "$root"
python "$root/verify-publication.py" "$root"
ruff check .
ruff format --check .
cp "$root/publication-verification.json" docs/benchmarks/refresh/
date +%s >"$root/publication-finished-epoch.txt"
printf 'Full refresh complete: %s\n' "$root"

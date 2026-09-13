#!/usr/bin/env bash
set -euo pipefail
chart="${1:?chart}"
sequence="${2:?job sequence}"
slot="${3:?worker slot}"
run_dir="${4:?report directory}"
export HELM_CACHE_HOME="$PWD/$run_dir/helm/cache-$slot"
hypothesis-helm test "$chart" --chart-timeout 5m --filter --max-examples 100 --seed 0 \
  --traversal-strategy random --artifact-dir "$run_dir/runs" \
  > "$run_dir/jobs/$sequence.json" 2> "$run_dir/jobs/$sequence.err"

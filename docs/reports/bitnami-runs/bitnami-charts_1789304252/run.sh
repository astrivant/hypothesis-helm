#!/usr/bin/env bash
set -uo pipefail
run_dir="${1:?pass the retained run directory}"
mkdir -p "$run_dir/runs"
export HELM_REPOSITORY_CONFIG="$PWD/$run_dir/helm/repositories.yaml"
export HELM_PLUGINS="$PWD/$run_dir/helm/plugins"
date +%s > "$run_dir/started-epoch.txt"
parallel --will-cite --jobs 4 --null --joblog "$run_dir/joblog.tsv" \
  'HELM_CACHE_HOME=/Users/emmadoyle/projects/personal/hypothesis-helm/docs/reports/bitnami-runs/bitnami-charts_1789304252/helm/cache-{%} .venv/bin/hypothesis-helm scan {} --helm /tmp/hh-helm4/darwin-arm64/helm --chart-timeout 5m --filter --max-examples 100 --seed 0 --artifact-dir '"$run_dir"'/runs > '"$run_dir"'/jobs/{#}.json 2> '"$run_dir"'/jobs/{#}.err' \
  :::: "$run_dir/charts.txt"
status=$?
date +%s > "$run_dir/finished-epoch.txt"
printf '%s\n' "$status" > "$run_dir/parallel-exit-code.txt"
exit "$status"

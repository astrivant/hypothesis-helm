#!/usr/bin/env bash
set -uo pipefail
run_dir="${1:?report directory}"
export HELM_REPOSITORY_CONFIG="$PWD/$run_dir/helm/repositories.yaml"
export HELM_PLUGINS="$PWD/$run_dir/helm/plugins"
date +%s >"$run_dir/started-epoch.txt"
parallel --will-cite --term-seq TERM,10000,KILL,1000 --jobs 4 --null --joblog "$run_dir/joblog.tsv" \
  bash "$run_dir/chart.sh" '{}' '{#}' '{%}' "$run_dir" :::: "$run_dir/charts.txt"
status=$?
date +%s >"$run_dir/finished-epoch.txt"
printf '%s\n' "$status" >"$run_dir/parallel-exit-code.txt"
exit "$status"

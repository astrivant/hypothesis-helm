#!/usr/bin/env bash
set -uo pipefail
run_dir="${1:?report directory}"
workspace="$run_dir"
if [[ "$workspace" != /* ]]; then workspace="$PWD/$workspace"; fi
export HELM_REPOSITORY_CONFIG="$workspace/helm/repositories.yaml"
export HELM_PLUGINS="$workspace/helm/plugins"
date +%s >"$run_dir/started-epoch.txt"
parallel --will-cite --line-buffer --term-seq TERM,10000,KILL,1000 --jobs 1 --null --joblog "$run_dir/joblog.tsv" \
    bash "$run_dir/chart.sh" '{}' '{#}' '{%}' "$run_dir" :::: "$run_dir/charts.txt"
status=$?
date +%s >"$run_dir/finished-epoch.txt"
printf '%s\n' "$status" >"$run_dir/parallel-exit-code.txt"
exit "$status"

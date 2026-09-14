#!/usr/bin/env bash
set -uo pipefail
root="${1:?refresh directory}"
export HELM_PLUGINS="$PWD/$root/helm/plugins"
export MPLCONFIGDIR="$PWD/$root/matplotlib"
export MPLBACKEND=Agg
mkdir -p "$MPLCONFIGDIR"
date +%s >"$root/started-epoch.txt"
python "$root/prepare-fixtures.py" "$root" >"$root/logs/prepare-fixtures.log" 2>&1 || exit $?
printf '%s\n' 'performance' >"$root/current.txt"
hypothesis-helm-benchmark --parameters "$root/parameters/standard.yaml" run --step 50 --time-limit 9m --max-permutations 600000 --shards 1,2,3,4 --shard none --output "$root/outputs/performance" >"$root/logs/performance.log" 2>&1
status=$?
printf 'performance\t%s\n' "$status" >>"$root/status.tsv"
[[ "$status" -eq 0 ]] || exit "$status"
printf '%s\n' 'discovery' >"$root/current.txt"
hypothesis-helm-benchmark --parameters "$root/parameters/discovery.yaml" discovery --max-strength 6 --time-limit 9m --output "$root/outputs/discovery" >"$root/logs/discovery.log" 2>&1
status=$?
printf 'discovery\t%s\n' "$status" >>"$root/status.tsv"
[[ "$status" -eq 0 ]] || exit "$status"
printf '%s\n' 'bug-density' >"$root/current.txt"
hypothesis-helm-benchmark discovery --input-complexity 8 --max-strength 6 --bug-percent 5 --seed 2026 --time-limit 9m --output "$root/outputs/bug-density" >"$root/logs/bug-density.log" 2>&1
status=$?
printf 'bug-density\t%s\n' "$status" >>"$root/status.tsv"
[[ "$status" -eq 0 ]] || exit "$status"
printf '%s\n' 'sparsity' >"$root/current.txt"
hypothesis-helm-benchmark --parameters "$root/parameters/standard.yaml" sparsity --count 32768 --retain 0.25 --levels 8 --time-limit 9m --output "$root/outputs/sparsity" >"$root/logs/sparsity.log" 2>&1
status=$?
printf 'sparsity\t%s\n' "$status" >>"$root/status.tsv"
[[ "$status" -eq 0 ]] || exit "$status"
printf '%s\n' 'topology-sparsity' >"$root/current.txt"
hypothesis-helm-benchmark --parameters "$root/parameters/topology.yaml" sparsity --count 1024 --levels 5 --time-limit 9m --output "$root/outputs/topology-sparsity" >"$root/logs/topology-sparsity.log" 2>&1
status=$?
printf 'topology-sparsity\t%s\n' "$status" >>"$root/status.tsv"
[[ "$status" -eq 0 ]] || exit "$status"
printf '%s\n' 'matrix' >"$root/current.txt"
hypothesis-helm-benchmark matrix --input-complexity 10 --trim-level 2 --seed 2026 --time-limit 9m --output "$root/outputs/matrix" >"$root/logs/matrix.log" 2>&1
status=$?
printf 'matrix\t%s\n' "$status" >>"$root/status.tsv"
[[ "$status" -eq 0 ]] || exit "$status"
printf '%s\n' 'pca' >"$root/current.txt"
hypothesis-helm-benchmark pca --input-complexity 10 --error-percent 5 --error-seed 1729 --seed 2026 --trim-level 2 --time-limit 9m --output "$root/outputs/pca" >"$root/logs/pca.log" 2>&1
status=$?
printf 'pca\t%s\n' "$status" >>"$root/status.tsv"
[[ "$status" -eq 0 ]] || exit "$status"
printf '%s\n' 'expansion' >"$root/current.txt"
hypothesis-helm-benchmark expansion --input-complexity 10 --error-percent 5 --error-seed 1729 --seed 2026 --trim-level 2 --time-limit 9m --output "$root/outputs/expansion" >"$root/logs/expansion.log" 2>&1
status=$?
printf 'expansion\t%s\n' "$status" >>"$root/status.tsv"
[[ "$status" -eq 0 ]] || exit "$status"
printf '%s\n' 'topology-depth' >"$root/current.txt"
hypothesis-helm-benchmark topology-depth --depths 0 1 2 3 4 5 --time-limit 9m --output "$root/outputs/topology-depth" >"$root/logs/topology-depth.log" 2>&1
status=$?
printf 'topology-depth\t%s\n' "$status" >>"$root/status.tsv"
[[ "$status" -eq 0 ]] || exit "$status"
printf '%s\n' 'nesting' >"$root/current.txt"
hypothesis-helm-benchmark nesting --permutations 8 --time-limit 9m --output "$root/outputs/nesting" >"$root/logs/nesting.log" 2>&1
status=$?
printf 'nesting\t%s\n' "$status" >>"$root/status.tsv"
[[ "$status" -eq 0 ]] || exit "$status"
printf '%s\n' 'stress' >"$root/current.txt"
hypothesis-helm-benchmark stress --time-limit 9m --output "$root/outputs/stress" >"$root/logs/stress.log" 2>&1
status=$?
printf 'stress\t%s\n' "$status" >>"$root/status.tsv"
[[ "$status" -eq 0 ]] || exit "$status"
printf '%s\n' 'sampling' >"$root/current.txt"
hypothesis-helm-benchmark sampling --time-limit 9m --output "$root/outputs/sampling" >"$root/logs/sampling.log" 2>&1
status=$?
printf 'sampling\t%s\n' "$status" >>"$root/status.tsv"
[[ "$status" -eq 0 ]] || exit "$status"
printf '%s\n' 'calibration-variation' >"$root/current.txt"
hypothesis-helm-benchmark calibration --time-limit 9m --output "$root/outputs/calibration-variation" >"$root/logs/calibration-variation.log" 2>&1
status=$?
printf 'calibration-variation\t%s\n' "$status" >>"$root/status.tsv"
[[ "$status" -eq 0 ]] || exit "$status"
printf '%s\n' 'filtering' >"$root/current.txt"
hypothesis-helm-benchmark filtering --time-limit 9m --output "$root/outputs/filtering" >"$root/logs/filtering.log" 2>&1
status=$?
printf 'filtering\t%s\n' "$status" >>"$root/status.tsv"
[[ "$status" -eq 0 ]] || exit "$status"
printf '%s\n' 'complete' >"$root/current.txt"
date +%s >"$root/finished-epoch.txt"

#!/usr/bin/env bash
set -uo pipefail
root="${1:?refresh directory}"
export HELM_PLUGINS="$PWD/$root/helm/plugins"
export MPLCONFIGDIR="$PWD/$root/matplotlib"
export MPLBACKEND=Agg
mkdir -p "$MPLCONFIGDIR"
date +%s > "$root/started-epoch.txt"
hypothesis-helm-benchmark generate --output "$root/standard-chart" --input-complexity 100 --mean 0 --stddev 1 --output-bins 256 > "$root/logs/generate.log" 2>&1
printf '%s\n' 'performance' > "$root/current.txt"
hypothesis-helm-benchmark run --chart "$root/standard-chart" --step 50 --time-limit 9m --max-permutations 600000 --shards 1,2,3,4 --shard none --output "$root/outputs/performance" > "$root/logs/performance.log" 2>&1
status=$?
printf 'performance\t%s\n' "$status" >> "$root/status.tsv"
[[ "$status" -eq 0 ]] || exit "$status"
python "$root/prepare-discovery.py" "$root" > "$root/logs/prepare-discovery.log" 2>&1
printf '%s\n' 'discovery' > "$root/current.txt"
hypothesis-helm-benchmark discovery --chart "$root/outputs/discovery/chart" --max-strength 6 --time-limit 9m --output "$root/outputs/discovery" > "$root/logs/discovery.log" 2>&1
status=$?
printf 'discovery\t%s\n' "$status" >> "$root/status.tsv"
[[ "$status" -eq 0 ]] || exit "$status"
printf '%s\n' 'bug-density' > "$root/current.txt"
hypothesis-helm-benchmark discovery --input-complexity 8 --max-strength 6 --bug-percent 5 --seed 2026 --time-limit 9m --output "$root/outputs/bug-density" > "$root/logs/bug-density.log" 2>&1
status=$?
printf 'bug-density\t%s\n' "$status" >> "$root/status.tsv"
[[ "$status" -eq 0 ]] || exit "$status"
printf '%s\n' 'sparsity' > "$root/current.txt"
hypothesis-helm-benchmark sparsity --chart "$root/standard-chart" --count 32768 --retain 0.25 --levels 8 --time-limit 9m --output "$root/outputs/sparsity" > "$root/logs/sparsity.log" 2>&1
status=$?
printf 'sparsity\t%s\n' "$status" >> "$root/status.tsv"
[[ "$status" -eq 0 ]] || exit "$status"
printf '%s\n' 'topology-sparsity' > "$root/current.txt"
hypothesis-helm-benchmark sparsity --chart examples/topology-benchmark --count 1024 --levels 5 --time-limit 9m --output "$root/outputs/topology-sparsity" > "$root/logs/topology-sparsity.log" 2>&1
status=$?
printf 'topology-sparsity\t%s\n' "$status" >> "$root/status.tsv"
[[ "$status" -eq 0 ]] || exit "$status"
printf '%s\n' 'matrix' > "$root/current.txt"
hypothesis-helm-benchmark matrix --input-complexity 10 --trim-level 2 --seed 2026 --time-limit 9m --output "$root/outputs/matrix" > "$root/logs/matrix.log" 2>&1
status=$?
printf 'matrix\t%s\n' "$status" >> "$root/status.tsv"
[[ "$status" -eq 0 ]] || exit "$status"
printf '%s\n' 'pca' > "$root/current.txt"
hypothesis-helm-benchmark pca --input-complexity 10 --error-percent 5 --error-seed 1729 --seed 2026 --trim-level 2 --time-limit 9m --output "$root/outputs/pca" > "$root/logs/pca.log" 2>&1
status=$?
printf 'pca\t%s\n' "$status" >> "$root/status.tsv"
[[ "$status" -eq 0 ]] || exit "$status"
printf '%s\n' 'expansion' > "$root/current.txt"
hypothesis-helm-benchmark expansion --input-complexity 10 --error-percent 5 --error-seed 1729 --seed 2026 --trim-level 2 --time-limit 9m --output "$root/outputs/expansion" > "$root/logs/expansion.log" 2>&1
status=$?
printf 'expansion\t%s\n' "$status" >> "$root/status.tsv"
[[ "$status" -eq 0 ]] || exit "$status"
printf '%s\n' 'topology-depth' > "$root/current.txt"
hypothesis-helm-benchmark topology-depth --depths 0 1 2 3 4 5 --time-limit 9m --output "$root/outputs/topology-depth" > "$root/logs/topology-depth.log" 2>&1
status=$?
printf 'topology-depth\t%s\n' "$status" >> "$root/status.tsv"
[[ "$status" -eq 0 ]] || exit "$status"
printf '%s\n' 'nesting' > "$root/current.txt"
hypothesis-helm-benchmark nesting --permutations 8 --time-limit 9m --output "$root/outputs/nesting" > "$root/logs/nesting.log" 2>&1
status=$?
printf 'nesting\t%s\n' "$status" >> "$root/status.tsv"
[[ "$status" -eq 0 ]] || exit "$status"
printf '%s\n' 'complete' > "$root/current.txt"
date +%s > "$root/finished-epoch.txt"

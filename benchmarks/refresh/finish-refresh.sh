#!/usr/bin/env bash
set -euo pipefail
root="${1:?refresh directory}"
export MPLCONFIGDIR="$PWD/$root/matplotlib"
export MPLBACKEND=Agg
while [[ ! -f "$root/finished-epoch.txt" ]]; do
  sleep 45
done
printf '%s\n' verification >"$root/postprocess-current.txt"
python "$root/verify-measurements.py" "$root" >"$root/logs/verify-measurements.log" 2>&1
python "$root/discovery-tables.py" "$root"
python "$root/sparsity-tables.py" "$root"
python "$root/polish-sparsity.py" "$root" >"$root/logs/polish-sparsity.log" 2>&1
printf '%s\n' topologies >"$root/postprocess-current.txt"
bash "$root/run-topologies.sh" "$root" >"$root/logs/topologies.log" 2>&1
python "$root/plan-topology-retries.py" "$root" >"$root/logs/topology-retries.log" 2>&1
bash "$root/retry-topologies.sh" "$root" >>"$root/logs/topology-retries.log" 2>&1
python "$root/catalog-topologies.py" "$root" >"$root/logs/catalog-topologies.log" 2>&1
python "$root/verify-topologies.py" "$root" >"$root/logs/verify-topologies.log" 2>&1
python "$root/publish.py" "$root" >"$root/logs/publish.log" 2>&1
python "$root/update-documentation.py" "$root" --benchmarks-only >"$root/logs/update-benchmarks.log" 2>&1
date +%s >"$root/diagrams-finished-epoch.txt"
printf '%s\n' 'Load tests, diagrams, tables and benchmark summaries complete; starting Bitnami, then Prometheus.'
while IFS=$'\t' read -r name run_dir; do
  printf '%s\n' "$name" >"$root/postprocess-current.txt"
  printf 'Testing %s charts; logs: %s/jobs/\n' "$name" "$run_dir"
  # Chart failures are findings. The finalizer rejects missing or invalid worker results.
  bash "$run_dir/run.sh" "$run_dir" || true
  python "$run_dir/finalize.py" "$run_dir" "$name" >"$root/logs/$name-finalize.log" 2>&1
done <"$root/repositories.tsv"
printf '%s\n' complete >"$root/postprocess-current.txt"
date +%s >"$root/all-finished-epoch.txt"

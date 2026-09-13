#!/usr/bin/env bash
set -euo pipefail
root="${1:?refresh directory}"
export PATH="$PWD/.venv/bin:/tmp/hh-helm4/darwin-arm64:$PATH"
export MPLCONFIGDIR="$PWD/$root/matplotlib"
export MPLBACKEND=Agg
while [[ ! -f "$root/finished-epoch.txt" ]]; do
  sleep 45
done
printf '%s\n' verification > "$root/postprocess-current.txt"
.venv/bin/python "$root/verify-measurements.py" "$root" > "$root/logs/verify-measurements.log" 2>&1
.venv/bin/python "$root/discovery-tables.py" "$root"
.venv/bin/python "$root/sparsity-tables.py" "$root"
.venv/bin/python "$root/polish-sparsity.py" "$root" > "$root/logs/polish-sparsity.log" 2>&1
printf '%s\n' topologies > "$root/postprocess-current.txt"
bash "$root/run-topologies.sh" "$root" > "$root/logs/topologies.log" 2>&1
.venv/bin/python "$root/plan-topology-retries.py" "$root" > "$root/logs/topology-retries.log" 2>&1
bash "$root/retry-topologies.sh" "$root" >> "$root/logs/topology-retries.log" 2>&1
.venv/bin/python "$root/catalog-topologies.py" "$root" > "$root/logs/catalog-topologies.log" 2>&1
.venv/bin/python "$root/verify-topologies.py" "$root" > "$root/logs/verify-topologies.log" 2>&1
.venv/bin/python "$root/publish.py" "$root" > "$root/logs/publish.log" 2>&1
printf '%s\n' bitnami > "$root/postprocess-current.txt"
bash docs/reports/bitnami-runs/bitnami-charts_1789311940/run.sh docs/reports/bitnami-runs/bitnami-charts_1789311940 || true
.venv/bin/python docs/reports/bitnami-runs/bitnami-charts_1789311940/finalize.py docs/reports/bitnami-runs/bitnami-charts_1789311940 bitnami > "$root/logs/bitnami-finalize.log" 2>&1
printf '%s\n' prometheus > "$root/postprocess-current.txt"
bash docs/reports/prometheus-runs/prometheus-charts_1789311940/run.sh docs/reports/prometheus-runs/prometheus-charts_1789311940 || true
.venv/bin/python docs/reports/prometheus-runs/prometheus-charts_1789311940/finalize.py docs/reports/prometheus-runs/prometheus-charts_1789311940 prometheus > "$root/logs/prometheus-finalize.log" 2>&1
printf '%s\n' complete > "$root/postprocess-current.txt"
date +%s > "$root/all-finished-epoch.txt"

#!/usr/bin/env bash
set -uo pipefail
root="${1:?refresh directory}"
# Timing studies finish before dependency downloads or graph rendering begin.
while [[ ! -f "$root/finished-epoch.txt" ]]; do
  sleep 45
done
.venv/bin/python "$root/prepare-topologies.py" "$root"
date +%s > "$root/topology-started-epoch.txt"
parallel --will-cite --jobs 4 --timeout 540 --colsep '\t' --joblog "$root/topology-joblog.tsv" \
  bash "$root/chart-topology.sh" '{1}' '{2}' "$root" :::: "$root/topology-jobs.tsv"
printf '%s\n' "$?" > "$root/topology-exit-code.txt"
date +%s > "$root/topology-finished-epoch.txt"

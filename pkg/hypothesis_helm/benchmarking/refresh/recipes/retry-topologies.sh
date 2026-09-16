#!/usr/bin/env bash
set -uo pipefail
root="${1:?refresh directory}"
export MPLBACKEND=Agg
export MPLCONFIGDIR="$PWD/$root/matplotlib"
parallel --will-cite --term-seq TERM,10000,KILL,1000 --jobs 4 --timeout 540 --colsep '\t' --joblog "$root/topology-retry-plots-joblog.tsv" \
  hypothesis-helm-benchmark topology --graph '{1}' --output '{2}' --title '{3}' \
  :::: "$root/topology-retry-plots.tsv" >"$root/topology-retry-plots.log" 2>&1
printf '%s\n' "$?" >"$root/topology-retry-plots-exit-code.txt"
parallel --will-cite --term-seq TERM,10000,KILL,1000 --jobs 4 --timeout 540 --colsep '\t' --joblog "$root/topology-retry-charts-joblog.tsv" \
  bash "$root/chart-topology.sh" '{1}' '{2}' "$root" :::: "$root/topology-retry-charts.tsv"
printf '%s\n' "$?" >"$root/topology-retry-charts-exit-code.txt"
date +%s >"$root/topology-retry-finished-epoch.txt"

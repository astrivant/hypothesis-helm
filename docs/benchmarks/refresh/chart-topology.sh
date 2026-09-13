#!/usr/bin/env bash
set -uo pipefail
source_chart="${1:?chart directory}"
output="${2:?output directory}"
root="${3:?refresh directory}"
mkdir -p "$output"
if [[ ! -f "$source_chart/values.yaml" ]]; then
  printf '%s\n' '{"status":"missing-values","reason":"Source chart has no values.yaml; input graph export was not attempted."}' > "$output/status.json"
  exit 0
fi
scratch="$(mktemp -d "${TMPDIR:-/tmp}/hypothesis-helm-topology.XXXXXX")"
trap 'rm -rf -- "$scratch"' EXIT
mkdir -p "$scratch/chart"
cp -RL "$source_chart/." "$scratch/chart/"
export PATH="$PWD/.venv/bin:/tmp/hh-helm4/darwin-arm64:$PATH"
export HELM_PLUGINS="$PWD/$root/helm/plugins"
export HELM_REPOSITORY_CONFIG="$PWD/$root/helm/repositories.yaml"
export HELM_CACHE_HOME="$scratch/helm-cache"
export MPLCONFIGDIR="$PWD/$root/matplotlib-topology-${PARALLEL_JOBSLOT:-0}"
export MPLBACKEND=Agg
export XDG_CACHE_HOME="$scratch/cache"
helm dependency build "$scratch/chart" > "$output/dependencies.txt" 2>&1
printf '%s\n' "$?" > "$output/dependency-exit-code.txt"
hypothesis-helm audit "$scratch/chart" --export-topological-graph "$output/graph.json" > "$output/audit.json" 2> "$output/audit.err"
audit_status=$?
printf '%s\n' "$audit_status" > "$output/audit-exit-code.txt"
if [[ ! -f "$output/graph.json" ]]; then
  printf '%s\n' '{"status":"export-failed","reason":"See audit.err and dependencies.txt."}' > "$output/status.json"
  exit 1
fi
chart_title="${output#"$root/outputs/chart-topologies/"}"
hypothesis-helm-benchmark topology --graph "$output/graph.json" --output "$output" --title "$chart_title" > "$output/plot.json" 2> "$output/plot.err"
plot_status=$?
printf '%s\n' "$plot_status" > "$output/plot-exit-code.txt"
exit "$plot_status"

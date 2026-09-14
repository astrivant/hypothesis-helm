#!/usr/bin/env bash
# Exercise the benchmark chart, recipes, measurements, and plots in CI.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "${1:-}" == --help ]]; then
  echo 'Usage: bash benchmarks/smoke.sh [NEW_OUTPUT_DIRECTORY]'
  echo 'Checks all 22 recipes, measures three steps with 1s ceilings, and exports a topology graph.'
  exit 0
fi
if (($# > 1)); then
  echo 'Supply at most one new output directory.' >&2
  exit 2
fi
output="${1:-benchmarks/runs/smoke}"
export MPLBACKEND=Agg
mkdir -p "$(dirname "$output")"
mkdir "$output"
export MPLCONFIGDIR="$(cd "$output" && pwd)/matplotlib"
bash scripts/project-run.sh hypothesis-helm-benchmark stress --generate-only --output "$output/plan"
bash scripts/project-run.sh hypothesis-helm-benchmark stress --steps 3 --time-limit 1s --output "$output/stress"
bash scripts/project-run.sh hypothesis-helm-benchmark error-surface --input-complexity 3 \
  --axes depth redundancy clustering --depths 0 2 --redundant-inputs 0 2 --clustering 0 1 \
  --error-rates 0 25 100 --repeats 1 --time-limit 1s --output "$output/error-surface"
bash scripts/project-run.sh hypothesis-helm-benchmark generate \
  --parameters "$output/plan/cases/00-worst-case.yaml" --output "$output/chart"
bash scripts/project-run.sh hypothesis-helm audit "$output/chart" --export-topological-graph "$output/graph.json" >"$output/audit.json"
bash scripts/project-run.sh hypothesis-helm-benchmark topology --graph "$output/graph.json" \
  --output "$output/topology" --title 'Combined topology stress fixture'
bash scripts/project-run.sh hypothesis-helm test "$output/chart" --permutations 2 \
  --sample-random 70 --sample-min-cases 32 --dry-run --artifact-dir "$output/sampled-plan" >"$output/sampled-plan.json"
bash scripts/project-run.sh hypothesis-helm test "$output/chart" --permutations 2 \
  --filter-adaptive --dry-run --artifact-dir "$output/aggressive-plan" >"$output/aggressive-plan.json"
test -s "$output/stress/results.json"
test -s "$output/stress/results.csv"
test -s "$output/stress/topology-stress.png"
test -s "$output/stress/topology-stress.svg"
test -s "$output/topology/topology.png"
test -s "$output/topology/topology.svg"
test -s "$output/error-surface/results.json"
test -s "$output/error-surface/clustering-error-recall.png"

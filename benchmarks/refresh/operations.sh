#!/usr/bin/env bash
# Keep executable arguments visible; scheduling belongs to the Python operation graph.
set -euo pipefail
stage="${1:?operation name}"
root="${2:?refresh directory}"
export MPLBACKEND=Agg
if [[ -d "$root/frozen-source/pkg" ]]; then
  export PYTHONPATH="$PWD/$root/frozen-source/pkg"
  export HELM_PLUGINS="$PWD/$root/helm/plugins"
  export MPLCONFIGDIR="$PWD/$root/matplotlib-$stage"
fi
case "$stage" in
  checks)
    if [[ "$(helm version --short)" != v4.* ]]; then
      echo 'Put Helm 4 on PATH before running the refresh.' >&2
      exit 2
    fi
    bash scripts/check.sh
    ;;
  dependencies) git submodule update --init --recursive ;;
  initialize) python benchmarks/refresh/initialize.py "$root" ;;
  prepare-fixtures)
    date +%s >"$root/started-epoch.txt"
    python "$root/prepare-fixtures.py" "$root"
    ;;
  performance | discovery | bug-density | sparsity | structure-sparsity | structural-sparsity | matrix | pca | expansion | structure-depth | nesting | stress | sampling | calibration-variation | filtering | error-surface)
    bash "$root/studies.sh" "$stage" "$root"
    ;;
  measurements-finished) date +%s >"$root/finished-epoch.txt" ;;
  verify-measurements) python "$root/verify-measurements.py" "$root" ;;
  profile)
    hypothesis-helm-benchmark --parameters "$root/parameters/standard.yaml" --profile "$root/profiles" run \
      --suite scaling --scaling-counts 4 --replicas 1,2 --time-limit 30s --shard none --output "$root/profile-run"
    ;;
  flamegraphs) python "$root/publish-flamegraphs.py" "$root" ;;
  discovery-tables) python "$root/discovery-tables.py" "$root" ;;
  sparsity-tables) python "$root/sparsity-tables.py" "$root" ;;
  polish-sparsity) python "$root/polish-sparsity.py" "$root" ;;
  topologies) bash "$root/run-topologies.sh" "$root" ;;
  plan-topology-retries) python "$root/plan-topology-retries.py" "$root" ;;
  retry-topologies) bash "$root/retry-topologies.sh" "$root" ;;
  catalog-topologies) python "$root/catalog-topologies.py" "$root" ;;
  verify-topologies) python "$root/verify-topologies.py" "$root" ;;
  publish) python "$root/publish.py" "$root" ;;
  update-benchmarks) python "$root/update-documentation.py" "$root" --benchmarks-only ;;
  diagrams-finished) date +%s >"$root/diagrams-finished-epoch.txt" ;;
  bitnami | prometheus | bitnami-finalize | prometheus-finalize)
    repository="${stage%-finalize}"
    run_dir=""
    while IFS=$'\t' read -r name directory; do
      if [[ "$name" == "$repository" ]]; then run_dir="$directory"; fi
    done <"$root/repositories.tsv"
    [[ -n "$run_dir" ]] || {
      echo "Missing repository inventory: $repository" >&2
      exit 2
    }
    if [[ "$stage" == *-finalize ]]; then
      python "$run_dir/finalize.py" "$run_dir" "$repository"
    else
      bash "$run_dir/run.sh" "$run_dir"
    fi
    ;;
  all-finished) date +%s >"$root/all-finished-epoch.txt" ;;
  update-documentation) python "$root/update-documentation.py" "$root" ;;
  verify-publication) python "$root/verify-publication.py" "$root" ;;
  ruff)
    ruff check .
    ruff format --check .
    ;;
  publication-finished)
    date +%s >"$root/publication-finished-epoch.txt"
    ;;
  *)
    echo "Unknown refresh operation: $stage" >&2
    exit 2
    ;;
esac

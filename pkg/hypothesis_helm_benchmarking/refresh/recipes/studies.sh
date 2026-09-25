#!/usr/bin/env bash
# Literal study commands; the Python inventory supplies ordering and ownership.
set -uo pipefail
study="${1:?study name}"
root="${2:?refresh directory}"
case "$study" in
    performance)
        hypothesis-helm-benchmark --parameters "$root/parameters/standard.yaml" run --step 50 --time-limit 9m --max-permutations 600000 --shards 1,2,3,4 --shard none --output "$root/outputs/performance"
        ;;
    discovery)
        hypothesis-helm-benchmark --parameters "$root/parameters/discovery.yaml" discovery --max-strength 6 --time-limit 9m --output "$root/outputs/discovery"
        ;;
    bug-density)
        hypothesis-helm-benchmark discovery --input-complexity 8 --max-strength 6 --bug-percent 5 --seed 2026 --time-limit 9m --output "$root/outputs/bug-density"
        ;;
    sparsity)
        hypothesis-helm-benchmark --parameters "$root/parameters/standard.yaml" sparsity --count 32768 --retain 0.25 --levels 8 --time-limit 9m --output "$root/outputs/sparsity"
        ;;
    structure-sparsity)
        hypothesis-helm-benchmark --parameters "$root/parameters/topology.yaml" sparsity --count 1024 --levels 5 --time-limit 9m --output "$root/outputs/structure-sparsity"
        ;;
    structural-sparsity)
        hypothesis-helm-benchmark structural-sparsity --time-limit 9m --output "$root/outputs/structural-sparsity"
        ;;
    matrix)
        hypothesis-helm-benchmark matrix --input-complexity 10 --filter-level 2 --seed 2026 --time-limit 9m --output "$root/outputs/matrix"
        ;;
    pca)
        hypothesis-helm-benchmark pca --input-complexity 10 --error-percent 5 --error-seed 1729 --seed 2026 --filter-level 2 --time-limit 9m --output "$root/outputs/pca"
        ;;
    expansion)
        hypothesis-helm-benchmark expansion --input-complexity 10 --error-percent 5 --error-seed 1729 --seed 2026 --filter-level 2 --time-limit 9m --output "$root/outputs/expansion"
        ;;
    structure-depth)
        hypothesis-helm-benchmark structure-depth --depths 0 1 2 3 4 5 --time-limit 9m --output "$root/outputs/structure-depth"
        ;;
    nesting)
        hypothesis-helm-benchmark nesting --permutations 8 --time-limit 9m --output "$root/outputs/nesting"
        ;;
    stress)
        hypothesis-helm-benchmark stress --time-limit 9m --output "$root/outputs/stress"
        ;;
    sampling)
        hypothesis-helm-benchmark sampling --time-limit 9m --output "$root/outputs/sampling"
        ;;
    sensitivity)
        hypothesis-helm-benchmark sensitivity --inputs 48 --components 64 --time-limit 9m --output "$root/outputs/sensitivity"
        ;;
    sensitivity-ordering)
        hypothesis-helm-benchmark sensitivity-ordering --inputs 8 --permutations 3 --repeats 5 --time-limit 9m --output "$root/outputs/sensitivity-ordering"
        ;;
    calibration-variation)
        hypothesis-helm-benchmark calibration --inputs 6 --depths 1 3 5 --breadths 1 4 8 --output-depths 0 1 2 --time-limit 9m --output "$root/outputs/calibration-variation"
        ;;
    filtering)
        hypothesis-helm-benchmark filtering --time-limit 9m --output "$root/outputs/filtering"
        ;;
    error-surface)
        if [[ "${BENCHMARK_SYMBOLIC_FIT:-false}" == "true" ]]; then
            hypothesis-helm-benchmark error-surface --output-size 11x13 --symbolic-fit --time-limit 9m --output "$root/outputs/error-surface"
        else
            hypothesis-helm-benchmark error-surface --output-size 11x13 --time-limit 9m --output "$root/outputs/error-surface"
        fi
        ;;
    *)
        echo "Unknown refresh study: $study" >&2
        exit 2
        ;;
esac
status=$?
# Validate this handoff immediately, while the failed study is still the unit
# retried by resume. The final gate checks the complete inventory again.
if ((status == 0)); then
    python "$root/verify-measurements.py" "$root" --study "$study" || status=$?
fi
printf '%s\t%s\n' "$study" "$status" >>"$root/status.tsv"
exit "$status"

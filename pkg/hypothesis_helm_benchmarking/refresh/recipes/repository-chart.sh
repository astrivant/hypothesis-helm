#!/usr/bin/env bash
set -euo pipefail
chart="${1:?chart}"
sequence="${2:?job sequence}"
slot="${3:?worker slot}"
run_dir="${4:?report directory}"
workspace="$run_dir"
if [[ "$workspace" != /* ]]; then workspace="$PWD/$workspace"; fi
export HELM_CACHE_HOME="$workspace/helm/cache-$slot"
# A failed retry must not leave an earlier result looking like this attempt's evidence.
if [[ -f "$run_dir/jobs/$sequence.json" ]]; then
    previous="$(mktemp -d "$run_dir/jobs/$sequence.previous.XXXXXX")"
    mv "$run_dir/jobs/$sequence.json" "$previous/report.json"
fi
status=0
hypothesis-helm test "$chart" --chart-timeout 5m --filter --no-cache --jobs 6 --max-examples 10 --seed 0 --shard none \
    --disable-codes HH2006 --log-file /dev/stderr --traversal-strategy random --artifact-dir "$run_dir/runs" \
    2>&1 >"$run_dir/jobs/$sequence.out" | tee "$run_dir/jobs/$sequence.err" || status=$?
cat "$run_dir/jobs/$sequence.out"
# The terminal summary identifies the saved evidence; it is not itself a JSON report.
report=""
while IFS= read -r line; do
    case "$line" in
        'Results saved: '*) report="${line#Results saved: }" ;;
    esac
done <"$run_dir/jobs/$sequence.out"
if [[ -z "$report" || ! -f "$report" ]]; then
    echo "No saved report for chart $chart; see $run_dir/jobs/$sequence.out and .err" >&2
    exit 2
fi
# Publish a complete record even when chart findings give the test a nonzero status.
cp "$report" "$run_dir/jobs/$sequence.json.pending"
mv "$run_dir/jobs/$sequence.json.pending" "$run_dir/jobs/$sequence.json"
exit "$status"

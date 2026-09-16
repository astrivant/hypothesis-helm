#!/usr/bin/env bash
# Every VM receives the same chart and suite; --shard partitions properties by path.
set -euo pipefail
helm dependency build "$HH_CHART"
hypothesis-helm generate "$HH_CHART" --max-examples 10 --output "$RUN_ROOT/suite"
hypothesis-helm run "$RUN_ROOT/suite" \
  --shard "$SHARD_INDEX/$SHARD_TOTAL" --jobs "$JOBS" --seed "$SEED" \
  --run-id "$HH_RUN_ID" --rerun all --cache-dir "$CACHE_DIR/outcomes" \
  --artifact-dir "$RESULTS_DIR/artifacts"

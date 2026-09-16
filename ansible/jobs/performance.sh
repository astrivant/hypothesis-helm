#!/usr/bin/env bash
# Split the same global input IDs across VMs, then among local worker replicas.
set -euo pipefail
hypothesis-helm-benchmark run \
  --shard "$SHARD_INDEX/$SHARD_TOTAL" --replicas "$JOBS" --seed "$SEED" \
  --suite progressive --step 50 --max-permutations 50000 --time-limit 9m \
  --output "$RESULTS_DIR/performance"

#!/usr/bin/env bash
# The application verifies identities, inventory, duplicate ownership and missing shards.
set -euo pipefail
cat "$LOCAL_RESULTS"/shards/*/results/artifacts/shards/*/report.json |
  hypothesis-helm aggregate --shards "$SHARD_TOTAL" --run-id "$HH_RUN_ID" \
    --output-dir "$LOCAL_RESULTS/final"

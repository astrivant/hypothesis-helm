#!/usr/bin/env bash
# Execute the action's Helm command; optional flags remain visible at the call site.
set -euo pipefail

validate_api=
schema_offline=
disable_schema_caching=
disable_cache=
if [[ ${HH_KUBECONFORM:-true} == true && ${HH_KUBESEC:-false} != true ]]; then validate_api=1; fi
if [[ ${HH_SCHEMA_OFFLINE:-false} == true ]]; then schema_offline=1; fi
if [[ ${HH_DISABLE_SCHEMA_CACHING:-false} == true ]]; then disable_schema_caching=1; fi
if [[ ${HH_CACHE:-true} == false ]]; then disable_cache=1; fi

if [[ ${HH_KUBESEC:-false} == true ]]; then
  HH_RERUN=all
fi

exec helm hypothesis test "${HH_CHART:-.}" \
  --shard "$HH_RESOLVED_SHARD" \
  --jobs "${HH_JOBS:-auto}" \
  ${HH_RUN_ID:+--run-id "$HH_RUN_ID"} \
  --max-examples "${HH_MAX_EXAMPLES:-100}" \
  --seed "${HH_SEED:-0}" \
  --sample-random "${HH_SAMPLE_RANDOM:-100}" \
  --sample-min-cases "${HH_SAMPLE_MIN_CASES:-128}" \
  --timeout "${HH_TIMEOUT:-30}" \
  --artifact-dir "$HH_ARTIFACT_DIR" \
  --output json \
  --rerun "${HH_RERUN:-auto}" \
  ${HH_MATCH:+--match "$HH_MATCH"} \
  --cache-dir "${HH_CACHE_DIR:-$HH_RESULT_DIR/cache}" \
  ${disable_schema_caching:+--disable-schema-caching} \
  ${disable_cache:+--no-cache} \
  ${validate_api:+--kubeconform} \
  --schema-version "${HH_SCHEMA_VERSION:-latest}" \
  --schema-cache-dir "${HH_SCHEMA_CACHE_DIR:-.cache/hypothesis-helm/schemas}" \
  --kubeconform-binary "${HH_KUBECONFORM_BINARY:-kubeconform}" \
  ${schema_offline:+--schema-offline}

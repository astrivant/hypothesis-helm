#!/usr/bin/env bash
# Keep each executable invocation explicit; Python validates inputs, never builds shell source.
set -euo pipefail

# Repeatable groups are data, one group per line; the action prepares Bash 4.4+.
exhaustive_groups=()
mapfile -t groups <<<"${HH_EXHAUSTIVE_GROUP:-}"
for group in "${groups[@]}"; do
    if [[ -n "$group" ]]; then exhaustive_groups+=(--exhaustive-group "$group"); fi
done

case "$HH_COMMAND" in
    test)
        exec helm hypothesis test "$HH_SOURCE" \
            ${HH_REPORT:+--report "$HH_REPORT"} \
            ${HH_PCA_SAMPLES:+--pca-samples "$HH_PCA_SAMPLES"} \
            ${HH_PCA_TIMEOUT:+--pca-timeout "$HH_PCA_TIMEOUT"} \
            ${HH_MAX_MUTATIONS:+--max-mutations "$HH_MAX_MUTATIONS"} \
            ${HH_SENSITIVITY_TIMEOUT:+--sensitivity-timeout "$HH_SENSITIVITY_TIMEOUT"} \
            ${HH_VALUES:+--values "$HH_VALUES"} \
            ${HH_CHART_TIMEOUT:+--chart-timeout "$HH_CHART_TIMEOUT"} \
            ${HH_SCAN_TIMEOUT:+--scan-timeout "$HH_SCAN_TIMEOUT"} \
            ${HH_BUILD_DEPENDENCIES:+--build-dependencies} ${HH_NO_BUILD_DEPENDENCIES:+--no-build-dependencies} \
            ${HH_FAIL:+--fail "$HH_FAIL"} \
            ${HH_MAX_EXAMPLES:+--max-examples "$HH_MAX_EXAMPLES"} \
            ${HH_TIME_LIMIT:+--time-limit "$HH_TIME_LIMIT"} \
            ${HH_PATHS:+--paths} \
            ${HH_EXHAUSTIVE:+--exhaustive} \
            ${HH_WHOLE_CHART:+--whole-chart} \
            ${HH_PERMUTATIONS:+--permutations "$HH_PERMUTATIONS"} \
            ${HH_FILTER:+--filter} \
            ${HH_FILTER_RANDOM:+--filter-random "$HH_FILTER_RANDOM"} \
            ${HH_FILTER_TOPOLOGY:+--filter-topology "$HH_FILTER_TOPOLOGY"} \
            ${HH_EXPAND_FAILURES:+--expand-failures} \
            ${HH_PRUNE_EQUIVALENT:+--prune-equivalent} \
            ${HH_MATCH:+--match "$HH_MATCH"} \
            ${HH_COLLECT_ONLY:+--collect-only} \
            ${HH_MAX_CASES:+--max-cases "$HH_MAX_CASES"} \
            ${HH_MAX_CANDIDATES:+--max-candidates "$HH_MAX_CANDIDATES"} \
            ${HH_EXHAUSTIVE_THRESHOLD:+--exhaustive-threshold "$HH_EXHAUSTIVE_THRESHOLD"} \
            "${exhaustive_groups[@]}" \
            ${HH_NO_INFER_GROUPS:+--no-infer-groups} \
            ${HH_MAX_GROUP_CASES:+--max-group-cases "$HH_MAX_GROUP_CASES"} \
            ${HH_SEED:+--seed "$HH_SEED"} \
            ${HH_FILTER_ADAPTIVE:+--filter-adaptive} \
            ${HH_SAMPLING_CALIBRATION:+--sampling-calibration "$HH_SAMPLING_CALIBRATION"} \
            ${HH_SENSITIVITY_ORDER:+--sensitivity-order "$HH_SENSITIVITY_ORDER"} \
            ${HH_SAMPLE_RANDOM:+--sample-random "$HH_SAMPLE_RANDOM"} \
            ${HH_SAMPLE_MIN_CASES:+--sample-min-cases "$HH_SAMPLE_MIN_CASES"} \
            ${HH_TRAVERSAL_STRATEGY:+--traversal-strategy "$HH_TRAVERSAL_STRATEGY"} \
            ${HH_TIMEOUT:+--timeout "$HH_TIMEOUT"} \
            ${HH_HELM:+--helm "$HH_HELM"} \
            ${HH_RELEASE:+--release "$HH_RELEASE"} \
            ${HH_NAMESPACE:+--namespace "$HH_NAMESPACE"} \
            ${HH_KUBE_VERSION:+--kube-version "$HH_KUBE_VERSION"} \
            ${HH_ALLOW_EMPTY:+--allow-empty} \
            ${HH_ARTIFACT_DIR:+--artifact-dir "$HH_ARTIFACT_DIR"} \
            ${HH_STRICT:+--strict} ${HH_NO_STRICT:+--no-strict} \
            ${HH_VALIDATE_SCHEMAS:+--validate-schemas} \
            ${HH_SCHEMA_VERSION:+--schema-version "$HH_SCHEMA_VERSION"} \
            ${HH_SCHEMA_CACHE_DIR:+--schema-cache-dir "$HH_SCHEMA_CACHE_DIR"} \
            ${HH_SCHEMA_OFFLINE:+--schema-offline} \
            ${HH_BASE_REF:+--base-ref "$HH_BASE_REF"} \
            ${HH_DRY_RUN:+--dry-run} \
            ${HH_CACHE_DIR:+--cache-dir "$HH_CACHE_DIR"} \
            ${HH_DISABLE_SCHEMA_CACHING:+--disable-schema-caching} \
            ${HH_PROGRESS:+--progress} \
            ${HH_RUN_ID:+--run-id "$HH_RUN_ID"} \
            ${HH_NO_CACHE:+--no-cache} \
            ${HH_RERUN:+--rerun "$HH_RERUN"} \
            ${HH_SHARD:+--shard "$HH_SHARD"} \
            ${HH_JOBS:+--jobs "$HH_JOBS"} \
            ${HH_OUTPUT_FORMAT:+--output-format "$HH_OUTPUT_FORMAT"} \
            ${HH_EXPORT_SUPPRESSIONS:+--export-suppressions} \
            ${HH_EXPORT_TOPOLOGICAL_GRAPH:+--export-topological-graph "$HH_EXPORT_TOPOLOGICAL_GRAPH"} \
            ${HH_MINIMAL_VALUES_TIMEOUT:+--minimal-values-timeout "$HH_MINIMAL_VALUES_TIMEOUT"} \
            ${HH_LOG_COLOR:+--log-color "$HH_LOG_COLOR"} \
            ${HH_LOG_FILE:+--log-file "$HH_LOG_FILE"} \
            ${HH_CONFIG:+--config "$HH_CONFIG"} \
            ${HH_CHARACTER_SETS:+--character-sets "$HH_CHARACTER_SETS"} \
            ${HH_RENDERER_POLICY:+--renderer-policy "$HH_RENDERER_POLICY"} \
            ${HH_YAML_PARSER:+--yaml-parser "$HH_YAML_PARSER"} \
            ${HH_DISABLE_CODES:+--disable-codes "$HH_DISABLE_CODES"}
        ;;
    scan)
        exec helm hypothesis scan "$HH_SOURCE" \
            ${HH_HELM_REPOSITORY:+--helm-repository} \
            ${HH_CHART_VERSION:+--chart-version "$HH_CHART_VERSION"} \
            ${HH_CLONE_TIMEOUT:+--clone-timeout "$HH_CLONE_TIMEOUT"} \
            ${HH_REPORT:+--report "$HH_REPORT"} \
            ${HH_ARTIFACT_DIR:+--artifact-dir "$HH_ARTIFACT_DIR"} \
            ${HH_HELM:+--helm "$HH_HELM"} \
            ${HH_VALUES:+--values "$HH_VALUES"} \
            ${HH_TIMEOUT:+--timeout "$HH_TIMEOUT"} \
            ${HH_CHART_TIMEOUT:+--chart-timeout "$HH_CHART_TIMEOUT"} \
            ${HH_SCAN_TIMEOUT:+--scan-timeout "$HH_SCAN_TIMEOUT"} \
            ${HH_MAX_EXAMPLES:+--max-examples "$HH_MAX_EXAMPLES"} \
            ${HH_CACHE_DIR:+--cache-dir "$HH_CACHE_DIR"} \
            ${HH_NO_CACHE:+--no-cache} \
            ${HH_JOBS:+--jobs "$HH_JOBS"} \
            ${HH_PERMUTATIONS:+--permutations "$HH_PERMUTATIONS"} \
            ${HH_FILTER:+--filter} \
            ${HH_FAIL:+--fail "$HH_FAIL"} \
            ${HH_SEED:+--seed "$HH_SEED"} \
            ${HH_BUILD_DEPENDENCIES:+--build-dependencies} ${HH_NO_BUILD_DEPENDENCIES:+--no-build-dependencies} \
            ${HH_PCA_SAMPLES:+--pca-samples "$HH_PCA_SAMPLES"} \
            ${HH_PCA_TIMEOUT:+--pca-timeout "$HH_PCA_TIMEOUT"} \
            ${HH_MAX_MUTATIONS:+--max-mutations "$HH_MAX_MUTATIONS"} \
            ${HH_SENSITIVITY_TIMEOUT:+--sensitivity-timeout "$HH_SENSITIVITY_TIMEOUT"} \
            ${HH_FILTER_ADAPTIVE:+--filter-adaptive} \
            ${HH_SAMPLING_CALIBRATION:+--sampling-calibration "$HH_SAMPLING_CALIBRATION"} \
            ${HH_SENSITIVITY_ORDER:+--sensitivity-order "$HH_SENSITIVITY_ORDER"} \
            ${HH_SAMPLE_RANDOM:+--sample-random "$HH_SAMPLE_RANDOM"} \
            ${HH_SAMPLE_MIN_CASES:+--sample-min-cases "$HH_SAMPLE_MIN_CASES"} \
            ${HH_TRAVERSAL_STRATEGY:+--traversal-strategy "$HH_TRAVERSAL_STRATEGY"} \
            ${HH_STRICT:+--strict} ${HH_NO_STRICT:+--no-strict} \
            ${HH_VALIDATE_SCHEMAS:+--validate-schemas} \
            ${HH_SCHEMA_VERSION:+--schema-version "$HH_SCHEMA_VERSION"} \
            ${HH_SCHEMA_CACHE_DIR:+--schema-cache-dir "$HH_SCHEMA_CACHE_DIR"} \
            ${HH_SCHEMA_OFFLINE:+--schema-offline} \
            ${HH_BASE_REF:+--base-ref "$HH_BASE_REF"} \
            ${HH_OUTPUT_FORMAT:+--output-format "$HH_OUTPUT_FORMAT"} \
            ${HH_EXPORT_SUPPRESSIONS:+--export-suppressions} \
            ${HH_EXPORT_TOPOLOGICAL_GRAPH:+--export-topological-graph "$HH_EXPORT_TOPOLOGICAL_GRAPH"} \
            ${HH_MINIMAL_VALUES_TIMEOUT:+--minimal-values-timeout "$HH_MINIMAL_VALUES_TIMEOUT"} \
            ${HH_LOG_COLOR:+--log-color "$HH_LOG_COLOR"} \
            ${HH_LOG_FILE:+--log-file "$HH_LOG_FILE"} \
            ${HH_CONFIG:+--config "$HH_CONFIG"} \
            ${HH_CHARACTER_SETS:+--character-sets "$HH_CHARACTER_SETS"} \
            ${HH_RENDERER_POLICY:+--renderer-policy "$HH_RENDERER_POLICY"} \
            ${HH_YAML_PARSER:+--yaml-parser "$HH_YAML_PARSER"} \
            ${HH_DISABLE_CODES:+--disable-codes "$HH_DISABLE_CODES"} \
            ${HH_REMOTE_MINIMAL_VALUES:+--export-minimal-values "$HH_REMOTE_MINIMAL_VALUES"}
        ;;
    audit)
        exec helm hypothesis audit "$HH_SOURCE" \
            ${HH_FAIL:+--fail "$HH_FAIL"} \
            ${HH_ARTIFACT_DIR:+--artifact-dir "$HH_ARTIFACT_DIR"} \
            ${HH_EXPORT_SUPPRESSIONS:+--export-suppressions} \
            ${HH_EXPORT_TOPOLOGICAL_GRAPH:+--export-topological-graph "$HH_EXPORT_TOPOLOGICAL_GRAPH"} \
            ${HH_MINIMAL_VALUES_TIMEOUT:+--minimal-values-timeout "$HH_MINIMAL_VALUES_TIMEOUT"} \
            ${HH_LOG_COLOR:+--log-color "$HH_LOG_COLOR"} \
            ${HH_LOG_FILE:+--log-file "$HH_LOG_FILE"} \
            ${HH_CONFIG:+--config "$HH_CONFIG"} \
            ${HH_CHARACTER_SETS:+--character-sets "$HH_CHARACTER_SETS"} \
            ${HH_RENDERER_POLICY:+--renderer-policy "$HH_RENDERER_POLICY"} \
            ${HH_YAML_PARSER:+--yaml-parser "$HH_YAML_PARSER"} \
            ${HH_DISABLE_CODES:+--disable-codes "$HH_DISABLE_CODES"}
        ;;
    generate)
        exec helm hypothesis generate "$HH_SOURCE" \
            ${HH_SUITE_OUTPUT:+--output "$HH_SUITE_OUTPUT"} \
            ${HH_MAX_EXAMPLES:+--max-examples "$HH_MAX_EXAMPLES"} \
            ${HH_STRICT:+--strict} ${HH_NO_STRICT:+--no-strict} \
            ${HH_FAIL:+--fail "$HH_FAIL"} \
            ${HH_EXPORT_TOPOLOGICAL_GRAPH:+--export-topological-graph "$HH_EXPORT_TOPOLOGICAL_GRAPH"} \
            ${HH_MINIMAL_VALUES_TIMEOUT:+--minimal-values-timeout "$HH_MINIMAL_VALUES_TIMEOUT"} \
            ${HH_LOG_COLOR:+--log-color "$HH_LOG_COLOR"} \
            ${HH_LOG_FILE:+--log-file "$HH_LOG_FILE"} \
            ${HH_CONFIG:+--config "$HH_CONFIG"} \
            ${HH_CHARACTER_SETS:+--character-sets "$HH_CHARACTER_SETS"} \
            ${HH_RENDERER_POLICY:+--renderer-policy "$HH_RENDERER_POLICY"} \
            ${HH_YAML_PARSER:+--yaml-parser "$HH_YAML_PARSER"} \
            ${HH_DISABLE_CODES:+--disable-codes "$HH_DISABLE_CODES"}
        ;;
    run)
        exec helm hypothesis run "$HH_SOURCE" \
            ${HH_SEED:+--seed "$HH_SEED"} \
            ${HH_MATCH:+--match "$HH_MATCH"} \
            ${HH_COLLECT_ONLY:+--collect-only} \
            ${HH_ARTIFACT_DIR:+--artifact-dir "$HH_ARTIFACT_DIR"} \
            ${HH_SAMPLE_RANDOM:+--sample-random "$HH_SAMPLE_RANDOM"} \
            ${HH_SAMPLE_MIN_CASES:+--sample-min-cases "$HH_SAMPLE_MIN_CASES"} \
            ${HH_TRAVERSAL_STRATEGY:+--traversal-strategy "$HH_TRAVERSAL_STRATEGY"} \
            ${HH_STRICT:+--strict} ${HH_NO_STRICT:+--no-strict} \
            ${HH_VALIDATE_SCHEMAS:+--validate-schemas} \
            ${HH_SCHEMA_VERSION:+--schema-version "$HH_SCHEMA_VERSION"} \
            ${HH_SCHEMA_CACHE_DIR:+--schema-cache-dir "$HH_SCHEMA_CACHE_DIR"} \
            ${HH_SCHEMA_OFFLINE:+--schema-offline} \
            ${HH_DRY_RUN:+--dry-run} \
            ${HH_CACHE_DIR:+--cache-dir "$HH_CACHE_DIR"} \
            ${HH_DISABLE_SCHEMA_CACHING:+--disable-schema-caching} \
            ${HH_PROGRESS:+--progress} \
            ${HH_RUN_ID:+--run-id "$HH_RUN_ID"} \
            ${HH_NO_CACHE:+--no-cache} \
            ${HH_RERUN:+--rerun "$HH_RERUN"} \
            ${HH_SHARD:+--shard "$HH_SHARD"} \
            ${HH_JOBS:+--jobs "$HH_JOBS"} \
            ${HH_OUTPUT_FORMAT:+--output-format "$HH_OUTPUT_FORMAT"} \
            ${HH_EXPORT_SUPPRESSIONS:+--export-suppressions} \
            ${HH_FAIL:+--fail "$HH_FAIL"} \
            ${HH_LOG_COLOR:+--log-color "$HH_LOG_COLOR"} \
            ${HH_LOG_FILE:+--log-file "$HH_LOG_FILE"} \
            ${HH_CONFIG:+--config "$HH_CONFIG"} \
            ${HH_CHARACTER_SETS:+--character-sets "$HH_CHARACTER_SETS"} \
            ${HH_RENDERER_POLICY:+--renderer-policy "$HH_RENDERER_POLICY"} \
            ${HH_YAML_PARSER:+--yaml-parser "$HH_YAML_PARSER"} \
            ${HH_DISABLE_CODES:+--disable-codes "$HH_DISABLE_CODES"}
        ;;
    *)
        echo "Unsupported action command: $HH_COMMAND" >&2
        exit 2
        ;;
esac

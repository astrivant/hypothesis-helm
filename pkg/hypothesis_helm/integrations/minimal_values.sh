#!/usr/bin/env bash
# Export beside charts; optionally commit exported YAML and proof files in one CI job.
set -euo pipefail
case "${HH_RESOLVED_SHARD:-none}" in
  none | 1/*) ;;
  *)
    echo 'Minimal values export is handled by shard 1.'
    exit 0
    ;;
esac
files_list="$(mktemp "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/helm-minimal-files.XXXXXX")"
trap 'rm -f "$files_list"' EXIT
if [[ "${HH_KUBECONFORM:-false}" == true || "${HH_KUBESEC:-false}" == true ]]; then
  helm hypothesis export-minimal-values "$HH_CHART" \
    --filename "${HH_MINIMAL_VALUES_FILENAME:-values-minimal.yaml}" \
    --minimal-values-timeout "${HH_MINIMAL_VALUES_TIMEOUT:-30s}" \
    --files-list "$files_list" --kubeconform \
    --schema-version "$HH_SCHEMA_VERSION" --schema-cache-dir "$HH_SCHEMA_CACHE_DIR" \
    --kubeconform-binary "$HH_KUBECONFORM_BINARY" --schema-offline
else
  helm hypothesis export-minimal-values "$HH_CHART" \
    --filename "${HH_MINIMAL_VALUES_FILENAME:-values-minimal.yaml}" \
    --minimal-values-timeout "${HH_MINIMAL_VALUES_TIMEOUT:-30s}" \
    --files-list "$files_list"
fi
if [[ "${HH_COMMIT_MINIMAL_VALUES:-false}" != true || ! -s "$files_list" ]]; then
  exit 0
fi
if [[ -z "${HH_COMMIT_BRANCH:-}" ]]; then
  echo 'Commit-back requires a branch checkout; pull-request merge refs are unsupported.' >&2
  exit 2
fi
# Reject pre-existing staged changes to these files instead of mixing ownership.
if ! git diff --cached --quiet; then
  echo 'Commit-back requires a clean Git index.' >&2
  exit 2
fi
git --literal-pathspecs add --pathspec-from-file="$files_list" --pathspec-file-nul
if git diff --cached --quiet; then
  exit 0
fi
git --literal-pathspecs -c user.name='github-actions[bot]' \
  -c user.email='41898282+github-actions[bot]@users.noreply.github.com' \
  commit --only --pathspec-from-file="$files_list" --pathspec-file-nul \
  -m 'Update minimal Helm values and verification proof' \
  -m 'Hypothesis-Helm-Minimal-Values: true'
git push origin "HEAD:$HH_COMMIT_BRANCH"

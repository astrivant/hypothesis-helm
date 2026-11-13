#!/usr/bin/env bash
# Check retained work graph inputs and exported artifacts against their reviewed hashes.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ${1:-} == --help ]]; then
    printf '%s\n' 'Usage: bash scripts/check-work-graphs.sh [--debug]' \
        'Check every retained work graph that has a work.sha256 receipt.'
    exit 0
fi
if [[ $# -gt 1 || ($# -eq 1 && $1 != --debug) ]]; then
    printf '%s\n' 'ERROR: Expected at most --debug' >&2
    exit 2
fi

shopt -s nullglob
receipts=(.github/review-evidence/*/work.sha256)
printf 'INFO: Checking %s work graph receipts\n' "${#receipts[@]}" >&2
for receipt in "${receipts[@]}"; do
    directory=${receipt%/work.sha256}
    if [[ ${1:-} == --debug ]]; then
        printf 'DEBUG: Checking %s\n' "$directory" >&2
    fi
    # Only the three declared files can contribute; receipt lines cannot name other paths.
    if ! shasum -a 256 "$directory/work.json" "$directory/work.md" "$directory/work.mmd" | cmp -s "$receipt" -; then
        printf 'ERROR: Work graph receipt is stale or incomplete: %s\n' "$directory" >&2
        exit 1
    fi
done

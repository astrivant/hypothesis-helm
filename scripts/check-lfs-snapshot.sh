#!/usr/bin/env bash
# Keep refreshed raw data local while retaining the published LFS snapshot.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
snapshot_check=$(mktemp -d)
trap 'rm -rf "$snapshot_check"' EXIT
git diff --cached --name-only --no-renames --diff-filter=ACMRTUXB -z >"$snapshot_check/paths"
git check-attr --cached -z --stdin filter <"$snapshot_check/paths" >"$snapshot_check/attributes"
blocked=0
mapfile -d '' -t attributes <"$snapshot_check/attributes"
for ((index = 0; index < ${#attributes[@]}; index += 3)); do
    path="${attributes[index]}"
    attribute="${attributes[index + 1]}"
    value="${attributes[index + 2]}"
    if [[ "$attribute" == filter && "$value" == lfs ]]; then
        blocked=$((blocked + 1))
        if ((blocked <= 10)); then
            printf 'Paused LFS update: %s\n' "$path" >&2
        fi
    fi
done
if ((blocked)); then
    printf '\nRaw-data publication is paused: %s staged LFS paths.\n' "$blocked" >&2
    printf '%s\n' \
        'Unstage these paths with git restore --staged -- <paths>; local files are preserved.' \
        'To intentionally publish a new snapshot: SKIP=lfs-snapshot git commit' >&2
    exit 1
fi

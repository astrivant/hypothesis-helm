#!/usr/bin/env bash
# A successful tag pipeline must end in verified public GitHub and PyPI artifacts.
set -euo pipefail
: "${GITHUB_REPOSITORY:?}" "${RELEASE_TAG:?}" "${SOURCE_SHA:?}" "${COSIGN_PUBLIC_KEY_SHA256:?}"
directory="$(mktemp -d)"
##
# Remove downloaded public files while retaining the verifier's exit status.
# -> ret::exit_code
cleanup() {
    status="$?"
    trap - EXIT
    rm -rf -- "$directory" || true
    exit "$status"
}
trap cleanup EXIT
test "$(gh release view "$RELEASE_TAG" --repo "$GITHUB_REPOSITORY" --json isDraft --jq .isDraft)" = false
gh release download "$RELEASE_TAG" --repo "$GITHUB_REPOSITORY" --dir "$directory"
python scripts/release/attest.py verify --directory "$directory" --tag "$RELEASE_TAG" --source "$SOURCE_SHA" --fingerprint "$COSIGN_PUBLIC_KEY_SHA256"
python scripts/release/verify-registry.py "$directory" "$RELEASE_TAG"

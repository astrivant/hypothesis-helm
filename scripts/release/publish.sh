#!/usr/bin/env bash
# Publish the existing verified build; never replace a public release or rebuild a tag.
set -euo pipefail
set +x
umask 077
: "${GITHUB_REPOSITORY:?}" "${RELEASE_TAG:?}" "${SOURCE_SHA:?}" "${COSIGN_PUBLIC_KEY_SHA256:?}"
: "${COSIGN_PRIVATE_KEY:?}" "${COSIGN_PASSWORD:?}"
distribution_directory="${DISTRIBUTION_DIRECTORY:-dist}"
directory="$(mktemp -d)"
##
# Remove this operation's temporary files while preserving the original exit status.
# -> ret::exit_code
cleanup() {
    status="$?"
    trap - EXIT
    rm -rf -- "$directory" || true
    exit "$status"
}
trap cleanup EXIT

# The source must be the existing tag on main, including during manual recovery.
test "$(git rev-parse "$RELEASE_TAG^{commit}")" = "$SOURCE_SHA"
git merge-base --is-ancestor "$SOURCE_SHA" origin/main
# Pagination distinguishes an absent release from an authentication or network failure.
release_state="$(gh api --paginate "repos/$GITHUB_REPOSITORY/releases" --jq '.[] | {tag_name, draft}' | jq -s -r --arg tag "$RELEASE_TAG" '.[] | select(.tag_name == $tag) | .draft')"
if [ "$release_state" = false ]; then
    bash scripts/release/verify-published.sh
    exit 0
fi
# PyPI is an independent output. Verify its downloaded bytes before publishing GitHub.
python scripts/release/verify-registry.py "$distribution_directory" "$RELEASE_TAG"
cp "$distribution_directory/"*.whl "$distribution_directory/"*.tar.gz "$directory/"
python scripts/release/attest.py prepare --directory "$directory" --tag "$RELEASE_TAG" --source "$SOURCE_SHA" --fingerprint "$COSIGN_PUBLIC_KEY_SHA256"
gh api "repos/$GITHUB_REPOSITORY/releases/generate-notes" -f tag_name="$RELEASE_TAG" -f target_commitish="$SOURCE_SHA" --jq .body >"$directory/notes.md"
tool_revision="$(git rev-parse HEAD)"
cat >>"$directory/notes.md" <<NOTES

## Verified artifacts

Wheel and source archive are the tested build published to [PyPI](https://pypi.org/project/hypothesis-helm/${RELEASE_TAG#v}/).
Source: [$SOURCE_SHA](https://github.com/$GITHUB_REPOSITORY/commit/$SOURCE_SHA).
Each distribution and the checksum manifest have Cosign signatures. Obtain the trusted public-key fingerprint independently before verification.
See the [verification guide](https://github.com/$GITHUB_REPOSITORY/blob/$tool_revision/docs/releases.md) for verification and recovery commands.
NOTES
release_flags=(--draft)
if [[ "${RELEASE_TAG#v}" =~ [A-Za-z] ]]; then
    release_flags+=(--prerelease)
fi
if [ -z "$release_state" ]; then
    gh release create "$RELEASE_TAG" --repo "$GITHUB_REPOSITORY" --verify-tag --title "Hypothesis Helm $RELEASE_TAG" --notes-file "$directory/notes.md" "${release_flags[@]}"
else
    # Existing draft payloads must match. A failed upload may leave only some assets.
    mkdir "$directory/previous"
    asset_count="$(gh release view "$RELEASE_TAG" --repo "$GITHUB_REPOSITORY" --json assets --jq '.assets | length')"
    if [ "$asset_count" -gt 0 ]; then
        gh release download "$RELEASE_TAG" --repo "$GITHUB_REPOSITORY" --dir "$directory/previous"
    fi
    for file in "$directory/previous/"*.whl "$directory/previous/"*.tar.gz; do
        [ -e "$file" ] || continue
        cmp "$file" "$directory/$(basename "$file")"
    done
    rm -rf -- "$directory/previous"
fi
rm -- "$directory/notes.md"
python scripts/release/upload.py "$directory"
mkdir "$directory/download"
gh release download "$RELEASE_TAG" --repo "$GITHUB_REPOSITORY" --dir "$directory/download"
python scripts/release/attest.py verify --directory "$directory/download" --tag "$RELEASE_TAG" --source "$SOURCE_SHA" --fingerprint "$COSIGN_PUBLIC_KEY_SHA256"
gh release edit "$RELEASE_TAG" --repo "$GITHUB_REPOSITORY" --draft=false

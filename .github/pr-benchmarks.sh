#!/usr/bin/env bash
# Validate a manual PR benchmark and publish only its final graphs and summaries.
set -euo pipefail

##
# Verify that the manual run still describes this open, same-repository PR.
# -> ret::void
validate_pr() {
    local metadata

    [[ "$PR_NUMBER" =~ ^[1-9][0-9]*$ ]] || {
        echo 'A positive pull-request number is required' >&2
        exit 1
    }
    metadata=$(gh api "repos/$GITHUB_REPOSITORY/pulls/$PR_NUMBER")
    jq -e --arg repository "$GITHUB_REPOSITORY" --arg sha "$GITHUB_SHA" \
        --arg ref "$GITHUB_REF" --arg base "$DEFAULT_BRANCH" \
        --arg base_sha "${EXPECTED_BASE_SHA:-}" '
        .state == "open" and .draft == false and
        .head.repo.full_name == $repository and .base.repo.full_name == $repository and
        .base.ref == $base and .head.ref != $base and
        .head.sha == $sha and ("refs/heads/" + .head.ref) == $ref and
        ($base_sha == "" or .base.sha == $base_sha)
        ' <<<"$metadata" >/dev/null || {
        echo 'Run on the current head branch of an open, ready PR in this repository; the head and base must not change during benchmarking.' >&2
        exit 1
    }
    PR_BRANCH=$(jq -r '.head.ref' <<<"$metadata")
    PR_BASE_SHA=$(jq -r '.base.sha' <<<"$metadata")
}

##
# Commit final publications without uploading raw data or overwriting newer work.
# -> ret::void
commit_graphs() {
    local paths path attribute changed
    local -a publication_paths

    validate_pr
    [[ "$(git rev-parse HEAD)" == "$GITHUB_SHA" ]]
    git diff --cached --quiet || {
        echo 'Unexpected staged changes before graph publication' >&2
        exit 1
    }
    git diff --quiet -- pkg/ scripts/ .github/ pyproject.toml poetry.lock \
        ':(exclude)pkg/hypothesis_helm_benchmarking/assets/fixture/parameters/' || {
        echo 'Refresh changed maintained code or catalogs; commit those changes before benchmarking the PR.' >&2
        exit 1
    }
    paths=$(mktemp)
    # Explicit output roots and extensions keep code, caches and LFS datasets out of the commit.
    mapfile -d '' -t publication_paths < <(git ls-files -z --modified --deleted --others --exclude-standard -- README.md studies/ docs/benchmarking/)
    for path in "${publication_paths[@]}"; do
        case "$path" in
            *.md | *.png | *.svg | *.pdf)
                attribute=$(git check-attr filter -- "$path")
                if [[ "$attribute" != *': filter: lfs' ]]; then
                    printf '%s\0' "$path" >>"$paths"
                fi
                ;;
        esac
    done
    if [[ -s "$paths" ]]; then
        git add -A --pathspec-from-file="$paths" --pathspec-file-nul
    fi
    rm -f "$paths"
    changed=false
    if ! git diff --cached --quiet; then
        git config user.name 'github-actions[bot]'
        git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
        git commit -m "Update benchmark graphs for PR #$PR_NUMBER"
        # Recheck immediately before pushing; a concurrent branch advance also rejects this ordinary fast-forward push.
        validate_pr
        git push origin "HEAD:refs/heads/$PR_BRANCH"
        changed=true
    fi
    printf 'sha=%s\n' "$(git rev-parse HEAD)" >>"$GITHUB_OUTPUT"
    if [[ "$changed" == true ]]; then
        # Token-authenticated pushes do not reliably start normal CI. Dispatch checks on the new graph commit explicitly.
        gh workflow run ci.yml --repo "$GITHUB_REPOSITORY" --ref "$PR_BRANCH"
    fi
}

case "${1:-}" in
    validate)
        validate_pr
        printf 'sha=%s\nbranch=%s\nbase_sha=%s\n' "$GITHUB_SHA" "$PR_BRANCH" "$PR_BASE_SHA" >>"$GITHUB_OUTPUT"
        gh api --method POST "repos/$GITHUB_REPOSITORY/statuses/$GITHUB_SHA" \
            -f state=pending -f context='PR benchmark results' \
            -f description='Manually requested benchmarks are running' \
            -f target_url="$GITHUB_SERVER_URL/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID" >/dev/null
        ;;
    commit) commit_graphs ;;
    *)
        echo 'Usage: pr-benchmarks.sh validate|commit' >&2
        exit 2
        ;;
esac

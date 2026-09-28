#!/usr/bin/env bash
# Validate a manual benchmark on the default branch or a PR and publish its final graphs and summaries.
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
    BENCHMARK_BRANCH=$(jq -r '.head.ref' <<<"$metadata")
    BENCHMARK_BASE_SHA=$(jq -r '.base.sha' <<<"$metadata")
}

##
# Allow the unchanged default branch without a PR, or validate the requested PR.
# -> ret::void
validate_request() {
    local remote_head

    if [[ -n "$PR_NUMBER" ]]; then
        validate_pr
        return
    fi
    [[ "$GITHUB_REF" == "refs/heads/$DEFAULT_BRANCH" ]] || {
        echo 'Without a pull-request number, run benchmarks on the default branch.' >&2
        exit 1
    }
    remote_head=$(git ls-remote --exit-code origin "$GITHUB_REF")
    [[ "${remote_head%%$'\t'*}" == "$GITHUB_SHA" ]] || {
        echo 'The default branch has changed; restart benchmarks on its current head.' >&2
        exit 1
    }
    BENCHMARK_BRANCH=$DEFAULT_BRANCH
    BENCHMARK_BASE_SHA=''
}

##
# Commit final publications without uploading raw data or overwriting newer work.
# -> ret::void
commit_graphs() {
    local paths path attribute changed message
    local -a publication_paths

    validate_request
    [[ "$(git rev-parse HEAD)" == "$GITHUB_SHA" ]]
    git diff --cached --quiet || {
        echo 'Unexpected staged changes before graph publication' >&2
        exit 1
    }
    git diff --quiet -- pkg/ scripts/ .github/ pyproject.toml poetry.lock \
        ':(exclude)pkg/hypothesis_helm_benchmarking/assets/fixture/parameters/' || {
        echo 'Refresh changed maintained code or catalogs; commit those changes before benchmarking.' >&2
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
        message="Update benchmark graphs on $BENCHMARK_BRANCH"
        if [[ -n "$PR_NUMBER" ]]; then
            message="Update benchmark graphs for PR #$PR_NUMBER"
        fi
        git commit -m "$message"
        # Recheck immediately before pushing; a concurrent branch advance also rejects this ordinary fast-forward push.
        validate_request
        git push origin "HEAD:refs/heads/$BENCHMARK_BRANCH"
        changed=true
    fi
    printf 'sha=%s\n' "$(git rev-parse HEAD)" >>"$GITHUB_OUTPUT"
    if [[ "$changed" == true && -n "$PR_NUMBER" ]]; then
        # PR pushes use GITHUB_TOKEN, so dispatch CI explicitly. The main publication token triggers push CI itself.
        gh workflow run ci.yml --repo "$GITHUB_REPOSITORY" --ref "$BENCHMARK_BRANCH"
    fi
}

case "${1:-}" in
    validate)
        validate_request
        printf 'sha=%s\nbranch=%s\nbase_sha=%s\n' "$GITHUB_SHA" "$BENCHMARK_BRANCH" "$BENCHMARK_BASE_SHA" >>"$GITHUB_OUTPUT"
        if [[ -n "$PR_NUMBER" ]]; then
            gh api --method POST "repos/$GITHUB_REPOSITORY/statuses/$GITHUB_SHA" \
                -f state=pending -f context='PR benchmark results' \
                -f description='Manually requested benchmarks are running' \
                -f target_url="$GITHUB_SERVER_URL/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID" >/dev/null
        fi
        ;;
    commit) commit_graphs ;;
    *)
        echo 'Usage: pr-benchmarks.sh validate|commit' >&2
        exit 2
        ;;
esac

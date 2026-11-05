#!/usr/bin/env bash
# Validate a manual benchmark on the default branch or a PR and publish its final graphs and summaries.
set -euo pipefail

##
# Verify the selected PR and require its exact head only before starting the run.
# phase::string -> ret::void
validate_pr() {
    local phase=$1 metadata

    [[ "$PR_NUMBER" =~ ^[1-9][0-9]*$ ]] || {
        echo 'A positive pull-request number is required' >&2
        exit 1
    }
    metadata=$(gh api "repos/$GITHUB_REPOSITORY/pulls/$PR_NUMBER")
    jq -e --arg repository "$GITHUB_REPOSITORY" --arg sha "$GITHUB_SHA" \
        --arg ref "$GITHUB_REF" --arg base "$DEFAULT_BRANCH" --arg phase "$phase" '
        .state == "open" and .draft == false and
        .head.repo.full_name == $repository and .base.repo.full_name == $repository and
        .base.ref == $base and .head.ref != $base and
        ("refs/heads/" + .head.ref) == $ref and
        ($phase != "start" or .head.sha == $sha)
        ' <<<"$metadata" >/dev/null || {
        echo 'Run on the selected branch of an open, ready PR in this repository; its head must match when the benchmark starts.' >&2
        exit 1
    }
    BENCHMARK_BRANCH=$(jq -r '.head.ref' <<<"$metadata")
    BENCHMARK_BASE_SHA=$(jq -r '.base.sha' <<<"$metadata")
}

##
# Validate the target and require its starting revision only before benchmarking.
# phase::string -> ret::void
validate_request() {
    local phase=$1 remote_head

    if [[ -n "$PR_NUMBER" ]]; then
        validate_pr "$phase"
        return
    fi
    [[ "$GITHUB_REF" == "refs/heads/$DEFAULT_BRANCH" ]] || {
        echo 'Without a pull-request number, run benchmarks on the default branch.' >&2
        exit 1
    }
    if [[ "$phase" == start ]]; then
        remote_head=$(git ls-remote --exit-code origin "$GITHUB_REF")
        [[ "${remote_head%%$'\t'*}" == "$GITHUB_SHA" ]] || {
            echo 'The default branch changed before the benchmark started; select its current head.' >&2
            exit 1
        }
    fi
    BENCHMARK_BRANCH=$DEFAULT_BRANCH
    BENCHMARK_BASE_SHA=''
}

##
# Remove only the disposable publication worktree; measured output remains in the runner workspace.
# -> ret::void
cleanup_publication() {
    if [[ -n "${publication_dir:-}" && -d "$publication_dir" ]]; then
        git worktree remove --force "$publication_dir" || true
        rmdir "$publication_dir" 2>/dev/null || true
    fi
    publication_dir=''
}

##
# Retain completed measurements when the target cannot accept them without overwriting newer work.
# reason::string -> ret::void
retain_artifacts() {
    local reason=$1

    echo "::warning::$reason Completed measurements remain available in benchmark-refresh and refresh-resume-data artifacts."
    if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
        printf 'Benchmark source: %s\n\n%s Results remain in the run artifacts.\n' "$GITHUB_SHA" "$reason" >>"$GITHUB_STEP_SUMMARY"
    fi
    printf 'sha=%s\npublication=artifacts\n' "$GITHUB_SHA" >>"$GITHUB_OUTPUT"
}

##
# Commit final publications without uploading raw data or overwriting newer work.
# -> ret::void
commit_graphs() {
    local paths path attribute message graph_commit target_sha publication_sha attempt remote_head diff_status
    local publication_dir=''
    local -a publication_paths

    validate_request publish
    [[ "$GITHUB_SHA" =~ ^[0-9a-f]{40}$ ]] || {
        echo 'An exact source commit is required for benchmark publication.' >&2
        exit 1
    }
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
    # The generated reports describe the measured commit even if publication occurs on a later branch head.
    printf '# Benchmark source\n\nMeasurements in this refresh used source commit %s.\n' "$GITHUB_SHA" >docs/benchmarking/benchmark-source.md
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
    if git diff --cached --quiet; then
        retain_artifacts 'No graph changes were available for publication.'
        return
    fi
    git config user.name 'github-actions[bot]'
    git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
    message="Update benchmark graphs on $BENCHMARK_BRANCH"
    if [[ -n "$PR_NUMBER" ]]; then
        message="Update benchmark graphs for PR #$PR_NUMBER"
    fi
    git commit -m "$message"
    graph_commit=$(git rev-parse HEAD)
    git check-ref-format "refs/heads/$BENCHMARK_BRANCH" >/dev/null
    trap cleanup_publication EXIT

    # Reapply only generated outputs on a fresh descendant; a moving ref never rewrites the measured commit.
    for attempt in 1 2 3; do
        if ! git fetch --no-tags origin "refs/heads/$BENCHMARK_BRANCH"; then
            retain_artifacts 'The publication branch could not be fetched.'
            return
        fi
        target_sha=$(git rev-parse FETCH_HEAD)
        if ! git merge-base --is-ancestor "$GITHUB_SHA" "$target_sha"; then
            retain_artifacts 'The publication branch no longer contains the measured commit.'
            return
        fi
        if git diff --quiet "$GITHUB_SHA" "$target_sha" -- . \
            ':(exclude)README.md' ':(exclude)docs/**' ':(exclude)studies/**'; then
            :
        else
            diff_status=$?
            if [[ "$diff_status" != 1 ]]; then
                echo 'Could not compare the measured source with the publication branch.' >&2
                return "$diff_status"
            fi
            retain_artifacts 'Measured inputs changed after the benchmark started; the newer revision has not been benchmarked.'
            return
        fi
        publication_dir=$(mktemp -d)
        GIT_LFS_SKIP_SMUDGE=1 git worktree add --detach "$publication_dir" "$target_sha"
        if ! git -C "$publication_dir" cherry-pick --no-commit "$graph_commit"; then
            cleanup_publication
            retain_artifacts 'Generated outputs conflict with newer branch changes.'
            return
        fi
        git -C "$publication_dir" commit -m "$message"
        publication_sha=$(git -C "$publication_dir" rev-parse HEAD)
        validate_request publish
        if git -C "$publication_dir" push origin "HEAD:refs/heads/$BENCHMARK_BRANCH"; then
            cleanup_publication
            printf 'sha=%s\npublication=branch\n' "$publication_sha" >>"$GITHUB_OUTPUT"
            if [[ -n "$PR_NUMBER" ]]; then
                gh workflow run ci.yml --repo "$GITHUB_REPOSITORY" --ref "$BENCHMARK_BRANCH"
            fi
            echo "INFO: Published benchmark graphs measured at $GITHUB_SHA."
            return
        fi
        cleanup_publication
        remote_head=$(git ls-remote --exit-code origin "refs/heads/$BENCHMARK_BRANCH") || {
            retain_artifacts 'The publication branch is no longer reachable.'
            return
        }
        if [[ "${remote_head%%$'\t'*}" == "$target_sha" ]]; then
            retain_artifacts 'The graph push was rejected without a concurrent branch advance.'
            return
        fi
        sleep "$attempt"
    done
    retain_artifacts 'The publication branch kept advancing during bounded retries.'
}

case "${1:-}" in
    validate)
        validate_request start
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

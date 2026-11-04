#!/usr/bin/env bash
# Run pytest with a deterministic pull-request event in a fresh child process.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ${1:-} == --help ]]; then
    printf '%s\n' 'Usage: bash scripts/run-pr-tests.sh [--debug] [PYTEST_OPTIONS...]' \
        'Run pytest with the committed synthetic GitHub pull-request event.'
    exit 0
fi

debug=false
if [[ ${1:-} == --debug ]]; then
    debug=true
    shift
fi

# Reset event and provider coordinates so the same fixture is used locally and in CI.
unset CIRCLECI CIRCLE_NODE_INDEX CIRCLE_NODE_TOTAL GITLAB_CI CI_NODE_INDEX CI_NODE_TOTAL GITHUB_TOKEN GH_TOKEN
export GITHUB_ACTIONS=true
export GITHUB_EVENT_NAME=pull_request
export GITHUB_EVENT_PATH="$PWD/.github/events/pull-request.json"
export GITHUB_REF=refs/pull/1/merge
export GITHUB_BASE_REF=main
export GITHUB_HEAD_REF=example-branch
export GITHUB_SHA=1111111111111111111111111111111111111111
export GITHUB_REPOSITORY=example/example
printf '%s\n' 'INFO: Running pytest with the synthetic pull-request event' >&2
if [[ $debug == true ]]; then
    printf '%s\n' 'DEBUG: Provider coordinates and authentication tokens were cleared' >&2
fi
exec bash scripts/project-run.sh pytest "$@"

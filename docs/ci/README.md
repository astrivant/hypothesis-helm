# CI examples

<!-- toc:start -->
**Table of contents**

- [Production promotion](#production-promotion)
- [GitLab](#gitlab)
- [CircleCI](#circleci)
- [GitHub Actions](#github-actions)
- [Binary downloads and caching](#binary-downloads-and-caching)
- [Validation and caches](#validation-and-caches)
  - [Kubesec score gate](#kubesec-score-gate)
  - [Retention between sprints](#retention-between-sprints)
  - [Memory-backed schemas](#memory-backed-schemas)
- [Minimal values in CI](#minimal-values-in-ci)
- [Optional percentage sampling](#optional-percentage-sampling)
- [Remote VM shards](#remote-vm-shards)
<!-- toc:end -->

[Documentation](../README.md) · [Project](../../README.md)

Use the remote definitions below and change `./chart` to your chart directory.
The examples track `main`; replace it with a published commit or tag to pin a version.
The new GitLab and CircleCI URLs become available when these files are published.

All three reference configurations support incremental runs: unchanged charts reuse matching
successful properties, while changed charts or unavailable comparison history run fresh tests.
The outcome cache also retains verified manifest streams, so Kubesec checks every selected
property's output on each invocation. Release tags always force fresh tests. This is chart-level
invalidation; it does not limit a changed chart to only its edited fields.

For filtering modes, worker counts and release coverage requirements, see
[Choosing test coverage](../coverage.md).

## Production promotion

For large production deployments, use the [validation flow](../../README.md#production-validation)
to find failures before taking progressively more expensive actions. These are recommended release gates;
the CI examples below provide chart tests and scanner integration. Our own
[CI chart and security jobs](../../.github/workflows/ci.yml) exercise
the published action with Kubesec enabled across three shards and two Kubernetes versions.
It runs independently on PRs and `main`, and is also required before publishing to PyPI.
Add cluster validation and deployment jobs
to your delivery pipeline, requiring each preceding gate to pass.

| Gate | Question it answers | Evidence required to continue |
| --- | --- | --- |
| hypothesis-helm + Kubesec | Do tested inputs produce acceptable manifests? | Passing tests, reviewed coverage and scanner results. |
| Server-side dry-run in a vcluster or staging cluster | Will that API server admit the release configuration? | Successful admission and validation. |
| Actual staging deployment | Does the application work when its resources are created? | Successful rollout, smoke tests and integration tests. |
| Production promotion | Does the tested release remain healthy under production conditions? | Monitored rollout and application health. |

Run hypothesis-helm with the [coverage appropriate to the release stage](../coverage.md#development-stages),
and enable [Kubesec](https://kubesec.io/) for security checks. Hypothesis-helm prepares and caches the Kubernetes
API schemas, and includes its own schema validator. Kubesec is the only external validator recommended for this pipeline.
Both use the prepared schemas; the examples
[route supported workloads to Kubesec and other resources to the built-in validator](#validation-and-caches).
Require the configured security policy and schema checks to pass, and review incomplete coverage or unsupported resources.
Use schemas for the target Kubernetes version, including any required custom resources.

After testing generated inputs, render the intended release values and submit those manifests for
[Kubernetes server-side dry-run](https://kubernetes.io/docs/reference/using-api/api-concepts/#dry-run),
for example with `kubectl --context staging apply --dry-run=server -f candidate.yaml`.
This exercises API validation and admission without persisting the resources; it does not start containers or test controllers.
The `helm hypothesis test --dry-run` option estimates test work and does not perform this cluster check.
For a vcluster, configure the Kubernetes version, CRDs and admission policies to represent the target environment;
acceptance there establishes compatibility with that environment only.

Deploy the candidate to staging through your normal Helm release process. Wait for the rollout and run application smoke
and integration tests, including the storage, networking and external dependencies that matter to the service.
Promote the same chart package and container image digests after these checks pass. Record environment-specific values;
validate the production values too, since changing configuration can change the rendered resources and behavior.
Retain the test and deployment results with the release so the promotion decision is traceable.

## GitLab

Copy into `.gitlab-ci.yml`:

```yaml
include:
  - remote: 'https://raw.githubusercontent.com/astrivant/hypothesis-helm/main/ci/gitlab.yml'

variables:
  KUBESEC_ENABLED: 'true'
  KUBESEC_SCORE_MINIMUM: '0'

helm-properties:
  rules:
    - if: '$CI_COMMIT_TAG'
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
    - if: '$CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH'
  variables:
    HELM_CHART: ./chart
  parallel:
    matrix:
      - K8S_VERSION: ['1.34.0', '1.35.0']
        SHARD_INDEX: ['1', '2', '3']

helm-report:
  rules:
    - if: '$CI_COMMIT_TAG'
      when: always
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
      when: always
    - if: '$CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH'
      when: always
```

The [shared job](../../ci/gitlab.yml) installs Helm, the plugin and validators;
restores Kubernetes schemas; runs each version across three shards; and saves
reports even on failure. If changing the shard matrix, set the global `SHARD_TOTAL` variable to match.
It sets `GIT_DEPTH: "0"` and caches outcomes and manifests separately for each version and shard.
`HH_INCREMENTAL: 'false'` disables automatic reuse; `HH_RERUN: all` forces fresh tests;
`HH_CACHE: 'false'` bypasses outcome reads and writes. Set `HH_BASE_REF` or
`HYPOTHESIS_HELM_BASE_REF` to override the comparison, and `HH_CACHE_DIR` to relocate its data.
GitLab still transfers its configured cache when outcome reuse is disabled; override the job's
`cache` list to disable those transfers.<sup>[1](https://docs.gitlab.com/ci/caching/)</sup>
`HYPOTHESIS_HELM_REF` pins the plugin separately and defaults to `main`.
The included `helm-report` job downloads every shard's artifacts and runs
`hypothesis-helm aggregate`, producing one final bundle per Kubernetes version.
Version and shard directories prevent artifact collisions. If changing versions,
update the `parallel.matrix` on both `helm-properties` and `helm-report`.

GitLab requires a public raw YAML URL for
[`include:remote`](https://docs.gitlab.com/ci/yaml/#includeremote).
Use `raw.githubusercontent.com` to serve the YAML content.

## CircleCI

Copy into `.circleci/config.yml`:

```yaml
version: 2.1
orbs:
  hypothesis-helm: https://raw.githubusercontent.com/astrivant/hypothesis-helm/main/ci/circleci.yml

workflows:
  chart-properties:
    jobs:
      - hypothesis-helm/test-chart:
          filters:
            tags:
              only: /^v.*/
          chart: ./chart
          kubesec: true
          kubesec-score-minimum: 0
          parallelism: 3
          schema-version: '1.35.0'
      - hypothesis-helm/aggregate:
          requires:
            - hypothesis-helm/test-chart: [success, failed, canceled]
          filters:
            tags:
              only: /^v.*/
          shards: 3
          schema-version: '1.35.0'
          kubesec: true
          kubesec-score-minimum: 0
```

Add `https://raw.githubusercontent.com/astrivant/hypothesis-helm/` to your
organization's [URL-orb allow list](https://circleci.com/docs/orbs/use/managing-url-orbs-allow-lists/).
The [shared orb](../../ci/circleci.yml) installs the plugin remotely by default.
Its `test` command can also run inside an existing job after installing the tools
and preparing schemas with `helm hypothesis schemas`.
The job fetches comparison history and persists outcome caches separately for each report group,
Kubernetes version and shard. Set `incremental: false` or `rerun: all` to run fresh tests,
`cache: false` to disable outcome caching, or `cache-dir` to change its directory.
Use `base-ref` when a feature branch targets something other than the repository's default branch.
The standalone `test` command uses these same parameters, but its caller must restore/save the
cache and fetch Git history. CircleCI cache keys include the node index to prevent shards from
competing for an immutable cache key.<sup>[1](https://circleci.com/docs/reference/configuration-reference/#save_cache)</sup>
`test-chart` persists each shard's report before returning its test or validator
failure. The `aggregate` job consumes the workspace and runs `hypothesis-helm aggregate`.
Its workflow dependency accepts failed jobs using CircleCI's
[status-aware requirements](https://circleci.com/docs/reference/configuration-reference/#requires).
For multiple charts or Kubernetes versions, give each test/aggregate pair a distinct
matching `report-group`. Set `aggregate.package` to the same plugin revision used by
`test-chart.plugin-path` when pinning versions.

## GitHub Actions

Our [CI chart validation jobs](../../.github/workflows/ci.yml) use incremental
testing on PRs and `main`. It fetches full Git history and restores outcomes and manifest
streams separately for each shard and Kubernetes version. Set the action's `incremental: 'true'`
to use the same behavior: unchanged charts reuse matching successful properties; changed charts,
missing history and cache misses run fresh tests. `base-ref` overrides the automatic PR target
or previous trunk commit.<sup>[1](../scanning/README.md#incremental-repository-tests)</sup>

Kubesec still runs on every invocation, checking fresh output and verified cached manifests
with the current schema version and score threshold. Tag builds use `rerun: all`. This is
chart-level invalidation: changing a chart's values or templates retests its selected properties,
including interacting paths. It does not restrict testing to the individually edited fields.

Copy [ci/github.yml](../../ci/github.yml) to `.github/workflows/helm.yml` and change
`chart: ./chart`. It runs on PRs, `main`, version tags and manual dispatch, restores
each shard's outcomes and manifests, and aggregates test and security reports even
after failures. Change the branch and tag patterns to match your release process.


The [action](../../action.yml) installs the tools and uploads per-shard reports.
See [action inputs and outputs](../ci.md#github-action) for worker, cache and artifact settings.
Its [Bash invocation](../../pkg/hypothesis_helm/integrations/github_action.sh) keeps
command flags at the execution site; Python handles shard metadata, cancellation
and action outputs.

## Binary downloads and caching

Helm and optional Kubesec binaries are cached **by default** across
GitHub Actions, GitLab and CircleCI runs. Each binary has its own key containing
the tool name, requested version, operating system and CPU architecture. Updating
one tool's version downloads that tool again without invalidating the others.
For example: `hh-binary-v1-linux-amd64-helm-v4.3.0-exact`.

A restored executable is used without downloading its release archive. Missing
executables are downloaded and extracted into a temporary directory before being
installed in the cache. Failed downloads do not become usable cache entries.
GitHub and CircleCI save binaries before running chart tests; GitLab uploads them
even when tests fail. Each shard restores its own local copy.

| Integration | Disable caching |
| --- | --- |
| GitHub Action | Set `binary-cache: 'false'` in the action's `with` inputs. |
| CircleCI `test-chart` job | Set `binary-cache: false` in the job parameters. |
| GitLab `helm-properties` job | Override `cache: []`. This disables both binary and schema caches. |

GitHub and CircleCI bypass restored binaries when the switch is disabled. Their
schema and test-result cache settings remain independent. To keep schema caching
in GitLab while disabling binary caching, override `cache` with only the schema
entry from the shared job.<sup>[\[1\]](https://docs.gitlab.com/ci/caching/#disable-cache-for-specific-jobs)</sup>

The `kubesec-binary` input can select a preinstalled security scanner. GNU Parallel and OS prerequisites remain installed through the package
manager; these release-binary caches do not replace package-manager caches.

The repository's own benchmark jobs use the same policy. Set the GitHub
repository variable `HH_BINARY_CACHE=false` or CircleCI pipeline parameter
`binary-cache: false` to disable it there.

Cache retention is controlled by the CI provider. An evicted cache is downloaded
again automatically.<sup>[\[2\]](#retention-between-sprints)</sup>

## Validation and caches

Every sharded example has a downstream aggregation job. Its core command is:

```sh
cat downloaded/*/report.json | hypothesis-helm aggregate \
  --shards 3 --run-id "$HH_RUN_ID" --output-dir docs/reports/final
```

All shards must receive the same run ID. Upload idle shards too: a missing report
prevents publication. Aggregation writes one PDF, Markdown, JSON, and JUnit bundle
per chart/version group, including test failures. When enabled, security results
are aggregated separately into `kubesec/` beside the final chart report;
require both the test jobs and aggregation before releasing.

The built-in schema validator validates API schemas by default. With Kubesec enabled, supported
workloads go to Kubesec and remaining resources go to the built-in schema validator. GNU Parallel
uses the available cores; `KUBESEC_JOBS` (GitLab) or `kubesec-jobs` (CircleCI/GitHub)
overrides concurrency. Each scanner receives only its shard's emitted manifests.
Helm failures retain their exit code; scanner failures fail otherwise successful jobs.

### Kubesec score gate

Each scanned workload must pass two checks: it is a valid manifest, and its
[Kubesec score](https://github.com/controlplaneio/kubesec#example-json-output)
meets the configured minimum. The default minimum is `0`; set `5`, for example,
to require additional security measures. Equality passes. A high score never
overrides invalid YAML, failed API validation, a crashed scanner or missing results.
The wrapper evaluates the JSON results itself, including score zero;
[Kubesec 2.14.2's exit policy](https://github.com/controlplaneio/kubesec/blob/v2.14.2/cmd/scan.go)
rejects zero despite labeling it passed in the JSON.
Only that built-in score exit policy is disabled. Command failures and incomplete
output still fail the wrapper. The configurable floor must be nonnegative.

| Entry point | Minimum-score setting |
| --- | --- |
| GitHub Action | `kubesec-score-minimum: '5'` |
| GitLab include | Global variable `KUBESEC_SCORE_MINIMUM: '5'` |
| CircleCI orb | `kubesec-score-minimum: 5` on both `test-chart` and `aggregate` |
| Local wrapper | `hypothesis-helm-kubesec manifests.jsonl --score-minimum 5` |
| This repository's CI | Repository variable `HH_KUBESEC_SCORE_MINIMUM`, default `0` |

Summaries report failed resource attempts and failed checks separately, plus
invalid manifests, below-floor scores, missing reports, scanner failures,
critical and advisory rule counts, and minimum/mean/maximum scores.
One resource can fail both checks. Advisories alone do not fail the gate.
Counts cover the generated configurations, so repeated resource names are
separate attempts rather than distinct deployed workloads.

All CI providers retain raw results, `details.jsonl`, `summary.json`,
`summary.md` and `junit.xml`. GitHub also publishes the Markdown as a job summary.
Every shard continues scanning after a failed resource so the totals cover all
scheduled resources; a cancellation still stops the running processes.

To combine downloaded security artifacts locally:

```sh
hypothesis-helm-kubesec downloaded-security --aggregate \
  --shards 3 --run-id "$HH_RUN_ID" --schema-version 1.35.0 \
  --score-minimum 5 --output docs/reports/final/kubesec
```

Use the same run ID, version and score minimum for scanning and aggregation.
Aggregation verifies all shard IDs, schema snapshots, result-file checksums and
counts, including idle shards. Missing evidence blocks success. Publish the
artifact directory even when the command exits nonzero.

Schemas use a versioned sparse checkout in `schemas`,
persisted across pipelines. Preparation refreshes the selected version once;
validation then uses the local snapshot offline. GitLab cache keys include the
version and shard. If changing its cache directory, also update `cache.paths`.

### Retention between sprints

Aim for **30 days** of retained cache data. Local Hypothesis Helm caches have no
time-based expiry; CI storage policy determines whether they survive between runs.
Content-derived keys still reject incompatible results.

| Provider | Cache lifetime |
| --- | --- |
| CircleCI | The shared job requests **15 days**, the provider maximum and just over two weeks. Check the organization's retention policy. [CircleCI retention](https://circleci.com/docs/guides/optimize/persist-data/) |
| GitLab | Configure the runner cache backend's lifecycle/cleanup policy for **30 days or longer**. CI YAML cannot set cache expiry. [GitLab caching](https://docs.gitlab.com/ci/caching/) |
| GitHub | Native caches can be removed after **seven idle days**, or earlier under storage pressure. The example also saves a **30-day artifact snapshot** of the schemas and outcomes. [GitHub cache limits](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching) |

GitHub snapshots support explicit recovery. To restore one
from a previous trusted trunk run before executing the next run's tests:

```sh
gh run download PREVIOUS_RUN_ID --name helm-cache-1-of-3 --dir .cache/hypothesis-helm
```

Use the matching shard's artifact. The normal restore/save steps refresh native
outcome caches even when tests fail; each shard writes a distinct key. GitLab and
CircleCI's shared definitions persist schemas; see [persisting path outcomes](../ci.md#persisting-path-outcomes)
to retain test results there too.

Reports default to **30 days** in the GitHub action (`artifact-retention-days`)
and GitLab job (`artifacts.expire_in`). Report retention does not extend cache
lifetime. GitHub repository/organization limits still apply to both reports and
[snapshot artifacts](https://docs.github.com/en/actions/tutorials/store-and-share-data).

### Memory-backed schemas

On Linux, optionally set `HYPOTHESIS_HELM_SCHEMA_MEMORY_DIR` (GitLab) or
`schema-memory-dir` (CircleCI/GitHub) to `/dev/shm/helm-schemas`. The selected
snapshot is copied to an existing tmpfs mount once and shared by local workers.
Persistent CI caches stay on disk. Separate runners stage their own copy.

Choose a job-specific directory when jobs share a mount. The mount must have
space for the schemas; parsing still costs time, and tmpfs can swap under pressure
([Linux documentation](https://docs.kernel.org/filesystems/tmpfs.html)).

## Minimal values in CI

Add the second pre-commit hook to export example values with validation status beside
all charts under the configured directory:

```yaml
repos:
  - repo: https://github.com/astrivant/hypothesis-helm
    rev: main # Pin a release or commit in your project.
    hooks:
      - id: helm-hypothesis
        args: [./chart]
      - id: helm-hypothesis-minimal-values
        args: [./chart, --filename, values-minimal.yaml]
```

The hook updates files for review and staging. The GitHub action also accepts
`export-minimal-values: 'true'`. To commit them back automatically, enable
`commit-minimal-values` on a branch workflow with `contents: write` permission:

```yaml
permissions:
  contents: write
steps:
  - uses: actions/checkout@v7
  - uses: astrivant/hypothesis-helm@main
    with:
      chart: ./chart
      commit-minimal-values: 'true'
      minimal-values-filename: values-minimal.yaml
      minimal-values-timeout: 30s
```

Commit-back implies export and defaults to `values-minimal.yaml` and `values-minimal.proof` in **each chart’s
directory**. Only the basename is configurable. Both the exported YAML and its matching `.proof` file are staged. Shard 1 handles export and commit-back
for a sharded action. For multiple chart matrices, use one final export job to
avoid competing pushes. Pushes require a branch checkout and use normal
fast-forward updates. Pull-request merge refs do not commit back.

For incremental repository tests on main/trunk, a generated commit-back at `HEAD`
automatically changes the comparison from `HEAD^` to `HEAD~2`. This keeps the preceding
source change in the diff. The commit-back script identifies its commits with
`Hypothesis-Helm-Minimal-Values: true`; simply enabling export does not widen the window.
Use `fetch-depth: 0` with `actions/checkout` to make comparison history available.
An explicit `--base-ref` takes precedence. See [incremental repository tests](../scanning/README.md#incremental-repository-tests).

Verified examples can be reduced while preserving valid, nonempty output.
Invalid examples are also exported, with the validation failure recorded for review.
A completed reduction establishes deletion-minimality under its validation checks. See [verification and limits](../inputs/README.md).

## Optional percentage sampling

Set the GitHub action inputs `sample-random: '70'` and `sample-min-cases: '128'`
to opt in. The CircleCI command/job exposes the same parameter names. The GitLab
include uses `SAMPLE_RANDOM` and `SAMPLE_MIN_CASES`. Defaults retain all eligible
cases. Use identical settings and seeds on every shard; aggregation checks that
they used the same policy and population.

The [sampling guide](../execution/README.md#percentage-sampling) explains selection
units, protected cases and the factors that determine bug discovery.

## Remote VM shards

Use the [Terraform and Ansible worker setup](../../ansible/README.md) to run generated-suite path shards on private GCP VMs,
collect every worker's artifacts locally, and build one verified aggregate report.

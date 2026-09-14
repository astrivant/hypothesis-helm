# CI examples

[Documentation](../README.md) · [Project](../../README.md)

Use the remote definitions below and change `./chart` to your chart directory.
The examples track `main`; replace it with a published commit or tag to pin a version.
The new GitLab and CircleCI URLs become available when these files are published.

## Recommended workflow

Use progressively broader coverage as changes approach a release:

| When | Recommended mode | Starting CPU / RAM per CI job | Local workers | CI shards |
| --- | --- | --- | ---: | ---: |
| MR / PR | `--filter-adaptive` | 2 vCPU / 4 GiB | `--jobs 2` | 1 |
| Changes on `main` | `--filter` | 2 vCPU / 4 GiB | `--jobs 2` | 1 |
| Before tagging a release | `--exhaustive` | 2 vCPU / 4 GiB | `--jobs 2` | 2 |

These are starting allocations, not measured resource minimums or completion guarantees.
Start large dependency-heavy charts with the same 2 vCPU / 4 GiB and two workers per job, then adjust using measured throughput.
Two release jobs total 4 vCPU / 8 GiB and four workers. Assign different charts to each job;
exhaustive testing cannot split one chart across CI shards.
Exhaustive runs launch concurrent Helm processes; the coordinator validates outputs and writes reports in seeded order.
[Sizing evidence and shard limitations](resources.md) explain how to adjust these estimates.

After installing the plugin, use these commands in the corresponding CI jobs:

```sh
# Merge request / pull request
helm hypothesis test ./chart --filter-adaptive --jobs 2 --chart-timeout 3m --shard none

# Main branch
helm hypothesis test ./chart --filter --jobs 2 --chart-timeout 5m --shard none

# Manual pre-tag check, once per chart with a finite values.schema.json
helm hypothesis test ./chart --exhaustive --jobs 2 --shard none
```

Adaptive sampling falls back to ordinary filtering when the chart has no matching
calibration. Neither filtered mode establishes exhaustive coverage. See the
[adaptive filtering guide](../adaptive-filtering/README.md) for the selection policy.

## Recommended release check

Run the exhaustive check manually on `main` just before tagging a service release.
It checks the accumulated changes on the exact commit you intend to tag. Leave
filtering, trimming and percentage sampling disabled. Explicit exhaustive mode runs
one local chart at a time, with up to eight concurrent Helm processes in this example, and does not support sharding; use a separate job from the
sharded examples below.

The schema must have a supported finite input domain. `--max-cases` bounds enumeration;
`--time-limit` bounds execution. Increase these budgets to fit the chart, and require
completed coverage in the report before tagging. An unsupported domain, a failure or
a timeout does not establish exhaustive coverage. For unbounded domains such as free-form
strings, use a documented finite test domain and state that coverage is limited to it.

The examples below demonstrate sharded property tests, report aggregation and cache
retention. Their manual triggers do not make them exhaustive. For these cached property
checks, `--rerun all` (`rerun: all` in the action) executes the selected tests again and
refreshes their cache, including failures. The explicit exhaustive command above renders
its configurations afresh. If tagging is automated, require the exhaustive check to finish
successfully before tagging the tested commit; these examples do not create tags.

## GitLab

Copy into `.gitlab-ci.yml`:

```yaml
include:
  - remote: 'https://raw.githubusercontent.com/astrivant/hypothesis-helm/main/ci/gitlab.yml'

helm-properties:
  rules:
    - if: '$CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH'
      when: manual
      allow_failure: false
  variables:
    HELM_CHART: ./chart
    KUBESEC_ENABLED: 'false' # true enables security scans
  parallel:
    matrix:
      - K8S_VERSION: ['1.34.0', '1.35.0']
        SHARD_INDEX: ['1', '2', '3']

helm-report:
  rules:
    - if: '$CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH'
      when: always
```

The [shared job](../../ci/gitlab.yml) installs Helm, the plugin and validators;
restores Kubernetes schemas; runs each version across three shards; and saves
reports even on failure. If changing the shard matrix, set the global `SHARD_TOTAL` variable to match.
`HYPOTHESIS_HELM_REF` pins the plugin separately and defaults to `main`.
The included `helm-report` job downloads every shard's artifacts and runs
`hypothesis-helm aggregate`, producing one final bundle per Kubernetes version.
Version and shard directories prevent artifact collisions. If changing versions,
update the `parallel.matrix` on both `helm-properties` and `helm-report`.

GitLab requires a public raw YAML URL for
[`include:remote`](https://docs.gitlab.com/ci/yaml/#includeremote).
Use `raw.githubusercontent.com`, rather than a GitHub HTML page.

## CircleCI

Copy into `.circleci/config.yml`:

```yaml
version: 2.1
orbs:
  hypothesis-helm: https://raw.githubusercontent.com/astrivant/hypothesis-helm/main/ci/circleci.yml

workflows:
  chart-properties:
    jobs:
      - approve-release-check:
          type: approval
          filters:
            branches:
              only: main
      - hypothesis-helm/test-chart:
          requires: [approve-release-check]
          filters:
            branches:
              only: main
          chart: ./chart
          parallelism: 3
          schema-version: '1.35.0'
          kubesec: false
      - hypothesis-helm/aggregate:
          requires:
            - hypothesis-helm/test-chart: [success, failed, canceled]
          filters:
            branches:
              only: main
          shards: 3
```

Add `https://raw.githubusercontent.com/astrivant/hypothesis-helm/` to your
organization's [URL-orb allow list](https://circleci.com/docs/orbs/use/managing-url-orbs-allow-lists/).
The [shared orb](../../ci/circleci.yml) installs the plugin remotely by default.
Its `test` command can also run inside an existing job after installing the tools
and preparing schemas with `helm hypothesis schemas`.
`test-chart` persists each shard's report before returning its test or validator
failure. The `aggregate` job consumes the workspace and runs `hypothesis-helm aggregate`.
Its workflow dependency accepts failed jobs using CircleCI's
[status-aware requirements](https://circleci.com/docs/reference/configuration-reference/#requires).
For multiple charts or Kubernetes versions, give each test/aggregate pair a distinct
matching `report-group`. Set `aggregate.package` to the same plugin revision used by
`test-chart.plugin-path` when pinning versions.

## GitHub Actions

Copy into `.github/workflows/helm.yml`:

```yaml
name: Helm release check
on: workflow_dispatch
permissions:
  contents: read
jobs:
  chart:
    if: ${{ github.ref == format('refs/heads/{0}', github.event.repository.default_branch) }}
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        shard: [1, 2, 3]
    steps:
      - uses: actions/checkout@v7
      - uses: actions/cache/restore@v5
        id: outcomes
        with:
          path: .cache/hypothesis-helm/outcomes
          key: helm-outcomes-v1-${{ runner.os }}-${{ runner.arch }}-1.35.0-${{ matrix.shard }}-of-3-${{ github.run_id }}-${{ github.run_attempt }}
          restore-keys: |
            helm-outcomes-v1-${{ runner.os }}-${{ runner.arch }}-1.35.0-${{ matrix.shard }}-of-3-
      - uses: astrivant/hypothesis-helm@main
        with:
          chart: ./chart
          shard: ${{ matrix.shard }}/3
          jobs: '2'
          run-id: ${{ github.run_id }}-${{ github.run_attempt }}
          schema-version: '1.35.0'
          kubesec: 'false'
          rerun: all
          cache-dir: .cache/hypothesis-helm/outcomes
      - uses: actions/cache/save@v5
        if: ${{ always() && steps.outcomes.outputs.cache-primary-key != '' }}
        with:
          path: .cache/hypothesis-helm/outcomes
          key: ${{ steps.outcomes.outputs.cache-primary-key }}
      - uses: actions/upload-artifact@v7
        if: ${{ always() }}
        with:
          name: helm-cache-${{ matrix.shard }}-of-3
          path: .cache/hypothesis-helm/
          include-hidden-files: true
          retention-days: 30
          if-no-files-found: warn
  report:
    needs: chart
    if: ${{ always() && needs.chart.result != 'skipped' }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-python@v7
        with:
          python-version: '3.13'
      - run: pip install 'git+https://github.com/astrivant/hypothesis-helm.git@main'
      - uses: actions/download-artifact@v8
        with:
          pattern: hypothesis-helm-chart-*
          path: downloaded
      - name: Write final report
        env:
          HH_RUN_ID: ${{ github.run_id }}-${{ github.run_attempt }}
        run: |
          cat downloaded/*/report.json | hypothesis-helm aggregate \
            --shards 3 --run-id "$HH_RUN_ID" --output-dir results/final
      - uses: actions/upload-artifact@v7
        if: ${{ always() }}
        with:
          name: hypothesis-helm-final
          path: results/final/
          if-no-files-found: error
          retention-days: 30
```

The [action](../../action.yml) installs the tools and uploads per-shard reports.
See [action inputs and outputs](../ci.md#github-action) for worker, cache and artifact settings.
Its [Bash invocation](../../pkg/hypothesis_helm/integrations/github_action.sh) keeps
command flags at the execution site; Python handles shard metadata, cancellation
and action outputs.

## Binary downloads and caching

Helm, Kubeconform and optional Kubesec binaries are cached **by default** across
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

Custom `kubeconform-binary` and `kubesec-binary` inputs still use the executable you
provide. GNU Parallel and OS prerequisites remain installed through the package
manager; these release-binary caches do not replace package-manager caches.

The repository's own benchmark workflows use the same policy. Set the GitHub
repository variable `HH_BINARY_CACHE=false` or CircleCI pipeline parameter
`binary-cache: false` to disable it there.

Cache retention is controlled by the CI provider. An evicted cache is downloaded
again automatically.<sup>[\[2\]](#retention-between-sprints)</sup>

## Validation and caches

Every sharded example has a downstream aggregation job. Its core command is:

```sh
cat downloaded/*/report.json | hypothesis-helm aggregate \
  --shards 3 --run-id "$HH_RUN_ID" --output-dir reports/final
```

All shards must receive the same run ID. Upload idle shards too: a missing report
prevents publication. Aggregation writes one PDF, Markdown, JSON, and JUnit bundle
per chart/version group, including test failures. Optional security results remain
separate artifacts; require both the test jobs and aggregation before releasing.

Kubeconform validates API schemas by default. With Kubesec enabled, supported
workloads go to Kubesec and remaining resources go to Kubeconform. GNU Parallel
uses the available cores; `KUBESEC_JOBS` (GitLab) or `kubesec-jobs` (CircleCI/GitHub)
overrides concurrency. Each scanner receives only its shard's emitted manifests.
Helm failures retain their exit code; scanner failures fail otherwise successful jobs.

Schemas use a versioned sparse checkout in `.cache/hypothesis-helm/schemas`,
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

GitHub snapshots are a fallback, not an automatic cache restore. To recover one
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
The exporter does not claim a global minimum. See [verification and limits](../inputs/README.md).

## Optional percentage sampling

Set the GitHub action inputs `sample-random: '70'` and `sample-min-cases: '128'`
to opt in. The CircleCI command/job exposes the same parameter names. The GitLab
include uses `SAMPLE_RANDOM` and `SAMPLE_MIN_CASES`. Defaults retain all eligible
cases. Use identical settings and seeds on every shard; aggregation checks that
they used the same policy and population.

The [sampling guide](../execution/README.md#percentage-sampling) explains selection
units, protected cases, and why this does not guarantee a particular bug recall.

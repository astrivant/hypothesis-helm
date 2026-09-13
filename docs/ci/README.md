# CI examples

[Documentation](../README.md) · [Project](../../README.md)

Use the remote definitions below and change `./chart` to your chart directory.
The examples track `main`; replace it with a published commit or tag to pin a version.
The new GitLab and CircleCI URLs become available when these files are published.

## Recommended release check

Run this manually on trunk just before tagging a service release. It checks the
sprint's accumulated changes across the chart's input surface. Use `--rerun all`
(`rerun: all` in the action) to execute the selected tests and refresh their cache,
including failures. Review every shard and the final report, then tag that exact
commit. Coverage and time budgets still apply; a passing run is not exhaustive
unless the report establishes that coverage.

The examples below use a manual trigger or approval on trunk. GitHub and GitLab
use the repository's default branch; replace `main` in CircleCI if needed. Keep
your existing pull-request checks. If tagging is automated, make its job depend
on successful tests and aggregation; these examples do not create tags.

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
```

The [shared job](../../ci/gitlab.yml) installs Helm, the plugin and validators;
restores Kubernetes schemas; runs each version across three shards; and saves
reports even on failure. If changing the shard matrix, set `SHARD_TOTAL` to match.
`HYPOTHESIS_HELM_REF` pins the plugin separately and defaults to `main`.

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
```

Add `https://raw.githubusercontent.com/astrivant/hypothesis-helm/` to your
organization's [URL-orb allow list](https://circleci.com/docs/orbs/use/managing-url-orbs-allow-lists/).
The [shared orb](../../ci/circleci.yml) installs the plugin remotely by default.
Its `test` command can also run inside an existing job after installing the tools
and preparing schemas with `helm hypothesis schemas`.

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

## Validation and caches

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

Verified examples can be reduced while preserving valid, nonempty output.
Invalid examples are also exported, with the validation failure recorded for review.
The exporter does not claim a global minimum. See [verification and limits](../inputs/README.md).

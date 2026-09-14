# CI integration

Use `--filter-adaptive` on MRs/PRs, `--filter` on `main`, and an unfiltered exhaustive search before tagging.
See the [recommended workflow](ci/README.md#recommended-workflow) for commands and release coverage requirements.

For cached property tests, use `--rerun all` to refresh results for every selected test.
This does not turn a filtered run into an exhaustive search. See the [release check and cache retention
policy](ci/README.md#recommended-release-check); tag the commit whose exhaustive coverage you reviewed.

`helm hypothesis test` and `helm hypothesis run` default to `--shard auto`.
Parallel pipeline jobs automatically select a deterministic partition, while
each runner keeps its own `--jobs auto` worker controller.

## Provider detection

| Provider | Coordinates | Index convention |
| --- | --- | --- |
| CircleCI | `CIRCLE_NODE_INDEX`, `CIRCLE_NODE_TOTAL` | Zero-based index, converted to one-based |
| GitLab CI | `CI_NODE_INDEX`, `CI_NODE_TOTAL` | One-based index |
| GitHub Actions | `HYPOTHESIS_HELM_JOB_INDEX`, `HYPOTHESIS_HELM_JOB_TOTAL`, supplied by the action inputs | Zero-based index, converted to one-based |

CircleCI exposes its [parallel node coordinates](https://circleci.com/docs/reference/variables/).
GitLab exposes [parallel job coordinates](https://docs.gitlab.com/ci/variables/predefined_variables/);
outside a parallel job, its total may be 1 with no index. These single-job cases
run the complete suite without adding a shard directory.

GitHub exposes matrix position through
[`strategy.job-index` and `strategy.job-total`](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts#strategy-context),
not built-in environment variables. Pass these context values to the action's
`job-index` and `job-total` inputs. The action exports the two
`HYPOTHESIS_HELM_JOB_*` variables for the shared detector. Without the action,
bridge them in the workflow yourself:

```yaml
- run: helm hypothesis test ./chart
  env:
    HYPOTHESIS_HELM_JOB_INDEX: ${{ strategy.job-index }}
    HYPOTHESIS_HELM_JOB_TOTAL: ${{ strategy.job-total }}
```

The default `auto` mode runs the full suite locally when no coordinates exist.
`--shard 2/4` overrides detection; `--shard none` disables it, including in
parallel CI jobs. Incomplete, invalid, or conflicting provider coordinates fail
with a setup error rather than silently running the wrong partition. Use
`--shard none` for whole-chart or exhaustive modes in parallel CI jobs.

All shards must use the same revision, selection, shard total, and seed. Keep
`--jobs` budgets appropriate for each runner. CI must require every shard to
succeed; empty partitions are successful, but an empty overall selection remains
an error. See [sharding details](usage.md#distributed-sharding).

## GitHub Action

The repository-root [action.yml](../action.yml) is a composite action for Linux
and macOS runners. It installs Python, Helm, and the plugin from the action's own
checkout, so the tested plugin version follows the action reference. It executes
`helm hypothesis test`, saves the JSON manifest stream, and uploads generated
tests and reports by default, including after a test failure. Failures still fail
the action. Chart dependencies must already be available; add a dependency-build
step for charts that require one.

Callers can reference the remote action directly:

```yaml
name: Helm properties
on: [push, pull_request]
permissions:
  contents: read
jobs:
  chart:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        shard: [1, 2, 3, 4]
    steps:
      - uses: actions/checkout@v7
      - uses: astrivant/hypothesis-helm@main # Use a published commit or tag to pin a version.
        id: hypothesis
        with:
          chart: helm/my-chart
          schema-version: '1.35.0'
          kubesec: 'false' # set true to install and run security scanning
          kubesec-jobs: auto
          job-index: ${{ strategy.job-index }}
          job-total: ${{ strategy.job-total }}
          jobs: auto
          max-examples: '50'
          seed: '42'
          run-id: ${{ github.run_id }}-${{ github.run_attempt }}
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
            --shards 4 --run-id "$HH_RUN_ID" --output-dir reports/final
      - uses: actions/upload-artifact@v7
        if: ${{ always() }}
        with:
          name: hypothesis-helm-final
          path: reports/final/
          if-no-files-found: error
          retention-days: 30
```

No shard calculation is required in shell. The matrix values create four jobs;
the strategy context identifies which partition belongs to each job. For a
non-matrix job, omit `job-index` and `job-total`.

Strategy coordinates cover the entire matrix. If you also vary operating systems
or versions and want full coverage for each combination, pass an explicit
`shard: ${{ matrix.shard }}/4` and include those other dimensions in
`artifact-name` to keep uploads unique.

### Inputs

| Input | Default | Purpose |
| --- | --- | --- |
| `chart` | `.` | Chart path relative to the workspace |
| `shard` | `auto` | CI detection, explicit `INDEX/TOTAL`, or `none` |
| `job-index`, `job-total` | Empty | GitHub strategy coordinates |
| `jobs` | `auto` | PID tuning or a fixed worker count |
| `max-examples` | `100` | Example budget per property |
| `seed` | `0` | Hypothesis seed |
| `timeout` | `30` | Seconds per Helm render |
| `match` | Empty | Keyword selection before partitioning |
| `artifact-dir` | `reports/hypothesis-helm` | Root for generated tests and reports |
| `upload-artifacts` | `true` | Upload the resulting directory |
| `artifact-name` | `hypothesis-helm` | Upload prefix; job and shard IDs are appended |
| `artifact-retention-days` | `30` | Report retention, subject to repository policy; independent of cache lifetime |
| `python-version` | `3.13` | Python version, at least 3.13 |
| `helm-version` | `v4.3.0` | Helm 4 version |

Outputs are `report-dir`, `junit-path`, `manifest-path`, `shard`, and
`exit-code`. Files may be incomplete after cancellation or setup failure.
Sharded output uses `ARTIFACT_DIR/shards/INDEX-of-TOTAL/`; unsharded output uses
the artifact root. Each directory includes `manifests.jsonl` for downstream
validation. Set `upload-artifacts: 'false'` to handle outputs in your workflow.
Give repeated action invocations distinct artifact roots and name prefixes.

The checked-in [action workflow](../.github/workflows/action.yml) exercises the
local action with a three-job matrix. It uses `uses: ./`, so it can run before
any release is published.

### Publishing

1. Commit the action, package changes, documentation, and smoke workflow.
2. Let the GitHub action workflow pass using the local action.
3. Create a release tag such as `v0.1.0` and a GitHub release from that commit.
4. Reference that tag or commit from consuming repositories. Marketplace listing
   can be added when creating the release; the root metadata already includes
   the action name, description, author, and branding.

No release or tag is created by the action itself.

## CircleCI and GitLab

Use the [copyable remote examples](ci/README.md). CircleCI imports the
[URL orb](../ci/circleci.yml); GitLab uses `include: remote` with the
[shared job](../ci/gitlab.yml). Both install the plugin and validators, prepare
cached schemas, and preserve per-shard artifacts.
Both provide a downstream aggregation job that verifies every shard, including
idle shards, and writes the final PDF, Markdown, JSON, and JUnit bundle.

CircleCI detects its node coordinates automatically. The GitLab version/shard
matrix passes explicit indices so each Kubernetes version covers the whole suite.

## Caching installed binaries

The GitHub Action caches Helm, Kubeconform and optional Kubesec binaries by tool,
version, operating system and architecture. Set `binary-cache: 'false'` to disable
both persistence and reuse. This is separate from `cache`, which controls test
outcomes, and `schema-cache`, which controls Kubernetes schemas. Preinstalled
validator overrides are unchanged. The shared GitLab and CircleCI definitions
also cache release binaries by default.<sup>[\[1\]](ci/README.md#binary-downloads-and-caching)</sup>

## Persisting path outcomes

The action accepts `cache-dir`, `cache` (default `true`), and `rerun` (default `auto`).
Set `cache-dir: .cache/hypothesis-helm` and restore/save that directory using your CI
provider's cache facility. Save it even when tests fail so failed path results survive.
Use a distinct outer cache key per runner environment and shard; the framework uses
content-derived keys inside that directory. Restore a previous run's directory to
reuse its results. Local cache entries are also included in uploaded report artifacts
when using the default cache location and the upload includes hidden files. Use the
[release-check example](ci/README.md#github-actions) for explicit outcome cache
restore/save and a 30-day snapshot fallback. Provider cache retention differs from
artifact retention; see [retention between sprints](ci/README.md#retention-between-sprints).

CI still tests the full selection by default. Set `rerun: failed` explicitly to retry
only failed or incomplete paths from a compatible cache. Previously passing paths
produce no new JSON manifests on a cached retry; use `rerun: all` when downstream
validators require a fresh manifest stream for every path. Neither action publication
nor remote cache provisioning is required for the local disk cache.

## Kubernetes API schema validation

The action exposes `kubeconform: 'true'`, `schema-version: 'latest'`,
`schema-cache-dir`, `schema-offline: 'false'`, and `kubeconform-binary` inputs.
The action installs kubeconform by default (`kubeconform-version: v0.7.0`); the
binary input can point to a preinstalled executable. API validation defaults to
enabled. Git must be available on the runner. Pin `schema-version` for reproducibility.
Restore/save the entire schema cache directory (default
`.cache/hypothesis-helm/schemas`) with your provider's cache facility. Set
`schema-offline: 'true'` only after those schemas have been cached. Each matrix shard
then validates locally, without downloading schemas for individual test cases.


Schema persistence is enabled by default in the GitHub Action. Separate
`actions/cache/restore` and `actions/cache/save` steps preserve the sparse checkout,
Git metadata, and immutable snapshots even after a failing test. Cache keys include
the runner platform and requested Kubernetes version, with a unique key per run and
prefix restoration; this allows `latest` to refresh instead of freezing an immutable
CI cache entry forever. Set `schema-cache: 'false'` to opt out of remote persistence.
The repository's own Action workflow explicitly uses validation and this cache.

The CircleCI URL orb prepares and saves schemas before running properties.
The GitLab shared job uses `cache:when: always`. Neither requires putting schemas
inside the report directory. `helm hypothesis schemas --schema-version latest
--schema-cache-dir .cache/hypothesis-helm/schemas` can prepare the cache independently
without generating or running tests.

## Optional Kubesec scans

Set `kubesec: 'true'` to install Kubesec v2.14.2 and GNU Parallel. `kubesec-jobs: auto`
uses the logical CPUs available to the job; set a positive integer to override it.
Scans consume the current shard's manifest stream and retain separate job logs,
security reports, and resource counts for each validator. The action exposes `kubesec-report-dir`
and `kubesec-exit-code`; either test or scanner failure fails the action.

Kubesec and Kubeconform share the prepared local schema snapshot. Schema cache
restore/save also runs when only Kubesec is enabled. Preparation refreshes the
catalog once unless `schema-offline: 'true'`; validators then use local files.
See [CI examples](ci/README.md) for installation and version/shard matrices.

When adding a Kubernetes-version matrix, keep shard indices local to each version
(e.g. `matrix.shard` and `job-total: '3'`). `strategy.job-total` counts both axes and
would partition each version's tests incorrectly. Include the version in artifact
names as well as schema-cache keys.

For optional Linux RAM-backed schema staging, see [memory-backed schemas](ci/README.md#memory-backed-schemas).

With `kubesec: true`, supported workloads receive schema and security validation
through Kubesec; remaining resources go to Kubeconform. This routing also applies
when the separate `kubeconform` input is false. Security runs force `--rerun all`
to produce the manifests needed for validation. Validator failures fail the job
and appear in scan artifacts rather than the Helm JUnit report.

### Minimal values and aggregation

| Input | Default | Purpose |
| --- | --- | --- |
| `run-id` | empty | Common pipeline and attempt identity for shard aggregation. |
| `export-minimal-values` | `false` | Export deterministic concrete values after tests. |
| `commit-minimal-values` | `false` | Export and commit the YAML and matching `.proof` files. |
| `minimal-values-filename` | `values-minimal.yaml` | Basename written inside each discovered chart. |
| `minimal-values-timeout` | `30s` | Search budget per chart. |

See the [piped aggregation and export examples](ci/README.md). Commit-back runs
only in shard 1 (or an unsharded job) and requires branch write permission.

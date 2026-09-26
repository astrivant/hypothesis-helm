# CI integration

<!-- toc:start -->
**Table of contents**

- [Provider detection](#provider-detection)
- [GitHub Action](#github-action)
  - [Inputs](#inputs)
  - [Inline configuration](#inline-configuration)
  - [Other commands](#other-commands)
  - [Publishing](#publishing)
- [CircleCI and GitLab](#circleci-and-gitlab)
- [Caching installed binaries](#caching-installed-binaries)
- [Persisting path outcomes](#persisting-path-outcomes)
- [Kubernetes API schema validation](#kubernetes-api-schema-validation)
- [Optional Kubesec scans](#optional-kubesec-scans)
  - [Minimal values and aggregation](#minimal-values-and-aggregation)
<!-- toc:end -->

Use `--filter-adaptive` on MRs/PRs, `--filter` on `main`, and an unfiltered exhaustive search before tagging.
See the [recommended workflow](coverage.md#development-stages) for commands and release coverage requirements.

For cached property tests, use `--rerun all` to refresh results for every selected test.
This does not turn a filtered run into an exhaustive search. See the [release check and cache retention
policy](coverage.md#release-checks); tag the commit whose exhaustive coverage you reviewed.

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
with a setup error before partition execution. Use
`--shard none` for whole-chart or exhaustive modes in parallel CI jobs.

All shards must use the same revision, selection, shard total, and seed. Keep
`--jobs` budgets appropriate for each runner. CI must require every shard to
succeed; empty partitions are successful, but an empty overall selection remains
an error. See [sharding details](usage.md#distributed-sharding).

## GitHub Action

The repository-root [action.yml](../action.yml) is a composite action for Linux
and macOS runners. It installs Python, Helm, and the plugin from the action's own
checkout, so the tested plugin version follows the action reference. Choose `command: test` (default), `scan`, `audit`, `generate`, or `run`.
The Action uploads results even after findings fail a command, and preserves its
exit status. Use `build-dependencies: 'true'` for recursive local testing or remote
scans; dependencies for generated single-chart suites must already be available.

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
              --shards 4 --run-id "$HH_RUN_ID" --output-dir docs/reports/final
      - uses: actions/upload-artifact@v7
        if: ${{ always() }}
        with:
          name: hypothesis-helm-final
          path: docs/reports/final/
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

CLI options use the same hyphenated names under `with:`, without `--`.
For example, `chart-timeout: 5m`, `filter: 'true'`, `fail: error`, and
`traversal-strategy: sensitivity-first`. Empty optional inputs inherit the CLI
or config default. In particular, `max-examples` no longer forces 100 examples:
`test` and `scan` default to 10 unless your config changes that budget.

| Input | Purpose |
| --- | --- |
| `command` | `test`, `scan`, `audit`, `generate`, or `run` |
| `source` | Local chart/directory, remote source for `scan`, or saved suite for `run`; falls back to `chart` |
| `config` | Policy filename; defaults to `.hypothesis-helm.yaml` in the workspace |
| `config-inline` | Inline YAML overrides; see precedence below |
| `report` | `true` writes Markdown/PDF inside artifacts; a filename chooses another location |
| `output-format` | `json` (default) or `yaml`; the stream is saved at output `manifest-path` |
| `suite-output` | The `generate --output` directory; defaults inside the artifact directory |
| `schema-validation` | The Action's name for `--validate-schemas`; enabled by default |
| `cache` | `false` passes `--no-cache`; enabled by default |

See the **[complete generated input reference](ci/action.md)** for every option,
accepted command, default and output. CLI restrictions still apply: an audit does
not accept execution budgets, remote scans do not support sharding, and filter
presets cannot be mixed with their individual methods. Unsupported options fail
rather than being silently ignored. `report`, custom `values`, dependency builds,
and chart/scan timeouts select recursive execution. Local recursive tests support
sharding: each job discovers the same charts and tests its assigned work within
each chart. Pass a common `run-id` and combine the uploaded results with
`helm hypothesis aggregate`. Use `time-limit` with a generated single-chart suite.

`exhaustive-group` accepts one comma-separated group per line. `ignore` accepts
one finding code per line; `disable-codes` accepts comma-separated codes.
Boolean inputs accept `true` or `false`; empty inherits the default.
`strict: 'false'` explicitly passes `--no-strict`. `fail: 'true'` means any finding;
`fail: error` stops only on errors. Omitted/false `fail` leaves config thresholds
in effect. For `export-topological-graph`, use `true` or a filename.

### Inline configuration

```yaml
- uses: astrivant/hypothesis-helm@main
  id: hypothesis
  with:
    command: test
    source: ./charts
    shard: none
    filter: 'true'
    jobs: '4'
    chart-timeout: 5m
    scan-timeout: 30m
    report: 'true'
    fail: error
    config: .hypothesis-helm.yaml # Optional; the workspace default is discovered automatically.
    config-inline: |
      hypothesis:
        max_examples: 10
        control_characters:
          allow: []
      findings:
        severity:
          HH2003: info
      input_constraints:
        - charts: [my-app]
          path: $.credentials
          hypothesis:
            max_examples: 30
```

The selected file is the base; `config-inline` overrides it. Nested mappings merge,
while scalars and entire lists replace. For example, `ignored: []` clears the base
ignored list, and `input_constraints` replaces all base rules. Normal CLI precedence
then applies: an explicit `max-examples` input overrides the global Hypothesis
budget, while more specific branch budgets remain effective.

Relative schema files and local chart selectors from a file stay relative to that
file. Inline references are relative to the workspace. The effective config is
validated and written to a private runner temporary file without modifying the
checkout. It is also used for minimal-values export, and is not uploaded as an
artifact. Do not put secrets into chart values unless you intend them to appear
in the normal finding/reproduction artifacts.

### Other commands

```yaml
# Remote Git, registered Helm repository, public chart index or OCI reference.
- uses: astrivant/hypothesis-helm@main
  with:
    command: scan
    source: https://github.com/example/charts.git
    filter-adaptive: 'true'
    chart-timeout: 3m
    report: 'true'

# Inspect input/schema gaps without running property tests.
- uses: astrivant/hypothesis-helm@main
  with:
    command: audit
    source: ./chart
    schema-validation: 'false'
    export-topological-graph: 'true'

# Generate and then execute a reusable suite.
- uses: astrivant/hypothesis-helm@main
  id: suite
  with:
    command: generate
    source: ./chart
    schema-validation: 'false'
    artifact-dir: .cache/generated
    artifact-name: generated-suite
- uses: astrivant/hypothesis-helm@main
  with:
    command: run
    source: ${{ steps.suite.outputs.suite-path }}
    jobs: '4'
    artifact-dir: .cache/executed
```

Outputs include `report-dir`, `junit-path`, `manifest-path`, `command-output`,
`suite-path`, `report-path`, `pdf-path`, `shard`, `kubesec-report-dir`,
`kubesec-exit-code`, and `exit-code`. `command-output` captures audit/generation,
dry-run and collection output; these do not produce a manifest stream and cannot
be combined with Kubesec. Requested paths may not exist after an early failure.

Sharded output uses `ARTIFACT_DIR/shards/INDEX-of-TOTAL/`; unsharded output uses
the artifact root. The manifest stream is `manifests.jsonl` or `manifests.yaml`.
Kubesec can consume either choice; YAML is converted to JSON Lines for its dispatcher.
Set `upload-artifacts: 'false'` to handle outputs in your workflow. Give repeated
Action invocations distinct artifact roots and name prefixes.

The [CI chart and security jobs](../.github/workflows/ci.yml) exercise the local
Action with three shards for each of two Kubernetes versions. They run on PRs,
pushes to `main`, manual dispatch and release verification.

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

The GitHub Action caches Helm and optional Kubesec binaries by tool,
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

The action exposes `schema-validation: 'true'`, `schema-version: 'latest'`, `schema-cache-dir`, and `schema-offline: 'false'`.
API validation runs in Python and is enabled by default in the action. Git must be available on the runner.
Pin `schema-version` for reproducibility. No separate API validator binary is installed.
Restore/save the entire schema cache directory (default
`schemas`) with your provider's cache facility. Set
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
--schema-cache-dir schemas` can prepare the cache independently
without generating or running tests.

## Optional Kubesec scans

Set `kubesec: 'true'` to install Kubesec v2.14.2 and GNU Parallel. `kubesec-jobs: auto`
uses the logical CPUs available to the job; set a positive integer to override it.
Scans consume the current shard's manifest stream and retain separate job logs,
security reports, and resource counts for each validator. The action exposes `kubesec-report-dir`
and `kubesec-exit-code`; either test or scanner failure fails the action.

Set `kubesec-score-minimum: '5'` to raise the default floor of `0`. Every resource
must be valid and score at least that minimum. Scanner errors always fail, even
when the returned score meets the floor. Scores equal to the floor pass.

Each shard saves `summary.json`, `summary.md`, `junit.xml`, and `details.jsonl`
alongside the raw scanner output. Summaries count failed resources, invalid
manifests, scores below the floor, failed checks, missing checks, scanner errors,
critical rules and advisories. They also show the observed minimum, mean and
maximum scores. GitHub displays the Markdown in the job summary; all providers
receive a concise terminal summary. These count generated resource attempts:
two different inputs rendering the same resource name remain separate attempts.

The [shared examples](ci/README.md#kubesec-score-gate) aggregate security results
across shards, check run identity and schema consistency, and publish separate
security JUnit results. A resource failing both validity and score contributes
two failed checks but only one failed resource.

Kubesec and the built-in schema validator share the prepared local schema snapshot. Schema cache
restore/save also runs when only Kubesec is enabled. Preparation refreshes the
catalog once unless `schema-offline: 'true'`; validators then use local files.
See [CI examples](ci/README.md) for installation and version/shard matrices.

When adding a Kubernetes-version matrix, keep shard indices local to each version
(e.g. `matrix.shard` and `job-total: '3'`). `strategy.job-total` counts both axes and
would partition each version's tests incorrectly. Include the version in artifact
names as well as schema-cache keys.

For optional Linux RAM-backed schema staging, see [memory-backed schemas](ci/README.md#memory-backed-schemas).

With `kubesec: true`, supported workloads receive schema and security validation
through Kubesec; remaining resources go to the built-in schema validator. This routing also applies
when the separate `schema-validation` input is false. Security runs force `--rerun all`
to produce the manifests needed for validation. Validator failures fail the job
and appear in scan artifacts. Helm JUnit records the Helm tests.

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

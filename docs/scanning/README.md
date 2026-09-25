# Local chart testing and remote repository scans

<!-- toc:start -->
**Table of contents**

- [Incremental repository tests](#incremental-repository-tests)
- [Helm repositories and registries](#helm-repositories-and-registries)
- [Discovery and testing](#discovery-and-testing)
- [Bitnami](#bitnami)
<!-- toc:end -->

[Documentation](../README.md) · [Project](../../README.md)

```sh
helm hypothesis test ./charts --report
helm hypothesis scan https://github.com/bitnami/charts.git --filter --report
helm hypothesis scan git@github.com:my-org/charts.git --report
helm hypothesis test ./charts --values ci/test-values.yaml --report docs/reports/charts
```

`test PATH` discovers charts in a local directory. `scan SOURCE` fetches remote charts
from a Helm repository/chart (see below), an HTTPS Git repository URL, or an SSH URL
(`git@host:owner/repo.git` or `ssh://git@host/owner/repo.git`). Git sources
require Git and use a three-commit shallow checkout of the default branch. Reports retain
the original URL and resolved commit; the temporary checkout is removed after
the scan, while reports, diagnostics, and failing values remain in the artifact
directory. Repository submodules are not initialized automatically.

Public HTTPS repositories work without credentials. Private repositories use
your existing Git credential helper or SSH configuration/agent. Checkout runs
noninteractively; configure credentials and SSH host trust beforehand. Use clone
URLs without embedded HTTPS credentials, query strings, or fragments.

`--clone-timeout 3m` bounds checkout, including commit resolution. The total
`--scan-timeout` also includes this time and takes precedence when shorter.
Failed clones produce a report with incomplete discovery and exit **1**;
checkout timeouts exit **124**, and interruption exits **130**.

## Incremental repository tests

Repository tests reuse a previous chart success only when Git reports the chart unchanged
and the prepared chart, dependencies, selected values, test settings, seed, Helm binary and
tool implementation still match. A cold cache, failure or incomplete run causes fresh testing.
Changing the seed therefore runs a new sample even when chart files have not changed.

```sh
helm hypothesis test ./charts --filter --base-ref origin/main \
  --cache-dir .cache/hypothesis-helm/charts --report
```

Without `--base-ref`, the comparison is selected automatically:

| Execution | Git comparison |
| --- | --- |
| Main, master, trunk or the repository's default branch | Previous commit, `HEAD^`. |
| Same branches, immediately after this tool commits minimal values | `HEAD~2`, retaining the source change before the generated commit. |
| GitHub pull request | Merge base with `GITHUB_BASE_REF`. |
| GitLab merge request | `CI_MERGE_REQUEST_DIFF_BASE_SHA`, or merge base with `CI_MERGE_REQUEST_TARGET_BRANCH_NAME`. |
| Other feature branches | Merge base with the remote default branch, falling back to `main`. |

`--base-ref` overrides `HYPOTHESIS_HELM_BASE_REF`, which overrides automatic selection.
CircleCI supplies the current branch through `CIRCLE_BRANCH`; set `HYPOTHESIS_HELM_BASE_REF`
explicitly when the PR targets another branch. Provider metadata is ignored when the scanned
repository differs from the surrounding CI checkout.<sup>[1](https://docs.github.com/en/actions/reference/workflows-and-actions/variables),
[2](https://docs.gitlab.com/ci/variables/predefined_variables/), [3](https://circleci.com/docs/reference/variables/)</sup>

The two-commit rule recognizes the `Hypothesis-Helm-Minimal-Values: true` trailer written by
the [commit-back step](../ci/README.md#minimal-values-in-ci). Enabling export alone does not
change the comparison. Missing history or an unavailable reference disables reuse; charts
are tested. Local CI checkouts should fetch the comparison history, for example with
`fetch-depth: 0` in GitHub Actions. Arbitrary overrides in remote scans may require a local
checkout with more history followed by `test`.

Completed chart results expire after **21 days**, provided the CI provider retains the
cache that long. Restore and save `.cache/hypothesis-helm/charts`, or the directory supplied
with `--cache-dir`. Writes use a filesystem lock and atomic replacement; concurrent failures
take precedence over conflicting successes. Separate CI cache uploads still require the
provider's normal save/restore policy. `--no-cache` forces fresh execution and disables writes.

Dependency preparation still runs before cache verification and remains outside testing
budgets. Requested exports and external Kubernetes validation require fresh execution.
Helm registry downloads have no Git comparison, so they also run afresh. Reports label reused
results **CACHED PASS**, with zero new attempts, and record the resolved comparison commit.
These rules apply to recursive repository execution; generated property suites retain their
[separate path-result cache](../execution/README.md#runtime-estimates).

## Helm repositories and registries

```sh
# Use a repository already configured in helm repo list.
helm hypothesis scan prometheus-community/prometheus --filter --report
helm hypothesis scan prometheus-community --filter --report
helm hypothesis scan prometheus-community/prometheus --chart-version 27.0.0 --report

# Scan every chart in a public repository index.
helm hypothesis scan https://prometheus-community.github.io/helm-charts/index.yaml --filter --report
helm hypothesis scan https://prometheus-community.github.io/helm-charts --helm-repository --filter --report

# Fetch one OCI chart using the existing Helm registry login.
helm hypothesis scan oci://registry.example.com/charts/service --chart-version 1.2.3 --filter --report
```

A configured repository name scans the latest stable release of each chart in its
index. `repo/chart` selects only that chart. `--chart-version` accepts a version or
Helm semantic version constraint and selects the latest matching release per chart;
it does not scan every historical version. Pre-release-only charts require a
constraint that includes pre-releases. Selection follows [Helm search](https://helm.sh/docs/helm/helm_search_repo/).

Registered repositories use Helm's existing authentication and TLS configuration.
Configure private repositories with `helm repo add` before scanning; OCI charts use
`helm registry login`. The scanner inherits `HELM_REPOSITORY_CONFIG` and
`HELM_REGISTRY_CONFIG`. Credentials are not copied into reports or CLI arguments.
Indexes and downloaded chart caches are isolated per scan, so concurrent source
downloads do not write to the same caches. A public index URL is added only to a
temporary repository configuration, leaving `helm repo list` unchanged.

`scan` rejects existing local paths. Use `test` for those directories. Use
`--helm-repository` to select a remote repository whose alias matches a local directory, or to
distinguish a public HTTP(S) repository base URL from an HTTPS Git clone URL.
OCI sources must identify an individual chart: OCI registries do not expose Helm
`index.yaml` inventories, so this command does not enumerate an entire OCI registry.

`--source-timeout 3m` (also spelled `--clone-timeout`) bounds index refresh and all
chart downloads together. Source preparation also counts toward `--scan-timeout`,
as Git checkout does; dependency builds remain excluded from testing budgets.
Increase the source timeout for large repositories.

Downloaded charts enter the same recursive discovery, dependency preparation, and
testing flow as local charts. Reports retain the original source, selected versions,
and downloaded package SHA-256 checksums. Temporary packages are removed after
reporting. An unavailable package is recorded as **download-failed / N/A** while
other charts continue; this produces exit **2** unless a chart test fails. Failed
source discovery exits **1**; preparation timeout exits **124** and interruption
exits **130**, with an incomplete report and the available package inventory.

## Discovery and testing

Local directories and schema-less charts use recursive testing automatically.
Single schema-backed charts retain their finite and generated-suite modes. Use
`--report`, `--chart-timeout`, `--scan-timeout`, `--values FILE`, or an explicit
dependency-build option to select the discovery/reporting flow for one chart too.

Suite controls (`--match`, `--paths`, `--collect-only`, `--dry-run`, worker/shard
settings, and outcome-cache controls) require an individual schema-backed chart
without recursive reporting options. Use `run` for saved suites.

Local `test` and remote `scan` discover `Chart.yaml` at the root and in child directories, including
nested charts. Discovery checks the required `apiVersion`, `name`, and `version` fields
before invoking Helm. Directory symlinks and tooling directories such as `.git`
and `.venv` are not traversed. Invalid metadata remains visible in the report.

Each application chart gets a dependency build, Helm lint, and generated tests.
When every allowed choice can be listed, the tool tests all configurations in
small spaces or selects configurations covering every allowed pair of choices.
For other charts, it tests discovered values paths in a random order determined
by the seed.<sup>[\[1\]](../usage.md#interaction-coverage)</sup>
`--permutations N` requests finite interaction coverage explicitly. Charts without a
values schema receive inferred path strategies from their values and template references.
Library charts cannot be tested as standalone applications.

If a finite plan cannot be constructed, `test` and `scan` still run generated path tests using the requested
workers, example count, seed, and chart timeout. A warning and the report's `coverage_fallback` record explain
why the requested interaction coverage was unavailable. This sampling does not guarantee N-way coverage;
finite-only filtering, expansion, and grouping options are listed when they cannot apply.
Preparation failures remain failures or incomplete results. A fresh execution cannot pass with zero manifest
test attempts; verified cache reuse and empty shards remain explicit no-work outcomes.

`--filter` applies topology filtering and failure expansion to supported finite
charts. For non-finite charts it restricts generation to known schema, default, and
template paths where analysis permits. Filtering precedes traversal. Each discovered
path is scheduled at most once; failed properties retain their reproducing values.

The [`--filter-adaptive` preset](../adaptive-filtering/README.md#recompute-before-visiting-each-chart)
recomputes complexity after preparing each usable chart, before selecting its property tests. Earlier audits and
cached outcomes do not replace this per-visit calculation. Unsupported calibration keeps ordinary filtering.

Use `--traversal-strategy random|linear|root-first|leaf-first|sensitivity-first` to choose execution order.
Random is the default and uses `--seed`; another seed changes the subset reached
before timeout. Discovery lists all identified paths, but execution may stop before
reaching the end of that list. Reports distinguish visited, completed, incomplete,
and remaining paths.<sup>[\[2\]](../execution/README.md#value-path-traversal)</sup>

`sensitivity-first` uses the default pairwise coverage when `--permutations` is omitted.
For a chart whose domain cannot be finitely enumerated, scans warn and fall back to seeded random path
testing, including when `--permutations N` is explicit. The report records the requested and effective strategies.

Discovery also reads dependency conditions and tags from chart metadata, including
controls absent from `values.yaml`, and inspects installed child charts under their
alias-qualified values paths. When testing a child setting, generation prioritizes
an enabled context and keeps the original context eligible. It preserves the selected
value and parent-schema constraints; it does not force activation when those conflict.
Nested dependencies include their ancestor controls. This applies to path testing
with or without `--filter`, including generated suites.
If the parent values file omits a dependency's settings, path tests reuse the installed
child's defaults. Testing `redis.sentinel.service.headless`, for example, does not
randomly change sibling settings such as Sentinel's timeout or volume mounts.
Changing an array entry preserves its other entries because Helm replaces arrays.
Additional values are generated only when the existing context cannot accommodate
the selected input or satisfy the schema.
When testing a fallback condition or tag, generation also tries removing earlier
conditions that would mask it, provided the parent schema allows that change.

JSON reports include dependency relationships, predicted baseline states, enabled
contexts proposed, and contexts that could not be established. Per-path results
count render attempts by predicted activation state; these are not proof of child
output coverage. Missing/ambiguous sources and unresolved forwarding remain visible.
Finite permutation runs propose activation interaction groups within the configured
group budget. Graph exports include dependency-control and conditional-template edges.

Random string generation excludes C0/C1 control characters, including tabs and `\u001f`,
from generated values and object keys at every nesting level. Line feeds, carriage returns, and other Unicode text remain
eligible for embedded configuration and application content. This sampling policy
does not change the chart's schema, edit supplied values, or constrain explicit
finite enumeration. Historical reports retain their original counterexamples.

Filtering changes which inputs the generator tries, not which inputs the chart's
schema allows. The original schema still validates every input. The generator
keeps arbitrary keys available in empty maps, maps defined by schema rules or key
patterns, and maps accessed through computed keys. If it cannot interpret a schema
rule or template operation, it reports that uncertainty and keeps the affected
inputs available. The inventory lists identifiable paths and marks computed
keys it cannot resolve.<sup>[\[3\]](../inputs/README.md)</sup>

Inferred types guide generation; they do not become new validation requirements.
Generation errors and budget exhaustion remain incomplete coverage, not chart bugs.

Add `--fail` to exit **1** on the first lint, render, or property-test failure
(or execution error). The failing input and available statistics are retained;
later charts remain pending/N/A, with `scan_status: failed-early`. With `--filter`,
this also stops failure expansion; path traversal stops before the next property.
Counterexamples are not shrunk. Missing values, blocked dependencies,
and other incomplete/N/A results do not trigger this flag. Each scan process
stops independently; it does not cancel scans launched by other workers.

```sh
helm hypothesis test ./charts --filter --fail --report
```

`--values` defaults to `values.yaml`, relative to each chart; an absolute path
uses the same file for every chart. The selected file replaces the default values
in an isolated working copy. Missing values fail a single-chart scan. In a tree,
the scanner records that chart as **N/A** and continues with the others.

Dependency builds use `Chart.lock` when present; without it, Helm resolves
versions from `Chart.yaml`. Source charts and their lockfiles remain unchanged.
Use `--no-build-dependencies` for an offline tree with dependencies already vendored.
Configure Helm repositories and registry credentials as for a normal dependency build.

`--chart-timeout 3m` is the property-test execution budget **per chart**, excluding
planning and dependency preparation. `--time-limit` remains a compatibility alias.
`--timeout 30` bounds each Helm command.

Add `--scan-timeout 9m` to cap scanning time, including cloning, discovery, linting,
planning, and property tests. The budget pauses during dependency builds, which
remain bounded by `--timeout`. The scan deadline takes precedence over a longer
chart budget. Its default is unlimited. Dependency preparation, cleanup, and report
writing can make total process lifetime exceed the scan budget.

Reports separate `dependency_preparation_seconds`, `testing_seconds`, and
`elapsed_seconds` (wall-clock duration), both per chart and for the scan.
Chart testing includes baseline checks, input planning, and property tests;
the runner's `execution_seconds` retains its narrower execution measurement.
Dependency time is excluded even when a build fails, times out, or is interrupted.
Historical reports without these measurements retain their wall-clock duration;
their testing time is not inferred.

```sh
helm hypothesis test ./charts --chart-timeout 3m --scan-timeout 9m --report
```

A scan timeout exits with **124**, preserves available test statistics, and leaves
unstarted charts pending/N/A. If discovery times out, `discovery_complete: false`
means the number of additional charts is unknown. Interrupting a scan likewise
saves partial results and exits with **130**.

`--report` writes `<directory-name>_<epoch>_report.md` and `.pdf` in the current
`docs/reports/` directory. An explicit stem or either filename extension overrides both
paths. Reusing an explicit output path replaces the previous report.
The PDF title page records the scan's start and finish, source commit, Hypothesis and
hypothesis-helm versions, and full shell-quoted scan command. The working directory
is included so relative paths can be resolved. These details are captured during execution
and retained in `scan.json`; republishing preserves them. Older runs without this metadata
show “not recorded” rather than the versions installed when publishing the report.

A clickable contents page follows, then one overview page containing
two aligned matrices. Each cell represents one chart, in the same order as the chart sections.
The first matrix uses the chart's highest observed finding category: red for violations,
amber for warnings, and blue for diagnostics that need investigation. Green means no findings
in the completed sample. Gray cells distinguish incomplete and untested charts; hatching also
marks unfinished testing on cells that already have findings. These categories come from the
[finding catalog](../rules/README.md), not an estimate of security or business impact.
The second matrix colors the same cells by measured time. Missing timings show `--`, not zero.
Cell numbers match the chart sections; clicking either matrix's cells in the PDF opens those details.
Testing time excludes dependency preparation. Historical results without testing
measurements show elapsed chart time instead; missing timings are marked unavailable.
Zero recorded errors do not imply full coverage, especially for incomplete scans.
PDF bookmarks link to every chart and diagnostic. Pages from page 3 onward link back to contents.
Markdown reports have linked contents and use the matching `<stem>-overview.png`;
keep that image beside the Markdown file when sharing it. The PDF embeds the image.

To measure new sensitivity plots during the same invocation, add `--max-mutations 48`
with `--report` on either `test` or `scan`. This selects up to 48 distinct Boolean/integer
fields and measures their 1,128 pairs when the schema and time budget permit. It is separate
from the bug-testing traversal and does not change `--max-examples` or `--permutations`.

```sh
helm hypothesis test ./charts --filter --jobs 6 --chart-timeout 120s \
    --max-mutations 48 --sensitivity-timeout 3m --report docs/reports/charts
```

Measurement runs after chart testing, using `--jobs`, `--seed`, `--values`, and the renderer
settings from the scan. `--sensitivity-timeout` defaults to an additional three minutes per chart,
excluding dependency preparation. A scan stopped by a deadline, interruption, or `--fail` skips
this extra phase. Measurement failures and missing pairs remain marked as unavailable; they do
not change the chart's test findings. Without `--max-mutations`, reporting reuses available plots.
Generated panels go beside the report in `<stem>-figures/`; raw measurements remain in the run's
artifact directory. `hypothesis-helm-report-figures` can also regenerate them from saved scan data.

Reports also measure up to 64 reference configurations per tested chart for a shared output-space
PCA comparison. **Graph structure** and **Output space** have separate appendix pages after the chart results;
the scan summary starts on page 4, after the cover, contents, and overview. Size and connectivity plots stay stacked
vertically in the graph appendix. Chart colors stay the same before and after selection, and both panels use one fitted
coordinate system. The figure caption links to the chart color key and measurement details.

Set `--pca-samples N` to change the reference size (`0` disables it), and `--pca-timeout 1m` to set
its separate per-chart budget. These measurements do not consume the chart-testing timeout or add
findings. They use schema-valid Boolean and integer changes around the baseline, not every possible
output. Failed renders and unavailable measurements are excluded, not plotted as zero. Without
filtering, both panels match. Finite selectors are replayed on this bounded sample; path scans use
their saved selection inventory. See the report's **Output-space PCA** appendix for the limits of
this comparison.

To update an existing report without repeating its chart tests:

```sh
hypothesis-helm-report-figures path/to/scan.json --report docs/reports/charts \
    --source-root ./charts --max-mutations 0 --pca-samples 64 --pca-timeout 1m
```

Use the source revision recorded in the scan. The original findings stay unchanged; enriched
measurement data is saved under `.cache/report-figures/`.

JSON statistics, lint/dependency logs, and failing values go under
`.cache/hypothesis-helm/runs/` for local `test` and `.cache/hypothesis-helm/scans/` for remote `scan`;
override that parent with `--artifact-dir`.

When testing finishes, times out, or stops with Ctrl-C, the terminal prints a short summary and
the location of the saved results. It does not dump the full JSON report. Read `scan.json` from
that location for automation; single-chart tests save `report.json`. Interrupted scans retain
completed results and exit with code 130. Explicit `-o json` or `-o yaml` still streams rendered
manifests to stdout, with the terminal summary on stderr.

Reports group failures by Helm chart. Each diagnostic appears once per chart,
followed by up to two failing examples, with up to six paths and values per example.
New runs show overrides that differ from the chart defaults, including dependent
fields. Older path-based results show the selected fields and link to the full context.
Long values and diagnostics are shortened explicitly. These previews do not establish
an independent or minimal cause. Complete inputs, diagnostics, and additional cases
remain in JSON and local artifacts; the Markdown and PDF are brief summaries.
Links labeled "Full input and diagnostic" and "Chart artifacts" are included only when the run
provides an HTTPS destination or explicitly publishes the existing artifacts to a public repository.
Local-only run directories are not published as PDF hyperlinks.
Missing reproducing values are reported explicitly.

Use `--export-suppressions` to save a categorized, editable `suppressions.yaml` in each chart's artifact directory as soon as it finishes,
including during recursive scans. Reports link to these drafts; they do not change the run's findings or active configuration.
See [reviewing generated suppressions](<../rules/README.md#export-suppressions-from-a-run>) for their scope and how to apply selected entries.

New failure artifacts include `changes.json`: DeepDiff comparisons of effective
values and parsed manifests against the defaults, plus a replayable record of the
exact overrides. Summaries show previous values and up to six manifest changes.
Document order, list order, and scalar types remain significant. A template error
or invalid YAML may prevent a manifest comparison; the JSON records that limitation.
Comparisons use observed renders and do not run extra Helm commands.

Reconstruct the failing overrides, including explicit `null` deletions:

```bash
helm hypothesis replay-changes reports/example/changes.json --output values-replayed.json
```

Use `--section values --baseline reports/example/values-baseline.json` to reconstruct
effective values, or `--section manifests --baseline reports/example/manifests-baseline.json`
for parsed output. Effective values describe the merged input; use the default
`overrides` section to reproduce a Helm invocation, since omitted keys inherit chart defaults.
Replay verifies the complete baseline and result checksums before writing output.
Records use JSON, with a fixed set of scalar and container types.
If a field delta cannot reproduce the exact JSON, the record explicitly stores a
whole-document replacement. This handles signed zero and unusual quoted keys.
These comparisons describe observed changes. Existing render hashes and compiler
proofs govern reuse; causal attribution requires further analysis.

`--filter` also recognizes supported explicit configuration rejections in templates.
Reports list their requirements and related values separately from manifest errors.
Counters distinguish excluded candidates, adjusted candidates, and real Helm
verification renders; exclusions never count as passing tests. A property with no
accepted generated inputs has status `configuration-rejected`. Unknown guards
remain testable. Automatic exclusions apply to inferred inputs; rejections of
inputs admitted by an authored values schema remain visible failures, with their
recovered requirements. See [compiler passes](../compiler/selection.md#rejection-guided-generation).
For charts without dependencies, Helm checks the first two different inputs that
the compiler predicts will violate each recognized requirement. These checks are
called **witness checks**. Later exclusions use the supported compiler analysis.
For charts with dependencies, Helm must confirm every predicted rejection before exclusion,
because child defaults and imported values can change what a parent template sees.
If Helm accepts a predicted rejection or returns a different error, that requirement is disabled
for automatic exclusion. Witness checks validate specific predictions; later exclusions
rely on the supported compiler analysis described above.

Published reports use absolute GitHub links targeting `main`.
PDF links are blue, underlined, and clickable, including links within paragraphs.
Their destinations become available when the reports and retained artifacts are on `main`.

YAML parser failures show their finding code, failure status, and triggering paths and values.
Parser excerpts and library suppression advice remain in the saved run data, rather than the Markdown or PDF summary.
This changes presentation only; duplicate-key validation stays enabled.

Repeated errors share diagnostic IDs across charts and dependencies. Dependency
template errors match by chart name, version, template contents, and terminal
diagnostic; unresolved sources use exact diagnostic matching. Different versions
and messages remain separate. JSON includes `error_groups`, `error_summary`, and
per-chart `error_refs`, while retaining original errors and artifacts. Grouping
does not skip tests or change chart statuses, and a matching diagnostic does not
prove a shared root cause.

Add `--export-minimal-values` to retain an example YAML baseline with validation status and compiler
inventory for each chart. An optional filename overrides the generated name; chart-relative subdirectories
keep exports separate. The default is `values-minimal-<checksum>-<epoch>.yaml`.
Reports include identified input-field counts and observed variation where
available. See [Input inventory](../inputs/README.md) for the measurement contract.

Exit codes: **0** means every discovered chart passed property tests; **1** means
invalid metadata, invalid execution, or test failures (also a sole chart missing
values); **2** means incomplete/N/A coverage or no charts; **130** means interrupted.

Ctrl-C (SIGINT) and CI termination (SIGTERM) stop scheduling new paths and charts, stop owned Helm processes,
and join workers before returning. Completed results and interrupted paths remain in the partial report;
unstarted charts remain pending. This also applies when a worker handles the interrupt and returns a partial result.
A successful sample establishes that its tested inputs passed the selected checks.

## Bitnami

```sh
git submodule update --init --depth 1 third_party/bitnami-charts
helm hypothesis test third_party/bitnami-charts --filter --disable-codes HH2006 --report docs/reports/bitnami
```

The submodule pins the source revision. Locked dependencies are downloaded from
the chart's declared repositories; inaccessible dependencies are reported as N/A.
These report commands suppress HH2006 warnings for objects without a declared structure.
Their values are still tested, and other findings remain enabled. Add comma-delimited codes to `--disable-codes` only when intended.

The [retained Bitnami scan](../reports/bitnami.md) includes one combined PDF and
the findings and coverage status for each visited chart. Raw measurements and logs remain in the local run cache.

Additional chart sources remain available in the repository's Git submodules for future scans.

<!--
The external chart sources are retained as submodules under
`third_party/bitnami-charts` and `third_party/prometheus-community-helm-charts`.
Initialize the Prometheus source with:

```sh
git submodule update --init third_party/prometheus-community-helm-charts
helm hypothesis test third_party/prometheus-community-helm-charts/charts --filter --disable-codes HH2006 --report
```

The [retained Prometheus Community scan](../reports/prometheus.md) includes all
46 discovered charts, a combined PDF, and per-chart findings and reproducing values.
-->

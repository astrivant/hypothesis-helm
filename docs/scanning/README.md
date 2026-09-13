# Scan a chart repository

[Documentation](../README.md) · [Project](../../README.md)

```sh
helm hypothesis scan ./charts --report
helm hypothesis scan https://github.com/bitnami/charts.git --filter --report
helm hypothesis scan git@github.com:my-org/charts.git --report
helm hypothesis scan ./charts --values ci/test-values.yaml --report reports/charts
```

The source can be a local directory, a Helm repository/chart (see below), an HTTPS Git repository URL, or an SSH URL
(`git@host:owner/repo.git` or `ssh://git@host/owner/repo.git`). Remote sources
require Git and use a shallow checkout of the default branch. Reports retain
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

Existing local paths take precedence over repository names. Use `--helm-repository`
to select a repository when its name also identifies a local directory, or to
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

The scanner finds `Chart.yaml` at the root and in child directories, including
nested charts. It checks the required `apiVersion`, `name`, and `version` fields
before invoking Helm. Directory symlinks and tooling directories such as `.git`
and `.venv` are not traversed. Invalid metadata remains visible in the report.

Each application chart gets a dependency build, Helm lint, and schema-generated
property tests. Finite domains use automatic exhaustive/pairwise coverage;
other supported schemas use whole-chart sampling. `--permutations N` requests
finite interaction coverage explicitly. Without `--filter`, charts without a values schema receive
baseline lint/render checks, reported as **baseline-only**, not property-test passes.
Library charts cannot be tested as standalone applications.

`--filter` applies topology trimming and failure expansion to supported finite
charts. For non-finite charts it tests schema-declared, defaulted, and referenced
configuration paths first, then samples the original-schema cases outside that generation view last. The first phase receives at most 90% of the chart budget; the last
phase receives the remainder. Cases are deferred, not proved irrelevant or removed.
Both phases keep separate findings, counters, and reproducing values.

The prioritizer uses a generation-only view. The original schema still validates
every input and remains unchanged. Empty maps, pattern/schema-defined maps, and
maps accessed dynamically remain open in the known-input phase. Unsupported
schema compositions remain unconstrained by this optimization. Opaque helper and
`tpl` contexts are reported explicitly; arbitrary root keys remain eligible in
the final phase. No report claims complete coverage of those unknown inputs.

With `--filter`, charts without a values schema also receive known-input testing
inferred from defaults and references, followed by broad robustness sampling.
Inferred types guide generation; they do not become new validation requirements.
Generation errors and budget exhaustion remain incomplete coverage, not chart bugs.

Add `--fail` to exit **1** on the first lint, render, or property-test failure
(or execution error). The failing input and available statistics are retained;
later charts remain pending/N/A, with `scan_status: failed-early`. With `--filter`,
this also stops failure expansion and skips the deferred phase after a known-input
failure. Counterexamples are not shrunk. Missing values, blocked dependencies,
and other incomplete/N/A results do not trigger this flag. Each scan process
stops independently; it does not cancel scans launched by other workers.

```sh
helm hypothesis scan ./charts --filter --fail --report
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
helm hypothesis scan ./charts --chart-timeout 3m --scan-timeout 9m --report
```

A scan timeout exits with **124**, preserves available test statistics, and leaves
unstarted charts pending/N/A. If discovery times out, `discovery_complete: false`
means the number of additional charts is unknown. Interrupting a scan likewise
saves partial results and exits with **130**.

`--report` writes `<directory-name>_<epoch>_report.md` and `.pdf` in the current
working directory. An explicit stem or either filename extension overrides both
paths. Reusing an explicit output path replaces the previous report.
JSON statistics, lint/dependency logs, and failing values go under
`reports/scans/`; override that parent with `--artifact-dir`.

Repeated errors are grouped automatically across charts and dependencies. Reports
show each diagnostic once, with links to every affected chart and phase. Dependency
template errors match by chart name, version, template contents, and terminal
diagnostic; unresolved sources use exact diagnostic matching. Different versions
and messages remain separate. JSON includes `error_groups`, `error_summary`, and
per-chart `error_refs`, while retaining original errors and artifacts. Grouping
does not skip tests or change chart statuses, and a matching diagnostic does not
prove a shared root cause.

Add `--export-minimal-values` to retain a example YAML baseline with validation status and compiler
inventory for each chart. An optional filename overrides the generated name; chart-relative subdirectories
keep exports separate. The default is `values-minimal-<checksum>-<epoch>.yaml`.
Reports include identified input-field counts and observed variation where
available. See [Input inventory](../inputs/README.md) for the measurement contract.

Exit codes: **0** means every discovered chart passed property tests; **1** means
invalid metadata, invalid execution, or test failures (also a sole chart missing
values); **2** means incomplete/N/A coverage or no charts; **130** means interrupted.
A successful sample is not a proof that all possible values work.

## Bitnami

```sh
git submodule update --init --depth 1 third_party/bitnami-charts
helm hypothesis scan third_party/bitnami-charts --report reports/bitnami
```

The submodule pins the source revision. Locked dependencies are downloaded from
the chart's declared repositories; inaccessible dependencies are reported as N/A.

The [retained Bitnami scan](../reports/bitnami.md) includes one combined PDF and
all available per-chart measurements and logs.

The external chart sources are retained as submodules under
`third_party/bitnami-charts` and `third_party/prometheus-community-helm-charts`.
Initialize the Prometheus source with:

```sh
git submodule update --init third_party/prometheus-community-helm-charts
helm hypothesis scan third_party/prometheus-community-helm-charts/charts --filter --report
```

The [retained Prometheus Community scan](../reports/prometheus.md) includes all
46 discovered charts, a combined PDF, and per-chart findings and reproducing values.

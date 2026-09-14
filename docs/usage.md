# Helm command reference

Install with Helm 4 and Python 3.13+ available:

```sh
PYTHON=python3.13 helm plugin install https://github.com/astrivant/hypothesis-helm
```

For a checkout, use `helm plugin install .`. The install hook bundles the package,
Hypothesis, ruamel.yaml, and pytest into the plugin's private virtualenv. End users
need neither Poetry nor a separately installed test runner. Helm 4 is unverified.

## Test a chart

```sh
helm hypothesis test ./chart
helm hypothesis test ./chart --paths --max-examples 50 --seed 42
helm hypothesis test ./chart --match replicas
helm hypothesis test ./chart --collect-only
```

Inside a chart directory, `helm hypothesis test` uses the current directory.

`test` chooses coverage automatically when it can list every allowed input choice.
It multiplies the number of choices for each field to count possible configurations
before applying constraints between fields. If that count is **less than 10,000**
and fits the case budget, it tests the full space. Larger finite spaces receive
coverage of every allowed pair of choices, plus full coverage within selected
groups of related fields when affordable. Otherwise, it tests values paths
individually and logs the reason.<sup>[\[1\]](#interaction-coverage)</sup>

`--paths` explicitly selects the generated-suite workflow: it adds fields discovered
in templates to the working input model, generates one Python test per values path, and executes the
suite. Collection and distributed sharding also select this workflow. Recursive
repository tests support `--jobs N` directly: charts run in sequence, with N workers
sharing the current chart's path queue and timeout.
`--max-examples` defaults to **10 per property** for `test` and `scan`, not a total across the chart.
Shrinking a failure can require additional attempts. `--match` selects
Python test names with a pytest keyword expression; path segments are included in
those names. `--collect-only` generates and lists the tests without rendering.
An empty selection returns a nonzero status rather than reporting success.

Progress is logged for each path as it is added to the input model, assigned a generated test,
and tested. Generation messages go to stderr so `generate` keeps its JSON output
on stdout. Test progress appears live, once per selected property rather than once
per Hypothesis example:

```text
[INFO] Coalescing path $.image.tag
[INFO] Generating test for path $.image.tag (schema)
[INFO] Testing path $.image.tag
```

`audit` similarly logs each audited path. Wildcard items appear as `[*]`; unusual
keys use quoted bracket notation.
`--match` limits test execution logs to selected properties. `--collect-only`
logs generation and lists tests without claiming to execute them.

The plugin invokes pytest with its own Python interpreter, pins the invocation's
Hypothesis seed, and streams failures and progress to the Helm console. Ambient
pytest configuration, `PYTEST_ADDOPTS`, and auto-loaded third-party pytest plugins
are excluded. Saved-suite Python and suite-local `conftest.py` remain executable
and editable.

Use a dedicated artifact directory for each chart/run:

```sh
helm hypothesis test ./chart --artifact-dir reports/my-chart \
  --release example --namespace testing --kube-version 1.31.0 --timeout 30
```

`--helm` selects the renderer executable. `--timeout` bounds each Helm invocation,
not the complete suite; use your CI job timeout for an overall budget. Pass
`--allow-empty` when the chart legitimately renders no resources. Dependencies
must already be present; `helm dependency build ./chart` prepares them.
No release is installed and no cluster is required.

## Inspect and rerun generated suites

```sh
helm hypothesis generate ./chart --output generated-tests
helm hypothesis run generated-tests
helm hypothesis run generated-tests --seed 42 --match replicas
helm hypothesis run generated-tests --collect-only
```

`generate` only exports the suite for review or customization. `run` executes its
saved Python without regenerating it, preserving edits. It accepts seed, selection
and collection options. Rendering settings and per-property example budgets are
embedded in the generated source; configure them through `test` when creating a
suite or edit the saved Python. Both commands use the plugin's bundled dependencies.

| Artifact | Meaning |
| --- | --- |
| `test_chart_values.py` | Editable, named Hypothesis properties and embedded render settings |
| `values.coalesced.yaml` | Round-trip YAML snapshot with discovered levers merged in |
| `values.inferred.schema.json` | Original schema extended with inferred undocumented properties |
| `paths.json` | Schema fragments, strategies, provenance and unresolved constructs |
| `junit.xml` | Test outcomes and failure details, including Hypothesis counterexamples |
| `report.json` | Run status, pytest exit code, seed, selection and result location |
| `hypothesis-helm.pytest.ini` | Dedicated pytest configuration for the plugin invocation |

`test` writes these beneath `--artifact-dir` (default `reports/hypothesis-helm`).
`run` writes results beside the saved suite. Reusing a directory overwrites its
artifacts; regenerate after chart changes. Generated chart paths are relative to
the suite directory. Keep that relationship when moving the repository.

Passing tests return 0 and failing properties return 1. Pytest collection, usage,
internal-error and empty-selection exit codes propagate through Helm. Invalid
chart paths, schemas and command setup return 2. Counterexamples appear in the
console and JUnit failure details; no Python command is needed to rerun the suite.

## Coalescing, paths, and strategies

The coalescer loads `values.yaml` with `ruamel.yaml`, preserving comments, quotes,
anchors, merge keys, and existing values in an independent round-trip copy.
Source chart files are not rewritten. A missing template-referenced key takes an
unambiguous schema default or literal `default`/`dig` fallback when available.
Parent objects are created as needed. Unknown or conflicting defaults become null
placeholders with diagnostics; they are not assumed to accept only null.

Undocumented types are inferred from existing YAML and recovered literal fallback
values. No arbitrary numeric bounds or enums are invented. The temporary testing
schema is extended for those discovered properties, including when the original
schema forbids additional keys. Existing documented constraints are retained.
Review `paths.json` and the inferred schema before adopting them as a contract.

The inventory includes containers, leaves, local schema references, composition
branches, array items, and schema-defined map entries. Containers receive tests
for lengths, empty collections and optional fields. Wildcards select concrete
entries at runtime; missing required siblings are drawn from their schema.
Each test first uses baseline values, then draws a dependent context if necessary.
The complete schema is validated in addition to each path's strategy.

| Schema evidence | Strategy |
| --- | --- |
| Boolean | `st.booleans()` |
| Bounded integer | `st.integers(...)` |
| Number | Finite `st.floats(...)` |
| String length bounds | `st.text(...)` |
| Enum / constant | `st.sampled_from(...)` / `st.just(...)` |
| Array items and lengths | `st.lists(...)` |
| Objects, regex, multiples, unique arrays and compound constraints | `hypothesis_jsonschema.from_schema(...)` |

The runtime dependencies are [Hypothesis](https://hypothesis.readthedocs.io/en/latest/),
[hypothesis-jsonschema](https://github.com/python-jsonschema/hypothesis-jsonschema),
[ruamel.yaml](https://yaml.dev/doc/ruamel.yaml/api/), and pytest.
A [generated example](../examples/generated-workload/test_chart_values.py) is
checked in for review. Edit assertions or rendering options in saved Python,
then use `helm hypothesis run` to execute it.

## Audit and rendering limits

```sh
helm hypothesis audit ./chart
helm hypothesis audit ./chart --strict
```

The template AST resolves direct values, root access, simple aliases, lexical
scopes, and literal lookups. It also parses nested `tpl` strings supplied as
literals, values references (including aliases and literal lookups),
`toYaml`/`toJson` of values, and `(.Files.Get "chart-relative-file")`. References
inside those strings use the supplied `tpl` context, including its `$` root, and
enter the same coalescing and property-generation process as direct references.
For example, `tpl .Values.content .` discovers `hidden` when `content` contains
`{{ .Values.hidden | default "fallback" }}`. Helm evaluates the string again for
each generated override during rendering, following its
[`tpl` semantics](https://helm.sh/docs/v3/howto/charts_tips_and_tricks/#using-the-tpl-function).

Discovery inspects template text available in the original defaults; it cannot
predict new template syntax introduced by generated string values. Dynamic string
construction, computed contexts, absent/non-string sources, and recursive `tpl`
expansion produce diagnostics. Expansion is limited to 32 nested calls. Computed
keys, named-template caller contexts, mutations, and unresolved aliases also
require review. Dependency templates and files not explicitly supplied to a
resolvable `tpl` call are not recursively audited; inspect subcharts separately.
Recursive schema paths are rejected instead of reported as covered.

Rendered YAML must contain resource envelopes with nonempty `apiVersion`, `kind`
and `metadata.name`; duplicate identities are rejected and `List` items checked
recursively. This is not Kubernetes admission or application behavior validation.
JSON null follows Helm's deletion semantics. Path coverage does not prove that
all template guards were activated or every execution branch was reached.

## Whole-chart modes

### Interaction coverage

A **configuration** is one complete set of input values. A **factor** is a field,
or a container treated as one choice, that the planner varies. Its **domain** is
the set of allowed choices. An **interaction** specifies choices for several
factors together. Pairwise coverage means every allowed pair of choices occurs
in at least one tested configuration; it does not mean every complete
configuration is tested.<sup>[\[2\]](getting-started/README.md#quick-start)</sup>

Choose the interaction strength with `--permutations`:

```sh
helm hypothesis test ./chart --permutations 2
helm hypothesis test ./chart --permutations 3 --max-cases 5000 --max-candidates 1000000
helm hypothesis test ./chart --permutations 2 --exhaustive-group ingress,service
helm hypothesis test ./chart --dry-run
```

`2` covers every schema-valid pair of factor values in at least one complete
configuration; `3` covers every valid triple. Increasing the strength increases
the coverage requirement. A strength at least as large as the number of factors
tests every distinct feasible configuration. This is a coverage requirement, not a
random-example budget. `--max-examples` does not control this mode. The default
automatic strength for larger finite spaces is `2`.

Small spaces are promoted to full enumeration even with an explicit interaction
strength. `--exhaustive-threshold 10000` is the default: **multiply the number of
choices for each factor**, including choices that constraints may later rule out.
That count must be strictly smaller than the threshold and fit `--max-cases`.
This is a conservative affordability decision,
not a count of schema-valid inputs. A heavily constrained larger space is not
automatically classified as small. Set `--exhaustive-threshold 0` to disable
promotion and retain the requested interaction strength. If the strength already
includes every factor, full enumeration is required regardless of the threshold.

#### Targeted exhaustive groups

Repeat `--exhaustive-group` to require all distinct feasible assignments within selected
groups, in addition to the global interaction coverage:

```sh
helm hypothesis test ./chart --permutations 2 \
  --exhaustive-group ingress,service,tls \
  --exhaustive-group persistence,storage
```

Selectors are dotted paths or JSON Pointer prefixes; `/a.b,/service` selects the
literal key `a.b` and the `service` container. Containers expand to their finite
factors. Each feasible group assignment appears in a full schema-valid chart
configuration, with other factors chosen to satisfy constraints. It is unnecessary
to cross every group with every unrelated setting. Unknown explicit selectors
and required coverage exceeding the planning budgets fail the command.

Automatic grouping uses local structural evidence:

1. Each schema dependency forms a group of its trigger and referenced fields.
   Conditional `if`/`then`/`else` constraints and composition expressions contribute
   the paths they mention.
2. Resolved references in one template expression form a candidate group. An
   `if`, `with` or `range` block contributes its guard and subtree references,
   including nested branches. Existing discovery resolves supported aliases and
   scopes; references sharing a source line can conservatively be grouped together.
3. The planner maps those references to finite factors and evaluates each candidate
   separately. It **does not transitively merge overlapping groups** or infer
   importance merely from similar names or shared YAML ancestry.

Inferred groups default to at most **256 candidate assignments** each; adjust
`--max-group-cases` or disable inference with `--no-infer-groups`. Oversized or
unresolved inferred groups are recorded as skipped with their reason. Explicit
groups are mandatory and are governed by the overall planning limits instead.
Overlapping groups share rendering cases where possible. Full enumeration already
covers every group, so it adds no redundant group cases.

Reports preserve group factor paths, source locations, candidate sizes and
accepted/skipped status. Dynamic includes, unresolved contexts and other discovery
limitations are logged and recorded for review. This is a heuristic for finding
useful groups, not proof that every semantically important interaction was found.

Factors come from the original values schema. Required closed objects are
expanded into nested leaf factors, so `ingress.enabled` can interact with
`service.type`. Optional objects and bounded arrays are atomic factors with all
their supported finite values; optional fields also include omission. Strings
need `enum` or `const`, integers need bounds, and objects must be closed with
`additionalProperties: false`. Unsupported or oversized factor domains fail
with a diagnostic identifying the path; this mode does not silently substitute
sampled values for an unbounded domain.

Planning validates complete configurations against the schema and checks that
their merge with chart defaults is schema-valid. Cross-field constraints on
closed object schemas restrict which interactions are feasible. An interaction
is excluded only after its possible completions have been checked. Leaf domains
retain the finite enumerator's restrictions on references and compositions.
The coverage planner reasons about valid assignments, but finite execution tests
each distinct normalized configuration only once. Overrides are normalized using
the runner's existing defaults-merge and null-deletion rules. A canonical typed
JSON identity ignores mapping order while preserving array order and scalar types.
Omission and an explicit default can therefore share one test. The baseline is
tested first and any equivalent planned assignments are removed. Deduplication
uses input values, not rendered manifests: distinct configurations remain distinct
tests even if the chart happens to produce identical resources.

The planner fills uncovered interactions deterministically without materializing
the entire Cartesian product. It does not promise a minimum-size suite, and
restrictive constraints can still require a large completion search. Two limits
bound work before Helm is invoked:

- `--max-cases` defaults to `10000`, limiting both planned configurations and each
  factor's candidate domain.
- `--max-candidates` defaults to `100000`, independently limiting the interaction
  inventory and the number of complete assignments examined during planning.

If either limit is exceeded, the command fails before rendering instead of
claiming partial coverage. Increase the limits or reduce the interaction strength.
The limits bound counts, not bytes or elapsed time.

The JSON report includes requested and effective strength, factor paths and
domains, valid interaction count, planned cases, planning candidates, and
`coverage_complete`. Coverage is complete only after every planned case passes.
`planned_cases` counts distinct additional configurations after deduplication;
`unique_configurations` and `planned_iterations` include the defaults, counted once.
Successful `attempts` therefore equals `planned_iterations`. Failures stop execution
and save the failing values and report for
replay; this deterministic mode does not shrink counterexamples.

#### Counts, timing and previous-run comparisons

Before rendering, stderr logs the selected strategy, distinct configuration count,
duplicate cases removed, total iterations, candidate assignments, coverage targets
and planning time. For example, after a 19-iteration run, a 24-iteration plan reports:

```text
Permutation comparison: 19 -> 24 iterations (+5 versus previous); all 24 iterations will run
Permutation progress: 0/24 completed, 24 remaining (0 attempted); elapsed 0.00s; estimated total 48.00s; ETA 48.00s (previous_run)
```

These durations are illustrative. The initial estimate uses measured successful
iteration timings from the previous run when execution settings match. Without
compatible history it is `unknown`; completed iterations provide a current-run
average and update the estimate. Planning duration is reported separately from
execution elapsed time and ETA. Estimates are approximate: changing chart contents,
resource counts or machine load can change iteration costs.

Progress is logged after the first iteration, approximately once per second at
iteration boundaries, and on completion or failure. JSON statistics include
`planned_iterations`, `attempted_iterations`, `completed_iterations`,
`remaining_iterations`, `unattempted_iterations`, `previous_planned_iterations`,
`iteration_delta`, `additional_iterations`, `elapsed_seconds`,
`seconds_per_iteration`, `estimated_total_seconds`, `estimated_remaining_seconds`
and `estimate_source`. `unique_configurations` is the actual number of planned tests;
`candidate_cases` includes the baseline and selected assignments before deduplication,
and `duplicate_cases_removed` explains the difference. `candidate_assignments` is
the conservative factor-domain count before cross-field constraints and effective-value
deduplication. Iterations include the defaults once. Failed or
interrupted iterations remain incomplete: remaining work includes those iterations
as well as unattempted ones.

Successful, failed and interrupted runs save `report.json` and a fresh `junit.xml`.
The JUnit testcase represents the entire finite coverage plan; iteration counts
are included as properties, and failures preserve the renderer diagnostic. A chart-specific
baseline is stored atomically under `<artifact-dir>/permutation-history/`, keyed
by the absolute chart path and shared across strengths and group selections.
Reuse the artifact directory to compare runs; changing chart paths or directories
starts a new baseline. History is diagnostic and does not reuse successful cases:
all planned iterations execute again. Concurrent runs read the last completed
baseline; the last writer supplies the next baseline.

`--dry-run` performs finite planning, logs the comparison and returns the statistics
without rendering, writing artifacts or replacing the baseline. For generated
per-path cache estimates specifically, use `--paths --dry-run`.

`--paths`, `--permutations`, `--whole-chart`, and `--exhaustive` are mutually exclusive.
Interaction suites execute serially and use the original chart schema. Like
the other whole-chart modes, they do not support per-path filtering, collection,
per-path cache estimates, or distributed sharding. `--seed` does not change the
deterministic coverage plan. Use `--shard none` when CI would otherwise enable
automatic sharding. Kubernetes validation and manifest streaming remain available.
Complete interaction coverage does not prove template branch coverage or correct
application behavior.

### Sampling and full enumeration

```sh
helm hypothesis test ./chart --whole-chart --max-examples 100 --seed 42
helm hypothesis test examples/workload --exhaustive --max-cases 1000
```

These explicit modes retain the earlier whole-chart runner against the original
schema. Sampling tests complete override objects; exhaustive mode enumerates
supported finite domains and refuses oversized or unsupported domains. They do
not generate a per-path suite and do not accept `--match` or `--collect-only`.
Failures save `values.json` and `report.json` for replay:

```sh
helm template hypothesis ./chart --values reports/hypothesis-helm/values.json
```

Sampling is evidence from tested inputs, not a proof of totality. Exhaustive
coverage is limited to the declared finite input domain and rendering environment.

## Examples and Astrivant

```sh
helm hypothesis test examples/workload
helm hypothesis test examples/configmap
helm hypothesis test examples/broken
helm hypothesis test examples/hidden-levers
helm hypothesis test ../astrivant/helm/astrivant --collect-only \
  --artifact-dir reports/astrivant
helm hypothesis run reports/astrivant --match networkPolicy
```

The broken chart intentionally fails on `replicas: 0`. The hidden-lever chart
exercises recovered template fallbacks. Astrivant has incomplete schema entries
and dynamic references; its generated tests may expose real chart failures.

## Stream rendered manifests

Use `helm hypothesis test ./chart --output json` (or `-o json`) to emit
newline-delimited JSON: one compact Kubernetes resource per line, flushed as
each render reaches coordinator verification. Parallel exhaustive runs preserve seeded order and emit complete records from one coordinator.
The same flag works with `helm hypothesis run
reports/hypothesis-helm`, `--whole-chart`, and `--exhaustive`. Progress,
pytest output, reports, and errors go to stderr; stdout contains only manifests.
Collection-only runs emit no manifests.

Every rendered example is included, including repeated examples during shrinking.
Documents are emitted before resource-envelope checks, so a JSON-serializable
resource that fails those checks still reaches the validator. Failed Helm
invocations and unparseable YAML cannot produce JSON manifests. Empty renders
emit no lines. This is a JSON Lines stream, not one JSON array.

To validate each manifest with both tools as it arrives, use this Bash pipeline.
Each validator receives the original resource separately, and either failure
makes the pipeline fail:

```bash
set -o pipefail
helm hypothesis test ./chart --filter -o json |
  (
    status=0
    while IFS= read -r manifest; do
      printf '%s\n' "$manifest" | kubeconform -strict || status=1
      printf '%s\n' "$manifest" | kubesec scan /dev/stdin || status=1
    done
    exit "$status"
  )
```

The per-line loop avoids requiring validators to understand JSON Lines.
[Kubeconform](https://github.com/yannh/kubeconform) validates Kubernetes resource
schemas; [Kubesec](https://github.com/controlplaneio/kubesec) analyzes security
configuration. Their exit statuses determine pipeline success; external validator
findings are not fed back into Hypothesis for shrinking or recorded as pytest
assertions. Configure any score threshold separately from Kubesec's scan exit
status. In `generate`, `--output` continues to specify the suite directory.

## Adaptive parallel test execution

`helm hypothesis test` and `helm hypothesis run` default to `--jobs auto`.
Auto mode starts with the available logical CPU count and uses PID feedback
to adjust active worker concurrency as individual tests finish. Its ceiling is
four times the available CPU count, capped by the number of selected tests.
Use `--jobs N` / `-j N` for fixed concurrency, or `--jobs 1` for serial execution:

```sh
helm hypothesis test ./chart
helm hypothesis test ./chart --jobs auto -o json
helm hypothesis run reports/hypothesis-helm --jobs 4
helm hypothesis run reports/hypothesis-helm -j 1
```

The controller measures completed tests per second, including interpreter startup,
rendering, shrinking, and manifest-output backpressure. Each completion updates
the measurement window. To reduce timing noise, control adjustments wait for at
least one target-sized group of completions (minimum two) and 100 milliseconds.
Startup, concurrency drain, and the final partially occupied queue do not count
as evidence that higher concurrency reduces throughput.

Since the maximum throughput is unknown, the controller probes nearby concurrency
levels and estimates the marginal throughput change per worker. A PID controller
uses that gradient to approach zero marginal gain, with a filtered derivative,
integral anti-windup, and a one-worker adjustment limit per measurement window.
Periodic probes allow further exploration; flat throughput favors fewer workers.
This seeks a local throughput maximum within the bounds, rather than guaranteeing
an optimum for heterogeneous tests or changing host load. Short suites may finish
before enough measurements exist to adjust concurrency.

A thread pool dispatches one selected property at a time into an isolated pytest
interpreter. Lowering concurrency lets active tests finish before replacing them;
it never cancels a property's Hypothesis generation or shrinking.
[Pytest is not generally thread-safe](https://docs.pytest.org/en/stable/explanation/flaky.html#thread-safety),
so pytest state stays isolated. With concurrent execution, module and session
fixtures run separately for each property. Interpreter and fixture startup costs
can dominate very small tests; `--jobs 1` uses a single pytest invocation.

Workers preserve live path logs and JSON manifest streaming. Manifest order
depends on scheduling; writes are synchronized so even large JSON lines remain
intact. Results are merged into `junit.xml`. `report.json` records the jobs mode,
peak scheduled worker count, and aggregate exit status. `concurrency.json`
records each completed test, elapsed time, exit code, active count, target count,
and latest measured throughput. Target changes also appear in progress logs.
Any failed worker fails the command.

Collection-only runs stay serial. Explicit `--exhaustive` supports concurrent
Helm processes with `--jobs N`; `auto` uses the available CPU count.
Other whole-chart modes remain serial and reject numeric `--jobs` values above one.
The pre-commit hook inherits `--jobs auto` without configuration changes.

## Progress and interruption

A Rich progress bar shows completed/selected tests, the worker target, and elapsed
time on stderr. It updates after each property finishes; redirected output keeps
a final summary without terminal animations. Pass `--progress` to `test` or `run`
to force a live bar on stderr even when redirected (this includes terminal escape
sequences). `--dry-run` and `--collect-only` do not display an execution bar. Serial runs show the same progress
through the bundled pytest plugin. Collection-only runs do not show a test bar.

Press Ctrl-C to stop submitting tests and interrupt active pytest process groups,
including their Helm children. Workers receive two seconds to finish cleanup,
followed by SIGTERM and a further one-second grace period before SIGKILL. The
command exits with status 130. Generated-suite runs retain the partial JUnit and
run reports; unfinished parallel tests are marked skipped, and concurrency
history records the interruption. The bar keeps its partial completion count.
JSON stdout remains reserved for manifests emitted before shutdown.

## Distributed sharding

Both `test` and `run` default to `--shard auto`, detecting CI node coordinates.
Use `--shard none` to disable detection or `--shard INDEX/TOTAL` to choose a
one-based partition explicitly. See [CI integration](ci.md) for provider mappings
and the GitHub Action.
Each independently launched instance executes only its assigned properties,
with its own fixed or PID-controlled worker pool:

```sh
# Separate runners, using the same chart revision and command options:
helm hypothesis test ./chart --shard 1/3 --jobs auto --seed 42
helm hypothesis test ./chart --shard 2/3 --jobs auto --seed 42
helm hypothesis test ./chart --shard 3/3 --jobs auto --seed 42

# Inspect one partition without rendering:
helm hypothesis test ./chart --shard 1/3 --match image --collect-only

# Partition an existing suite, with reports in a separate location:
helm hypothesis run generated-tests --shard 1/3 --artifact-dir reports/distributed
```

The partition algorithm (`sha256-nodeid-v1`) hashes the UTF-8 pytest node ID
relative to the suite root, then takes the result modulo TOTAL. It is independent
of absolute checkout location, Python hash randomization, collection order, and
worker scheduling. It runs after keyword selection. Different totals repartition
the suite; identical totals and node IDs preserve ownership when unrelated tests
are added. Hash partitioning does not promise equal counts or equal execution
time, and a long property is not split across shards.

Run every index from 1 through TOTAL using the same chart/suite revision, plugin
version, `--match`, generation options, and seed. Each property then belongs to
exactly one instance, without a coordinator or shared queue. Repeating a shard
intentionally repeats its properties; no distributed deduplication service is
involved. A partition with no assigned properties succeeds with zero workers.
An empty overall selection, including a mistyped `--match`, still exits with
pytest's no-tests status (5). Sharding is unavailable in the explicit
`--whole-chart` and `--exhaustive` modes.

`test` writes its generated suite and reports beneath
`ARTIFACT_DIR/shards/INDEX-of-TOTAL/`. `run` reads the saved suite in place and
writes reports beneath `SUITE/shards/INDEX-of-TOTAL/`, or under the supplied
`--artifact-dir`. Each directory includes `shard.json` with the algorithm,
matched count, assigned count, and exact node IDs, plus the usual JUnit and run
reports and, when workers execute, concurrency history. Distinct shards do not
overwrite one another's artifacts. Do not run the same shard twice concurrently
against the same artifact directory.

Progress bars, stdout manifest streams, exit statuses, and Ctrl-C shutdown are
local to each instance. Keep each shard's JSON stream separate; independent
instances do not share the manifest-write lock. Collect the shard JUnit files in
CI and require every instance to succeed. Cancelling one instance does not stop
the others; the CI orchestrator controls cancellation across runners.

Auto concurrency uses each instance's available CPU count. Separate machines or
CPU-limited containers provide independent resource budgets. On a shared host,
set `--jobs N` per instance to avoid multiplying the automatic CPU budget.
Custom fixtures must also avoid mutating shared files or external resources.

## Values structure baselines

Cached test runs store the original `values.yaml` tree as canonical JSON encoded
in base64 at `<cache-dir>/<sha256(seed)>/structures/<source-key>.b64`. Mapping
keys, container kinds, array lengths, and indices remain; scalar contents and
scalar types become `null`. Mapping order is ignored. Custom saved suites without
source metadata use `values.coalesced.yaml` instead.

The source key hashes the values-file path relative to the generated suite.
Keep that relative layout and seed consistent between branches and runners; the
absolute checkout directory can differ. Use distinct cache roots for unrelated
projects. The marker survives changes to the full test-result fingerprint, so
`report.json` and `--dry-run` can report `new`, `unchanged`, `changed`, or
`invalid-cache`, with `added_paths` and `removed_paths`. Container-kind changes can
report `changed` even when the named paths remain identical. A missing or invalid
baseline treats current paths as added. Scalar changes still invalidate test
outcomes through the full fingerprint.

For PR/MR jobs, restore the main branch's cache into the same `--cache-dir`, then:

```sh
helm hypothesis test ./chart --seed 0 \
  --cache-dir .cache/hypothesis-helm/results \
  --disable-schema-caching
```

`--disable-schema-caching` reads and compares the baseline but never replaces it,
even if tests fail. It does not select a branch or retrieve a remote cache; configure
CI to restore the main branch's cache and reserve publication of that baseline for
main-branch jobs. Result outcomes can still be written, so PR/MR jobs must not save
their entire cache over the main branch's cache. The GitHub Action accepts
`disable-schema-caching: 'true'` and `cache-dir` for this workflow.

Without the flag, completed or interrupted test runs save their starting structure.
Collection errors leave the baseline intact. `--dry-run` and `--collect-only` never
update it; `--no-cache` disables both marker reads and writes. The flag does not
change kubeconform schema downloads or `--schema-cache-dir`.

## Persistent path results

Result entries use `<cache-dir>/<sha256(seed)>/<suite-fingerprint>.json`. The seed
key is the SHA-256 hex digest of the seed's UTF-8 decimal representation; `--seed 0`
uses `5feceb66ffc86f38d952786c6d696c79c2dbc239dd4e91b46729d73a27fb57e9`.
The inner fingerprint retains chart, schema, implementation, and selection checks,
so changing inputs cannot reuse a stale success just because the seed is unchanged.
Execution and `--dry-run` use the same layout. Older flat cache entries are left
untouched and treated as cold; the next execution writes the new layout.

`helm hypothesis test` and `helm hypothesis run` cache completed path outcomes under
`<artifact-dir>/cache/` (inside the shard directory when sharding). With a valid
cache, local runs retry failed, skipped, and incomplete paths; previously passing
paths are deselected. If every selected path already passed, the command succeeds
without rendering new manifests. First runs and changed inputs run the full selection.
`--collect-only` lists the full selection and leaves the result cache unchanged.

Expect an initial run to take substantially longer than a cached local retry: it
traverses the schema and discovered values-path tree, generates the suite, and
executes every selected property with its rendering and validation work. An empty
schema cache adds the initial fetch and sparse checkout. Path discovery and suite
generation still occur on subsequent `test` invocations; cached successes save
property execution time. Filters and shards reduce the executed selection, while
CI defaults and `--rerun all` continue to execute it in full. This path traversal
is not exhaustive testing of every distinct configuration.

```bash
helm hypothesis test ./chart                         # local failed-path rerun
helm hypothesis test ./chart --rerun all             # force every selected path
helm hypothesis test ./chart --cache-dir .cache/helm # choose a persistent cache
helm hypothesis test ./chart --no-cache              # neither read nor write results
CI=true helm hypothesis test ./chart --rerun failed  # explicitly retry in CI
```

`--rerun auto` is the default. CI runs execute every selected path while recording
results. `$CI` is case-insensitive: empty, `0`, `false`, `no`, and `off` mean local;
other nonempty values mean CI. If `$CI` is absent, provider markers for GitHub Actions,
GitLab CI, CircleCI, Azure Pipelines, Jenkins, and Buildkite provide fallback detection.
An explicit `$CI` takes precedence for retry defaults. Progress bars stay disabled when
any provider marker is enabled, even with `CI=false`.

Cache keys include the suite source, coalesced values, schema, original chart files
(including dependencies), framework source, Python version, seed, keyword selection,
and shard. Changes invalidate prior results. Shards have independent cache entries;
thread workers record separate outcome files, which the parent merges atomically.
Interrupted runs retain completed results; incomplete paths remain eligible for retry.
Malformed cache files are treated as cold caches. Cache entries record pytest node IDs
and outcomes, not rendered manifests or Hypothesis examples. Use `--rerun all` after
changing external tools or environment-dependent behavior, or to resample passing paths.

## Kubernetes API conformity

Enable strict [kubeconform](https://github.com/yannh/kubeconform) validation for each
rendered YAML stream. Install Git and kubeconform first (`brew install git kubeconform`
on macOS), then use the Helm command:

```bash
helm hypothesis test ./chart --kubeconform
helm hypothesis test ./chart --kubeconform --schema-version 1.35.0
helm hypothesis run ./generated-tests --kubeconform --schema-version 1.35.0
```

`--schema-version latest` is the default: it selects the highest stable `X.Y.Z`
version published in [Kubernetes JSON Schema](https://github.com/yannh/kubernetes-json-schema),
not Kubernetes development HEAD. Pin an exact version for reproducible CI runs.
`--kube-version` remains the separate Helm capabilities option; set both options to
the same version when testing a specific cluster target.

The tool fetches Git metadata with `--depth=1 --filter=blob:none` and sparsely checks
out only the selected `vX.Y.Z-standalone-strict` directory. The cache defaults to
`.cache/hypothesis-helm/schemas`; override it with `--schema-cache-dir PATH`. A file
lock serializes checkout updates, and immutable snapshots let threads and shards
validate against the same schema content even while another run updates the checkout.
Online runs refresh the catalog. To use only previously downloaded schemas:

```bash
helm hypothesis test ./chart --kubeconform --schema-version 1.35.0 \
  --schema-cache-dir .cache/hypothesis-helm/schemas --schema-offline
```

Offline mode fails clearly if the requested schemas are absent. Restore/save the
entire schema cache directory in CI, including its Git metadata. This cache is
separate from path-result caching; `--no-cache` disables cached test outcomes, while
schema caching remains active. `--collect-only` does not fetch schemas or run the validator.

Validation uses local schema files, strict mode, and one kubeconform worker per
property worker to avoid nested concurrency. Invalid resources, unsupported API
versions, and missing schemas fail the property and participate in Hypothesis shrinking.
Custom resources require schemas beyond the upstream Kubernetes catalog and currently
fail as missing schemas. This checks API structure, not admission policies or live
cluster behavior. Manifests still stream through `--output json` before validation,
including failing examples. Use `--kubeconform-binary PATH` for a specific executable.

Path-result cache keys include the schema content identity, resolved Kubernetes
version, and validator binary digest. Enabling validation or changing any of these
requires a fresh property run. Use `--rerun all` to validate fresh manifests again
when an unchanged local suite previously passed.


### Preparing schemas independently

`helm hypothesis schemas --schema-version latest --schema-cache-dir
.cache/hypothesis-helm/schemas` fetches the remote catalog, sparsely checks out the
selected strict schema version, and prints the resolved configuration as JSON.
Use it before a CI cache-save step when schema downloads must survive a later
failing test. It accepts `--schema-offline` and `--kubeconform-binary` as well.

### Timing estimates

The progress bar's ETA uses measured property completion rates and stays unknown
until enough observations exist. JUnit durations measure individual properties,
including generation, rendering, validation, and shrinking. Neither is a reliable
prediction based solely on schema types: input rejection, branch-dependent output,
shrinking, and changing parallelism affect elapsed time. The ETA excludes schema
preparation and collection, which happen before the progress bar starts.

## Cache-aware dry runs

Preview work without executing property examples, rendering charts, validating
manifests, or downloading schemas:

```bash
helm hypothesis test ./chart --paths --dry-run
helm hypothesis test ./chart --paths --dry-run --rerun all --kubeconform \
  --schema-version latest --schema-cache-dir .cache/hypothesis-helm/schemas
helm hypothesis run generated-tests --dry-run --match replicas
```

The command emits a JSON plan to stdout (`-o json` also works). It applies the
same keyword filter, shard, seed, cache fingerprint, and local/CI rerun policy as
execution. `selected_properties` counts properties after filtering and sharding;
`scheduled_properties` counts those that need to run; `reused_properties` counts
cached successes omitted by the rerun policy. Each property includes its prior
outcome, planned action, and literal `max_examples` setting when known.

`successful_example_budget` sums those settings for scheduled properties. It is
not an exact render count or an exhaustive count of the value domain: Hypothesis
may stop early or do additional work for rejection, replay, and shrinking. If a
hand-edited test has an unknown budget, the aggregate is `null`. All cached
successes produce zero scheduled properties and a zero budget locally; CI or
`--rerun all` still schedules the full selected suite. Cache files do not contain
reliable timing histories, so `estimated_seconds` remains `null` when work exists.

With `--kubeconform`, the dry run inspects locally available schemas using offline
preparation. Missing schemas or a missing validator are reported without downloading
anything, and cached successes are not reused when validation identity cannot be
established. An online execution can refresh schema content and invalidate the
estimated cache hit; `schema_cache.note` makes this uncertainty explicit. Use
`--schema-offline` to plan against the cached schema snapshot alone.

Chart tests are generated in temporary storage at their intended logical location,
so their fingerprint matches a real run. Existing generated files, reports, and
result caches are preserved. Pytest collection imports suite modules and conftest
files, so custom import-time side effects still apply. Use `--paths --dry-run`
for these per-path cache estimates; automatic finite plans have their own
[iteration statistics](#counts-timing-and-previous-run-comparisons).
Dry runs cannot combine with `--collect-only`, `--whole-chart`, or `--exhaustive`.

## Strict source values

`--strict` requires every configurable path declared by the schema or resolved from
templates to be explicitly present in the chart's original `values.yaml`. Optional
schema fields count too, even if no template currently references them. A schema
`default`, Helm `default`/`dig` fallback, or value inserted into the in-memory
coalesced document does not satisfy this requirement.

```sh
helm hypothesis audit ./chart --strict
helm hypothesis test ./chart --strict
helm hypothesis generate ./chart --strict --output generated-tests
helm hypothesis run generated-tests --strict
```

Missing fields produce `no-default` findings with their paths and available template
locations. Strict commands exit with status 1 before generation, rendering, or schema
downloads when the audit has findings or unresolved accesses. Existing checks for
undocumented or untyped fields and missing descriptions still apply. A cached passing
test result cannot bypass this preflight, including during `--dry-run`.

Presence is checked by key, so an explicit `null` leaf is present; it must still
satisfy the schema and render successfully when tested. A null parent does not
supply nested keys. Named fields inside arrays or dynamic maps must appear in every
entry. Empty collections are acceptable for scalar item values, but cannot demonstrate
nested named fields: strict mode requires representative entries containing those
fields. Fixed array positions must exist as well.

Saved suites use `chart-source.json` to audit their original chart rather than the
coalesced snapshot. Regenerate older suites without this metadata before using
`run --strict`. Strict checks never modify the source `values.yaml`.

### In-memory rendered-output comparison

Each render is hashed with SHA-256 over the complete parsed manifest bundle.
Canonical mapping keys ignore YAML formatting, comments and key order; resource
order, array order, scalar types and resource contents remain significant.
Digest-set membership is average O(1); parsing and hashing still process the output.
Memory grows with the number of distinct output and validation-context digests.

Repeated output reuses successful resource-envelope and kubeconform validation
under the same validation configuration. Failed validation is never cached.
Helm still runs for every selected input, manifest streaming is preserved, and
custom assertions and the empty-output policy still execute for every input.
This output cache is separate from distinct-input planning and does not change
permutation coverage or its iteration count.

`report.json` includes `render_hashes` counters for observed, unique and duplicate
bundles and successful validation cache hits. Whole-chart checks start a fresh
run-local index. Generated pytest suites use a process-local index reset each
session. Parallel workers report summed local counts: `worker_unique_bundles`
is not global uniqueness, so `global_unique_bundles` is null. Interrupted workers
that cannot finish may not export counters. Only counters are written; hashes
remain in memory.

Independent CI jobs do not share this index. Processes on one host could use a
shared service or multiprocessing manager; cross-job reuse needs an accessible
external store. A future shared cache must identify the validator and schema as
well as the render, and publish success only after validation completes.

### Shared typed values model

Permutation analysis compiles the supplied schema into a `ValuesModel`. Declared
objects become dynamic attrs classes; scalar and array annotations come from
schema types or explicit enum/const domains. Each attrs field carries its original
values key and a shared `ValueNode` containing the schema, path and requiredness.
The model exists independently of which optional fields appear in `values.yaml`.

Factor extraction, schema relationship analysis and template group resolution
reference these same nodes. The planner assigns finite choices into typed attrs
instances and uses the model's cattrs converter to restore values mappings for
JSON Schema validation and Helm. No model metadata enters the rendered values.

```python
from hypothesis_helm import Chart
from hypothesis_helm.schemas.model import ValuesModel

chart = Chart.load("./chart")
model = ValuesModel.from_schema(chart.schema)
values = model.structure(chart.defaults)
service = model.reference(("service",)).target
assert model.unstructure(values) == chart.defaults
```

Conversion preserves explicit null, omission, arrays, extra values and original
keys, including keys requiring Python attribute aliases. Schema defaults are not
inserted and scalars are not coerced. `structure(..., validate=False)` is reserved
for partial candidates; normal conversion validates against the full schema.
Untyped or opaque schema fragments remain lossless raw values, with their
constraints enforced by JSON Schema. This does not broaden the supported finite
domains or turn type declarations into evidence of cross-field interaction:
template guards and schema constraints still supply that evidence. Unresolved
references and inference limits retain their existing diagnostics.

### Exact-equivalence pruning

`--prune-equivalent` enables conservative pre-render pruning for whole-chart
candidates. It skips Helm only when the proof compiler establishes the same
output as an earlier successful render. Schema validation and custom assertions
still run per candidate; unsupported behavior falls back to Helm.

```sh
helm hypothesis test ./chart --permutations 2 --prune-equivalent
```

Reports distinguish candidate checks, actual renders and equivalence certificates.
See the [compiler stages, soundness contract and limitations](safe-pruning.md)
before extending the supported template language or introducing another metric.

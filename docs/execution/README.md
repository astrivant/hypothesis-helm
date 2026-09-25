# Execution and estimates

<!-- toc:start -->
**Table of contents**

- [Value-path traversal](#value-path-traversal)
  - [Sensitivity-guided permutation traversal](#sensitivity-guided-permutation-traversal)
- [Parallel execution](#parallel-execution)
  - [Input memory](#input-memory)
  - [Runtime estimates](#runtime-estimates)
- [Distributed sharding](#distributed-sharding)
- [One final report](#one-final-report)
- [Progressive dry runs](#progressive-dry-runs)
  - [Shutdown and partial results](#shutdown-and-partial-results)
- [Optional filtering](#optional-filtering)
  - [Expanding observed failures](#expanding-observed-failures)
- [Percentage sampling](#percentage-sampling)
  - [Adaptive preset](#adaptive-preset)
  - [Parallel exhaustive execution](#parallel-exhaustive-execution)
<!-- toc:end -->

[Documentation](../README.md) · [Project](../../README.md)

Random text generation excludes tabs and other C0/C1 control characters, such as
`\u001f`, that are generally not useful chart inputs. Newlines and carriage returns
remain allowed for multiline configuration, as does other Unicode text. The same
rules apply inside nested values and generated object keys.
This applies to whole-chart sampling and newly generated per-path suites; regenerate
saved suites to update their strategies. Explicit finite domains and chart defaults
are unchanged. If a schema requires only excluded strings, sampling cannot satisfy
that schema, and reports the empty or unsatisfiable sample as unsuccessful.

## Value-path traversal

`run`, `test`, and `scan` default to `--traversal-strategy random`. Discovery builds
the path inventory, filtering selects the work, and traversal orders it for execution.
Each selected path is scheduled once per invocation. Its **property test** can try
many values and, on failure, simplify the input to a smaller reproducing example
(called **shrinking**). A timeout leaves the unvisited paths explicitly untested.<sup>[\[1\]](../architecture/README.md#execution-and-validation)</sup>

| Strategy | Execution order |
| --- | --- |
| `random` | Random order, reproducible with the same seed and selected paths. |
| `linear` | Original path order. Scans follow supplied values before additional discovered paths. |
| `root-first` | Increasing path depth: `.global` before `.global.configMaps`. |
| `leaf-first` | Decreasing path depth: deepest leaves before their parent containers. |
| `sensitivity-first` | Finite permutation tests: measure retained references, then prioritize larger and more numerous interactions. |

```sh
helm hypothesis test ./charts --filter --seed 42 --traversal-strategy random --chart-timeout 3m
helm hypothesis run generated-tests --traversal-strategy leaf-first --seed 42
```

The previous names `shallow` and `deep` are no longer accepted. Update existing
commands to `root-first` and `leaf-first`, respectively.

The same seed and selected paths reproduce the execution order. Change the seed
to test a different selection of paths before a timeout; some paths may appear in
both runs. Assigning paths to shards or skipping cached successes does not reorder
the remaining paths. Root-first and leaf-first traversal finish all paths at one depth
before starting the next depth within each shard. Independent CI shards do not
wait for one another. Paths at the same depth keep their original order.

Finite permutation runs order distinct configurations after filtering, with defaults
checked first. Fields necessarily recur across joint configurations. In these modes,
root-first uses the shallowest changed field and leaf-first the deepest, relative to defaults.
A render can be skipped as equivalent only after another input has passed validation
and the compiler has established that both inputs produce exactly the same output.

Ordering costs O(P) for linear traversal and O(P log P) for random and depth-based strategies,
with O(P) storage, excluding path encoding and finite-case comparisons. P counts
the paths or configurations selected for execution. Changing traversal strategy
changes their order; it does not add or remove tests. Testing every path does not
test every possible value or every interaction between paths.

Scan reports retain the seed, strategy, visited order, completed and incomplete path
counts, and remaining order. `path-inventory.json` records the planned sequence.
Per-path dry runs list the same ordered properties without executing them.

### Sensitivity-guided permutation traversal

Use `sensitivity-first` when you want measured interactions to determine which retained configurations run first:

```sh
helm hypothesis test ./chart --traversal-strategy sensitivity-first --seed 42
helm hypothesis test ./chart --permutations 3 --traversal-strategy sensitivity-first --sensitivity-order 2 --seed 42
```

The first command uses the default pairwise coverage (`--permutations 2`). In the second, tests cover triples,
while sensitivity analysis considers individual changes and pairs. `--sensitivity-order N`
sets the maximum number of changed paths in an analyzed group, independently of coverage. It must be between 1 and
`--permutations`; the default is the smaller of 2 and the requested permutation strength. Increasing it never authorizes
analysis above the interaction order selected for bug testing.

Sensitivity ordering still needs a finite input domain. Recursive `test` and remote `scan`
use seeded random path testing for charts whose domains cannot be enumerated. They log this fallback and record its
reason and effective traversal in the chart report, including when `--permutations N` is explicit. Those generated path tests
do not guarantee the requested N-way coverage. Saved suites and explicit `--paths`, `--whole-chart`, and `--exhaustive` modes cannot use
`sensitivity-first`.

Filtering and sampling select the configurations first. The scheduler then finds baseline-relative groups whose reference
configurations survived selection. Measuring a pair requires the baseline, each change separately, and both changes together.
Larger groups similarly require every subset of their changes. Missing references remain unknown; the scheduler does not
restore filtered cases to fill these gaps.

Reference configurations run first as ordinary bug tests, within the chart's execution deadline. Their successful manifest
outputs supply the measurements, and those configurations are not tested again during the remaining traversal. A failure
during this phase is a normal test failure; failure expansion still follows the configured policy.

Remaining configurations are prioritized by:

1. The largest measured interacting group among their changed paths.
2. The number of distinct measured interactions among those paths. More interactions rank higher.
3. The magnitude of those interactions, then individual output changes.
4. The existing seeded order for ties or configurations without measured effects.

An interaction is a nonzero mixed finite difference of the manifest path/value indicators used by the
[sensitivity study](<../../studies/sensitivity/README.md>). It measures how joint changes differ from the separate changes.
Different tested values for the same group of paths count as one interaction; the largest observed magnitude is retained.
These measurements describe the tested baseline and values. They neither prove that an unmeasured region is harmless nor
guarantee earlier bug discovery. The report's `sensitivity` object includes path scores and missing-reference counts.

This strategy is available for finite `test` and `scan` runs with explicit `--permutations`, including recursive chart discovery.
It does not apply to saved per-path suites, unbounded domains, or `--exhaustive`. A dry run describes the requested bound;
it cannot produce measured priorities without executing tests. Finite interaction execution remains serial.

For G candidate groups of at most K paths, checking their reference sets takes up to O(G × 2^K) subset visits, plus mutation
encoding. Computing their finite differences takes O(G × 2^K × F) work when each output has at most F manifest features.
Ranking P remaining cases against I measured interactions takes O(P × I × K + P log P), excluding input comparison costs.
Profiling adds no test configurations, but may front-load a large fraction of the retained tests; a timeout can occur before
the ranked remainder starts. Feature storage scales with the number of retained reference outputs, rather than every output
in the full plan. Measurement evidence is local to the invocation; no cross-run sensitivity cache is used.

## Parallel execution

Repository tests process one chart at a time. With `--jobs 6`, six Python workers
share that chart's ordered queue of value paths. Each path is claimed once and
receives up to **10 generated examples** by default (`--max-examples` overrides this).
Workers share one `--chart-timeout` deadline. They stop and are joined before the next chart starts. Dependency
preparation happens before testing and is excluded from this budget.
The deadline includes input generation, even when satisfying schema constraints takes time before Helm can render.
A path interrupted during generation is incomplete; it is neither a passed test nor a chart defect.

`--jobs auto` uses the available CPU count for this repository path queue. Results
record completed and interrupted paths separately; workers write isolated records
which the coordinator merges into the chart report. A fixed seed reproduces the
queue order, but timing and worker scheduling can change where a timed run stops.
Render-hash caches remain local to each property; this queue does not introduce a
shared writable render cache. Finite interaction execution remains serial.

The generated pytest suite uses a separate scheduler:

Each worker runs a generated test for one values path. That test may try many
inputs, independently of tests for other paths, so several workers can run at once.

1. **Collect and dispatch:** Pytest identifies the selected properties. A thread
   pool dispatches each queued property into a separate pytest process, isolating
   fixtures, Hypothesis state, and temporary chart files. Input generation and
   counterexample shrinking remain sequential within each property.
2. **Measure and adjust:** With `--jobs auto`, the scheduler measures how many tests
   finish per second. A feedback controller adjusts the number of active workers
   based on those measurements, starting at the available CPU count and probing up to four
   times that count, bounded by the number of selected tests. Measurement windows
   smooth timing noise; reducing concurrency lets active tests finish.
3. **Aggregate results:** The parent merges JUnit results and exit statuses, while
   synchronized manifest writes keep each JSON record intact. Completion order
   can vary without changing how individual properties are evaluated.

Custom tests must preserve this independence: shared mutable files or external
resources can introduce interference. Process and fixture startup add overhead,
so small suites may benefit less from parallelism. Automatic tuning seeks higher
throughput by probing nearby concurrency levels within its bounds. Use
`--jobs N` for fixed concurrency or `--jobs 1` for serial execution. The explicit
whole-chart sampling and finite interaction modes remain serial. Explicit `--exhaustive --jobs N` runs up to N Helm processes concurrently.

### Input memory

Finite plans store assignment IDs and reconstruct values when needed. Filtering and
traversal retain selected positions and reconstruct configurations on demand. Planning
still validates candidate inputs before claiming coverage; replay trades some repeated
construction work for lower memory use. The seed, case order and coverage rules are unchanged.

Benchmark workers receive compact ranges of input IDs. Custom JSONL workloads retain byte
offsets and hashes, read one record at a time, and reject records changed after validation.
Neither approach requires loading all input documents into each worker's memory.

Memory still grows with the discovered paths, selected IDs, deduplication hashes and
interaction-coverage bookkeeping. Reports retain bounded factor domains and observed results;
PCA retains the numerical data needed for its calculation. This reduces input storage without
claiming constant memory for the entire run.

### Runtime estimates

This section describes generated property suites. Recursive repository tests can also
reuse entire completed charts after [Git and content verification](../scanning/README.md#incremental-repository-tests).

**Expect the first execution to take substantially longer than a cached local
rerun.** The tool traverses the complete schema and discovered values-path tree to
generate properties, then executes every selected property because no successful
results are cached yet. Without filters or sharding, that means the full generated
suite, with repeated Helm renders and optional API schema validation for each
property's examples. A cold schema cache also requires the initial Git fetch and
sparse checkout.

Later `test` invocations still discover paths and generate the suite; the main
saving comes from skipping compatible cached successes. CI defaults, `--rerun all`,
and changes that invalidate the cache execute the full selection again. Traversing
all paths does not mean exhaustively testing every distinct configuration.

Use `--dry-run` to estimate work from the current cache before executing tests:

```sh
helm hypothesis test examples/workload --match replicas --max-examples 6 \
  --seed 0 --shard none --dry-run
```

Example output for a local run with a cold cache (paths and explanatory notes
omitted):

```json
{
  "status": "dry-run",
  "cache_hit": false,
  "rerun": "failed",
  "selected_properties": 1,
  "scheduled_properties": 1,
  "reused_properties": 0,
  "successful_example_budget": 6,
  "worker_limit": 1,
  "properties": [
    {
      "test": "test_chart_values.py::test_replicas_fc55c2d623",
      "cached_outcome": null,
      "action": "run",
      "max_examples": 6
    }
  ],
  "estimated_seconds": null
}
```

`estimated_seconds: null` means there is no reliable duration estimate before
execution. After a compatible passing run, the local plan instead reports
`cache_hit: true`, `scheduled_properties: 0`, `reused_properties: 1`, and
`successful_example_budget: 0`; the property's action becomes `reuse`.

Each cached run also records a base64-encoded values structure, retaining keys and
array positions while replacing scalar leaves with `null`. Reports and `--dry-run`
expose `values_structure` with the comparison status and added or removed paths.
Scalar changes still invalidate cached test results independently of this marker.

For PR/MR comparisons, restore the main branch's path cache and pass
`--disable-schema-caching --cache-dir .cache/hypothesis-helm/results`. This reads
its structure baseline without replacing it; only main-branch jobs should publish
updates to that shared baseline. The GitHub Action exposes the same option as
`disable-schema-caching: 'true'`. This flag controls the values structure marker;
Downloaded Kubernetes schemas retain their existing cache behavior.
See [structure baselines](../usage.md#values-structure-baselines) for cache layout
and CI requirements.

Result caches are grouped under `<cache-dir>/<sha256(seed)>/`, with a separate
suite fingerprint per entry. `--dry-run` looks up the same seed-specific entries
as execution.

The JSON plan lists selected, scheduled, and reused properties, plus the total
successful-example budget. With a cold cache, this selection schedules one
property with a budget of six. With a compatible cached success, a local rerun
schedules zero; `--rerun all` or CI defaults schedule it again. Match the original
run's artifact directory, validation options, seed, and budget when inspecting its
cache. `--validate-schemas` also reports schema-cache availability without fetching
schemas; an online refresh may change the predicted result-cache hit. See
[cache-aware dry runs](../usage.md#cache-aware-dry-runs) for details.


`helm hypothesis test ./chart --progress` explicitly enables a live progress bar
on stderr, including when output is redirected. It also works with
`helm hypothesis run`; JSON manifests remain on stdout.

The progress bar shows a live ETA based on completed properties. It starts unknown
and updates as measurements arrive; JUnit reports record each property's duration.
Schema types alone cannot predict runtime: Helm branches and resource counts,
Hypothesis input rejection and shrinking, and runner contention all affect cost.
`--max-examples` sets the sampling budget; rejection, replay and shrinking affect
the actual render count. Treat the ETA as a
rough estimate, particularly while automatic worker concurrency changes or a failing
property is shrinking. The ETA remains unknown until execution provides timings.

## Distributed sharding

Use `--shard INDEX/TOTAL` to split a suite across independent instances. Each
shard retains its own `--jobs auto` controller and worker pool, providing
parallelism both across runners and within each runner. For example, launch
these commands on three separate runners:

```sh
helm hypothesis test ./chart --shard 1/3 --jobs auto
helm hypothesis test ./chart --shard 2/3 --jobs auto
helm hypothesis test ./chart --shard 3/3 --jobs auto
```

Shards use a stable hash of each property identifier, after `--match` filtering.
Running every shard against the same suite and selection covers each property
exactly once. Reports and generated files are isolated under
`.cache/hypothesis-helm/runs/shards/INDEX-of-TOTAL/`. Saved suites also support
`helm hypothesis run generated-tests --shard 1/3`.

Each runner reports its own status; CI must require all shards to succeed.
Worker limits apply per instance, so use fixed `--jobs N` budgets when several
instances share a host. See [sharding](../usage.md#distributed-sharding) for
artifact handling, empty partitions, and reproducibility requirements.

## One final report

Give every shard the same `--run-id`, and use a fresh artifact directory per run.
For three local shards with two worker processes each:

```sh
run_id="$(date +%s)-$$"
artifacts=".cache/hypothesis-helm/sharded-$run_id"
parallel --jobs 3 --halt never --quote \
  helm hypothesis run generated-tests --shard {}/3 --jobs 2 \
  --run-id "$run_id" --artifact-dir "$artifacts" \
  --cache-dir .cache/hypothesis-helm/results ::: 1 2 3 || true
cat "$artifacts"/shards/*/report.json |
  helm hypothesis aggregate --shards 3 --run-id "$run_id" --output-dir "docs/reports/sharded-$run_id"
```

`aggregate` writes one final bundle containing `report.pdf`, `report.md`,
`report.json`, and `junit.xml`. The default is `docs/reports/aggregate`; `--output-dir` selects another new directory.
The merge returns a failure status when any shard fails. Missing, stale, or incompatible shards prevent publication. Suite fingerprints, collection
identities, shard ownership, and JUnit checksums must agree. Repeating the merge
with identical inputs reuses the same final bundle; concurrent mergers targeting
the same output directory cannot publish competing reports. Partial shard artifacts remain available separately.

Scan reports link **Full input and diagnostic** directly to the saved JSON evidence, including failure checkpoints from interrupted runs.
Markdown keeps relative paths; PDFs use absolute file URLs to open the data on the machine that generated the report.
Keep those artifacts in place when reading a local PDF. Published HTTPS links and links within the report are unchanged.

On separate CI runners, upload each shard’s `report.json` and pipe the downloaded
files into a single downstream aggregation job, including after test failures.
Reports embed their JUnit evidence; original runner paths are never opened. JSON
arrays, NDJSON, concatenated JSON objects, and explicit file arguments are supported.
Include the pipeline attempt in the run ID to prevent mixing retries. See the
[CI example](../ci/README.md). Checksums detect corruption and mismatched evidence;
they do not authenticate untrusted report producers.

Render-hash caches are process-local: six workers have six independent hash sets.
Persistent property caches have separate shard keys. Worker results use private
files; parents merge cache updates under a filesystem lock and publish atomically.
Concurrent conflicting failures are retained, while a later successful retry can
replace a previous failure. Schema checkouts use locks and immutable snapshots;
values-structure markers use atomic replacement. Duplicate invocations targeting
the same shard directory serialize through a per-shard lock.

A shared filesystem must support process locks and atomic renames. CI cache restores
on separate machines provide independent snapshots. Upload shard
artifacts for aggregation; do not rely on concurrent CI cache uploads to merge data.
Cached successes appear as reused properties, separately from executed JUnit cases.
When manifest output is requested, reused properties replay their complete saved resources
through `-o json` or `-o yaml`. Every stream is checked against its SHA-256 hash before a
property is skipped. Missing or corrupt streams cause fresh execution. Downstream validators
therefore receive both fresh and cached manifests, and run their current checks on both.
Streams are published only after the property and its teardown pass; reports record
`replayed_manifests` separately from newly rendered output.
An idle shard exits successfully with zero test workers and still publishes its report,
whether it owns no properties or all its properties have cached successes. Include that
report in aggregation, even when every shard is idle. For two pending properties across
three shards, unused capacity is expected. Hash assignment can produce uneven loads.
An unmatched `--match` expression remains an error. Cache reuse requires a compatible
suite fingerprint; changing chart contents can invalidate the full cached selection.
Elapsed time spans the timestamps reported by the shards; cross-host clock skew can
affect that measurement.

## Progressive dry runs

Run `helm hypothesis test examples/workload --dry-run --prune-equivalent`
to compare pairs, triples, and higher interaction strengths, up to the number of
fields with finite value choices. The plot shows planned input counts and estimated
render savings. It goes to stderr; stdout remains JSON.
Small input spaces are still enumerated automatically. Totals are exact when the
planner can enumerate the space within its limits. For larger spaces, the report
gives bounds and labels estimated filtering savings as estimates.
A higher-strength plan may omit cases from a lower-strength plan. To count the
additional work across stages, the estimate counts each distinct input only once.

Dry runs never invoke Helm, run assertions, write history, or authorize pruning.
Estimated render savings assume the first tested input in each equivalence group
passes validation and that the chart and renderer stay unchanged. Templates the
compiler cannot analyze still require rendering. Runtime estimates use compatible
render and validation timings from prior runs in the artifact directory.
Without those measurements, time is unknown. Per-path dry runs instead plot
selected, scheduled and cached properties with their existing filters.

Whole-chart execution has a default three-minute budget. Set another limit with
`helm hypothesis test examples/workload --time-limit 30s` (bare numbers mean seconds;
`m` and `h` suffixes are also accepted). Planning and dry-run calculation are excluded
from this execution budget. Generated per-path suites do not use this option.

At the deadline, the CLI stops the active iteration and returns `status: time-limit`
with exit code 124. Completed, attempted and remaining iteration counts, elapsed
time, render hashes, pruning statistics and measured history are retained, along
with an incomplete JUnit result. A budget stop records unfinished work.
Starting another run begins its planned inputs again; retained statistics
describe the previous run.

The dry-run plot recommends the highest completed strength whose predicted
execution time fits the budget. It evaluates higher strengths where the planning
limits allow; unavailable stages are reported. Timing remains advisory and an
unknown estimate never claims to fit. Explicit coverage settings remain unchanged,
and actual runs enforce the execution limit regardless of the forecast.

CLI execution interrupts input generation, active renders and assertions using a temporary timer.
Library calls from a non-main thread, or applications that already own an alarm,
instead stop between operations and cap Helm's timeout to the remaining budget;
an in-flight custom callback in those cases must return before execution can stop.

### Shutdown and partial results

Deadlines stop new work before cleanup. Process owners stop their child groups and
wait for their direct children; executor owners then join their threads or replicas.
Cancellation during registration or joining is deferred until ownership is secure.
SIGTERM uses the same cleanup path as Ctrl-C unless the embedding application has
installed its own signal handler.

The shutdown regression tests cover these boundaries:

| Hierarchy | Verified cases |
| --- | --- |
| CLI → pytest → Helm or nested command | Serial, fixed and adaptive workers; SIGINT and SIGTERM; stubborn descendants |
| Git, Helm registry or validator command → descendants | Successful exit, communication failure and timeout |
| Benchmark coordinator → replicas → renderer → descendants | Coordinator cancellation, worker deadline and outer GNU Parallel timeout |
| Shared process owner → multiple children | One cleanup failure or repeated cancellation does not skip sibling joins |

Benchmark results retain completed and remaining counts when stopped. A timeout is
recorded as incomplete work. Cleanup can extend elapsed
time beyond the testing budget. GNU Parallel wrappers allow ten seconds between
termination and forced killing so Python workers can finish cleanup and reporting.
SIGKILL, machine loss and CI runners that forcibly destroy the job cannot run Python
cleanup handlers; these cases require the runner's process or container teardown.

## Optional filtering

Filtering selects which planned cases to execute. The individual controls below
default to zero and can be combined; `--filter` is a preset described under
[expanding observed failures](#expanding-observed-failures).

```sh
helm hypothesis test CHART --permutations 2 --filter-random 1 --filter-topology 1 --seed 2026
```

- `--filter-random N`: randomly keep one quarter of the cases for each increase in N.
  Levels 1–3 retain about 25%, 6.25%, and 1.56%.
- `--filter-topology N`: group inputs whose predicted template output and branch
  choices match, then keep one quarter of each group for each increase in N.
  Keep at least one input per group and every input the compiler cannot classify.
- Together: add the two levels and sample within each topology group. Still keep
  at least one input per group and all unclassified inputs. This can keep more
  cases than random filtering alone at the same total level.

The chart's default values are always checked before the retained cases.
Each quarter-size selection is rounded up to a whole number of cases: 17 non-default cases
become 5 at level 1, then 2 at level 2. With the same planned cases, seed, and
other options, increasing the filter level only removes cases. For example, every
case kept by `--filter-random 2` is also kept by `--filter-random 1`.

Topology groups come from template analysis before testing. Execution determines
whether their inputs pass the selected checks. If the compiler cannot analyze an expression or
establish the renderer's behavior, it keeps the affected cases. Reports show which
inputs affect each template, branch choices, group sizes, and omitted cases.
Sampling within groups preserves examples of different outputs, but it can change
how often each output appears compared with the full input space.

The planner builds the test cases and removes duplicates before filtering. Filtering
reduces the number of cases executed; it does not reduce the work needed to plan
them. A passing filtered run means all executed checks passed. It does not establish
the original plan's interaction coverage or exhaustive group coverage.
Exact-equivalence pruning remains a separate control. These two filters apply to finite
permutation plans, including automatic enumeration. It does not apply to per-path
suites, random whole-chart sampling, or explicit exhaustive mode.

See [computational cost](../adaptive-filtering/README.md#computational-cost) for the shared comparison
of unfiltered execution, individual filters, percentage sampling and both filter presets.

### Expanding observed failures

Use `--filter` as shorthand for `--filter-topology 2 --expand-failures`.
It cannot be combined with either of those individual options; they can still be
used together. Random filtering is independent: add `--filter-random N`
alongside `--filter` if wanted. Its default remains zero.

```sh
helm hypothesis test ./chart --filter --time-limit 9m
```

Failure expansion is enabled automatically by `--filter` in finite permutation
tests and scans. Without `--filter`, opt in with `--expand-failures`. After a check fails,
it schedules previously omitted inputs that the compiler placed in the same group
of predicted outputs and branch choices, executes each
at most once, and continues within the existing `--time-limit`. Added inputs are
rendered even when `--prune-equivalent` is enabled. The original failure still
fails the run; reports retain individual failures and additional-work counts.
The initial selection continues after failures when expansion is enabled;
without the flag, ordinary execution still stops at the first failure.

This measures how widely a failure applies. In one PCA benchmark, testing 47
failing inputs found every distinct faulty output produced by 51 known failing
inputs. The other four inputs produced faulty outputs already seen. Expansion
can test those four as well. It cannot discover a group whose first failing case
was never tested, or assume an untested input will fail. Cases the compiler cannot
group are not automatically added through expansion.<sup>[\[2\]](<../../studies/expansion/README.md>)</sup>

See the [paired failure-expansion matrix](<../../studies/expansion/README.md>).
Dry runs report a bound on additional work; the actual count depends on failures.

## Percentage sampling

`--sample-random 70 --sample-min-cases 128` keeps 70% of the cases left after earlier
filters, rounded up to a whole case. It keeps at least 128, or all cases if fewer
than 128 remain. For example, it keeps 700 of 1,000 cases and all 100 of 100 cases.
The default is `--sample-random 100`, which disables this reduction. The minimum
test count sets the sampling floor. Bug discovery depends on which inputs
trigger defects and which inputs the sample contains.<sup>[\[3\]](../adaptive-filtering/README.md#what-determines-the-minimum)</sup>

```sh
helm hypothesis test ./chart --filter --sample-random 70 --sample-min-cases 128 --seed 2026
helm hypothesis scan bitnami/nginx --sample-random 70 --sample-min-cases 128 --seed 2026
helm hypothesis run ./generated-tests --sample-random 70 --sample-min-cases 128 --seed 2026
```

For finite plans, sampling selects complete configurations. For generated suites
and nonfinite chart scans, it selects path properties; each property can generate
many values. Finding a measured fraction of bugs when sampling complete
configurations does not establish the same result when sampling paths instead.
Unbounded `--whole-chart` generation has no enumerated population and rejects this option.

Existing filters run first, percentage sampling runs next, then traversal and
sharding. Chart plans and scans still test defaults before the selected cases.
With topology filtering, unknown cases and one
representative per region remain protected, so more than the requested percentage
may run. Failure expansion may subsequently add cases. Combining this option with
`--filter-random` applies both reductions; the minimum applies to the population left
by preceding filters and does not restore cases they already removed.

A fixed seed chooses the same identities independently of traversal order. Increasing
the percentage keeps previously selected cases and adds more, provided the eligible
population and protected cases have not changed.
All shards choose the global sample before partitioning it; workers do not sample
again. Dry runs, JSON reports, scan summaries, and aggregate reports include the
eligible, retained, omitted, and protected counts. Omissions are not successful tests.

For N eligible cases, sampling uses O(N log N) time to rank stable case identities
and O(N) memory. When every case is retained, it skips ranking and takes O(N) time.

See the [measured sample-size study](<../../studies/sampling/README.md>). Repeated
bugs can be found from a small sample. An error that occurs for only one input
requires sampling most of the population to obtain a high discovery probability.

### Adaptive preset

[`--filter-adaptive`](../adaptive-filtering/README.md) combines `--filter` with about 70% retention when measured
calibration supports it. Each chart receives a fresh complexity and topology analysis before test selection. Case and
changed-field floors can enlarge the sample. Unknown complexity or unmatched calibration keeps ordinary filtering.
See the [evidence and test matrix](../adaptive-filtering/TESTS.md).

### Parallel exhaustive execution

`helm hypothesis test ./chart --exhaustive --jobs 8 --shard none` uses eight concurrent Helm processes.
`--jobs auto` uses the available CPU count; `--jobs 1` preserves serial execution. Dependencies and planning finish before the execution budget starts.
The baseline is checked first. Workers prefetch a bounded window of finite inputs; the coordinator parses and validates results in seeded order,
updates one render-hash cache, streams complete JSON records, and writes the report. Schema validators and custom Python assertions run on the coordinator.

A failure, timeout or interrupt stops all owned Helm process groups and joins the worker threads before returning.
If the prepared chart's `Chart.yaml` disappears or becomes unreadable, testing stops for that chart with an execution error.
Serial paths, parallel path workers and exhaustive execution do not shrink this error or count it as a chart defect.
Earlier findings are retained, and a repository scan can continue to the next chart after the current workers have stopped.
Prefetched inputs that have not reached coordinator validation do not count as completed coverage; their number appears in `parallel_execution`.
The chart has one shared execution deadline, including coordinator validation. Cleanup can extend wall time slightly beyond that deadline.
Parallel exhaustive execution requires equivalence pruning and rejection filtering to be disabled. Distributed sharding remains unavailable for this mode.

# Execution and estimates

[Documentation](../README.md) · [Project](../../README.md)

Random text sampling excludes C0/C1 controls except LF and CR, including
inside nested values and generated map keys. Generated tabs are excluded too. Other Unicode text remains eligible.
This applies to whole-chart sampling and newly generated per-path suites; regenerate
saved suites to update their strategies. Explicit finite domains and chart defaults
are unchanged. If a schema requires only excluded strings, sampling cannot satisfy
that schema; an empty or unsatisfiable sample is not a successful test.

## Value-path traversal

`run`, `test`, and `scan` default to `--traversal-strategy random`. Discovery builds
the path inventory, filtering selects the work, and traversal orders it for execution.
Each selected path is scheduled once per invocation; its property can generate and
shrink multiple values. A timeout leaves the unvisited paths explicitly untested.

| Strategy | Execution order |
| --- | --- |
| `random` | Stable random priorities derived from `--seed` and path identity. |
| `linear` | Original path order. Scans follow supplied values before additional discovered paths. |
| `root-first` | Increasing path depth: `.global` before `.global.configMaps`. |
| `leaf-first` | Decreasing path depth: deepest leaves before their parent containers. |

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

Finite permutation runs order distinct configurations after trimming, with defaults
checked first. Fields necessarily recur across joint configurations. In these modes,
root-first uses the shallowest changed field and leaf-first the deepest, relative to defaults.
A render can be skipped as equivalent only after another input has passed validation
and the compiler has established that both inputs produce exactly the same output.

Ordering costs O(P) for linear traversal and O(P log P) for the other strategies,
with O(P) storage, excluding path encoding and finite-case comparisons. P counts
the paths or configurations selected for execution. Changing traversal strategy
changes their order; it does not add or remove tests. Testing every path does not
test every possible value or every interaction between paths.

Scan reports retain the seed, strategy, visited order, completed and incomplete path
counts, and remaining order. `path-inventory.json` records the planned sequence.
Per-path dry runs list the same ordered properties without executing them.

## Parallel execution

The unit of parallel work is a generated property for a values path. Each property
can render and validate its own inputs without depending on another property's
results, allowing the suite to execute properties concurrently.

1. **Collect and dispatch:** Pytest identifies the selected properties. A thread
   pool dispatches each queued property into a separate pytest process, isolating
   fixtures, Hypothesis state, and temporary chart files. Input generation and
   counterexample shrinking remain sequential within each property.
2. **Measure and adjust:** With `--jobs auto`, each completion feeds a throughput
   measurement. A PID controller uses measured changes in throughput to adjust
   active concurrency, starting at the available CPU count and probing up to four
   times that count, bounded by the number of selected tests. Measurement windows
   smooth timing noise; reducing concurrency lets active tests finish.
3. **Aggregate results:** The parent merges JUnit results and exit statuses, while
   synchronized manifest writes keep each JSON record intact. Completion order
   can vary without changing how individual properties are evaluated.

Custom tests must preserve this independence: shared mutable files or external
resources can introduce interference. Process and fixture startup add overhead,
so small suites may benefit less from parallelism. Automatic tuning seeks higher
throughput within its bounds; it does not guarantee a global optimum. Use
`--jobs N` for fixed concurrency or `--jobs 1` for serial execution. The explicit
whole-chart and exhaustive modes remain serial.

### Runtime estimates

**Expect the first execution to take substantially longer than a cached local
rerun.** The tool traverses the complete schema and discovered values-path tree to
generate properties, then executes every selected property because no successful
results are cached yet. Without filters or sharding, that means the full generated
suite, with repeated Helm renders and optional kubeconform validation for each
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
kubeconform's downloaded Kubernetes schemas retain their existing cache behavior.
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
cache. `--kubeconform` also reports schema-cache availability without fetching
schemas; an online refresh may change the predicted result-cache hit. See
[cache-aware dry runs](../usage.md#cache-aware-dry-runs) for details.


`helm hypothesis test ./chart --progress` explicitly enables a live progress bar
on stderr, including when output is redirected. It also works with
`helm hypothesis run`; JSON manifests remain on stdout.

The progress bar shows a live ETA based on completed properties. It starts unknown
and updates as measurements arrive; JUnit reports record each property's duration.
Schema types alone cannot predict runtime: Helm branches and resource counts,
Hypothesis input rejection and shrinking, and runner contention all affect cost.
`--max-examples` is a sampling budget, not an exact render count. Treat the ETA as a
rough estimate, particularly while automatic worker concurrency changes or a failing
property is shrinking. No reliable time estimate is claimed before tests execute.

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
`reports/hypothesis-helm/shards/INDEX-of-TOTAL/`. Saved suites also support
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
artifacts="reports/sharded-$run_id"
parallel --jobs 3 --halt never --quote \
  helm hypothesis run generated-tests --shard {}/3 --jobs 2 \
  --run-id "$run_id" --artifact-dir "$artifacts" \
  --cache-dir .cache/hypothesis-helm/results ::: 1 2 3 || true
cat "$artifacts"/shards/*/report.json |
  helm hypothesis aggregate --shards 3 --run-id "$run_id" --output-dir "$artifacts/final"
```

`aggregate` writes one `final/` bundle containing `report.pdf`, `report.md`,
`report.json`, and `junit.xml`. `--output-dir` selects another new directory.
The merge returns a failure status when any shard fails. Missing, stale, or incompatible shards prevent publication. Suite fingerprints, collection
identities, shard ownership, and JUnit checksums must agree. Repeating the merge
with identical inputs reuses the same final bundle; concurrent mergers targeting
the same output directory cannot publish competing reports. Partial shard artifacts remain available separately.

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
on separate machines are independent snapshots, not shared memory. Upload shard
artifacts for aggregation; do not rely on concurrent CI cache uploads to merge data.
Cached successes appear as reused properties, separately from executed JUnit cases.
An idle shard exits successfully with zero test workers and still publishes its report,
whether it owns no properties or all its properties have cached successes. Include that
report in aggregation, even when every shard is idle. For two pending properties across
three shards, unused capacity is expected; hash assignment does not guarantee equal loads.
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
with an incomplete JUnit result. A budget stop does not create a chart
counterexample or claim complete coverage. Starting another run currently starts
its planned inputs again; retained statistics are not a resume checkpoint.

The dry-run plot recommends the highest completed strength whose predicted
execution time fits the budget. It evaluates higher strengths where the planning
limits allow; unavailable stages are reported. Timing remains advisory and an
unknown estimate never claims to fit. Explicit coverage settings remain unchanged,
and actual runs enforce the execution limit regardless of the forecast.

CLI execution interrupts active renders and assertions using a temporary timer.
Library calls from a non-main thread, or applications that already own an alarm,
instead stop between operations and cap Helm's timeout to the remaining budget;
an in-flight custom callback in those cases must return before execution can stop.

## Optional trimming

Both controls default to zero and can be combined:

```sh
helm hypothesis test CHART --permutations 2 --trim-random 1 --trim-topology 1 --seed 2026
```

- `--trim-random N`: randomly keep one quarter of the cases for each increase in N.
  `--trim` remains an alias. Levels 1–3 retain about 25%, 6.25%, and 1.56%.
- `--trim-topology N`: group inputs whose predicted template output and branch
  choices match, then keep one quarter of each group for each increase in N.
  Keep at least one input per group and every input the compiler cannot classify.
- Together: add the two levels and sample within each topology group. Still keep
  at least one input per group and all unclassified inputs. This can keep more
  cases than random trimming alone at the same total level.

The chart's default values are always checked before the trimmed cases.
Each quarter-size selection is rounded up to a whole number of cases: 17 non-default cases
become 5 at level 1, then 2 at level 2. With the same planned cases, seed, and
other options, increasing the trim level only removes cases. For example, every
case kept by `--trim-random 2` is also kept by `--trim-random 1`.

Topology groups come from template analysis before testing. Membership does not
mean an input has passed a test. If the compiler cannot analyze an expression or
establish the renderer's behavior, it keeps the affected cases. Reports show which
inputs affect each template, branch choices, group sizes, and omitted cases.
Sampling within groups preserves examples of different outputs, but it can change
how often each output appears compared with the full input space.

The planner builds the test cases and removes duplicates before trimming. Trimming
reduces the number of cases executed; it does not reduce the work needed to plan
them. A passing trimmed run means all executed checks passed. It does not establish
the original plan's interaction coverage or exhaustive group coverage.
Exact-equivalence pruning remains a separate control. Trimming applies to finite
permutation plans, including automatic enumeration. It does not apply to per-path
suites, random whole-chart sampling, or explicit exhaustive mode.

### Computational cost

| Mode | Approximate time | Annotation |
|---|---|---|
| Default | `P + N·R` | Execute the full finite plan. |
| `--trim-random` | `P + N + K log K + K·R` | Shuffle once; restore retained cases to execution order. |
| `--trim-topology` | `P + A + N·C + Σ(Kᵢ log Kᵢ) + K·R` | Classify every candidate; sample within regions. |
| Both | Same form as topology | Add the levels within each group; keep at least one case and all unclassified cases. |

`P`: planning cost; `N`: planned non-default cases; `K`: retained cases;
`Kᵢ`: retained cases in region i; `R`: render and validation cost;
`A`: chart analysis and IR construction; `C`: per-case symbolic evaluation, value
normalization and projection construction.
The single defaults check is omitted from these expressions. They describe execution
without optional equivalence pruning, with bounded-size values; larger values add
serialization and copying costs.

All modes store the full plan (`O(N)` cases). Random trimming also stores `O(N)`
indices. Topology trimming stores group membership and predicted output information.
Planning can take longer than execution: exhaustive enumeration must account for
the product of all fields' value counts. Strength-t planning must cover every valid
assignment to each set of t fields. Planning limits still apply before trimming.

### Expanding observed failures

Use `--filter` as shorthand for `--trim-topology 2 --expand-failures`.
It cannot be combined with either of those individual options; they can still be
used together. Random trimming is independent: add `--trim-random N` (or `--trim N`)
alongside `--filter` if wanted. Its default remains zero.

```sh
helm hypothesis test ./chart --filter --time-limit 9m
```

Failure expansion is enabled automatically by `--filter` in finite permutation
tests and scans. Without `--filter`, opt in with `--expand-failures`. After a check fails,
it schedules omitted inputs in the same supported symbolic region, executes each
at most once, and continues within the existing `--time-limit`. Added inputs are
rendered even when `--prune-equivalent` is enabled. The original failure still
fails the run; reports retain individual failures and additional-work counts.
The initial selection continues after failures when expansion is enabled;
without the flag, ordinary execution still stops at the first failure.

This measures how widely a failure applies. In the seeded PCA fixture, 47 tested
erroneous inputs represented all 51 erroneous inputs' output regions: four regions
contained a second, output-equivalent input. Expansion can exercise those four
without discovering a different erroneous output. It does not infer failures for
unexecuted inputs, and cannot recover an entirely missed failure region.
Unsupported regions have no automatic expansion membership.

See the [paired failure-expansion matrix](../../benchmarks/expansion/README.md).
Dry runs report a bound on additional work; the actual count depends on failures.

## Percentage sampling

`--sample-random 70 --sample-min-cases 128` retains 70% of eligible cases, rounded
upward, with a floor of 128. Smaller populations run in full. The default is
`--sample-random 100`, which disables sampling. The floor is a policy choice;
it is not a guarantee of defect recall.

```sh
helm hypothesis test ./chart --filter --sample-random 70 --sample-min-cases 128 --seed 2026
helm hypothesis scan bitnami/nginx --sample-random 70 --sample-min-cases 128 --seed 2026
helm hypothesis run ./generated-tests --sample-random 70 --sample-min-cases 128 --seed 2026
```

For finite plans, sampling selects complete configurations. For generated suites
and nonfinite chart scans, it selects path properties; each property can generate
many values. Benchmark configuration recall does not predict path-property recall.
Unbounded `--whole-chart` generation has no enumerated population and rejects this option.

Existing filters run first, percentage sampling runs next, then traversal and
sharding. Chart plans and scans still test defaults before the selected cases.
With topology filtering, unknown cases and one
representative per region remain protected, so more than the requested percentage
may run. Failure expansion may subsequently add cases. Combining this option with
`--trim-random` applies both reductions; the minimum applies to the population left
by preceding filters and does not restore cases they already removed.

A fixed seed chooses the same identities independently of traversal order. Increasing
the percentage keeps previously selected cases and adds more, provided the eligible
population and protected cases have not changed.
All shards choose the global sample before partitioning it; workers do not sample
again. Dry runs, JSON reports, scan summaries, and aggregate reports include the
eligible, retained, omitted, and protected counts. Omissions are not successful tests.

For N eligible cases, sampling uses O(N log N) time to rank stable case identities
and O(N) memory. When every case is retained, it skips ranking and takes O(N) time.

See the [measured sample-size study](../../benchmarks/sampling/README.md). Repeated
bugs can be found from a small sample. An error that occurs for only one input
requires sampling most of the population to obtain a high discovery probability.

### Planned aggressive preset

[`--filter-aggressive`](../aggressive-filtering/README.md) is a proposed preset combining `--filter` with about 70%
retention. After discovery and chart preparation, it would recompute complexity for each chart immediately before
selecting its tests. Its minimum sample and distinct-field coverage would be calibrated against that fresh result
and chart topology. Unknown complexity or missing calibration would keep all cases left by `--filter`. The flag is not yet
implemented; the explicit sampling options above are available today.

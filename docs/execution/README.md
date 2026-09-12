# Execution and estimates

[Documentation](../README.md) · [Project](../../README.md)

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

## Progressive dry runs

Run `helm hypothesis test examples/workload --dry-run --prune-equivalent`
to plot increasing strengths through the finite factor count, additional and cumulative inputs, and
potential render savings. The plot goes to stderr; stdout remains JSON.
The configured run retains automatic exhaustive enumeration for small domains.
Affordable full totals are exact; larger totals show bounds and an explicitly
heuristic filtering extrapolation. Stages need not be nested, so incremental
work is calculated using input-set unions.

Dry runs never invoke Helm, run assertions, write history, or authorize pruning.
Filtering forecasts assume successful representatives and a fixed renderer and
chart; unsupported templates require rendering. Runtime estimates use compatible
measured renderer and check costs from prior runs in the artifact directory.
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

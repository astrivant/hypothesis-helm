# Planned preset: `--filter-aggressive`

[Execution](../execution/README.md#percentage-sampling) · [Audit complexity](../inputs/README.md#potential-output-complexity)

**Design proposal; the CLI does not implement this flag yet.** The current default retains all eligible cases.

`--filter-aggressive` would apply `--filter`, then retain about **70% of the remaining eligible cases** using seeded
random sampling. This omits about 30%, subject to minimum coverage requirements. Defaults, protected topology
representatives and failure expansion retain their existing behavior. The preset would share `--filter`'s exclusion
rules for individual filtering flags and could not be combined with `--filter`.

## Let the audit determine the minimum

The audit supplies the chart's greatest supported output complexity: the maximum **breadth × depth** across its
allowed values. Calibration must measure how sample size affects defect discovery at different complexity levels,
using the configurable benchmark chart. A formula that simply treats the score as a field count would mix unrelated units.

The calibration should record minimum sample sizes and minimum distinct-field coverage against output complexity,
input-field count, gate structure and interaction patterns. Charts with the same maximum output score can have very
different rare failure conditions. Measure multiple seeds and validate the policy on held-out generated charts.
Publish the observed recall, variation and supported range with each calibration version.

The existing sampling study measures one fixture. It does not yet establish this complexity-dependent minimum;
its fixed 128-case floor must not be presented as a measured result of the audit.

## Recompute before visiting each chart

Discovery inventories the charts. When execution reaches each usable chart, prepare its dependencies and effective
values/schema snapshot, then recompute complexity before filtering, sampling or scheduling that chart's tests.
Every chart visit requires a fresh calculation, including repeat runs with a warm outcome cache. A previous audit
or another chart's score cannot replace it.

Use that result to choose the calibration and coverage floors for this chart only. Record the analyzed snapshot's
fingerprint and calculation time. If the snapshot changes before selection, recompute against the new snapshot;
if a consistent result cannot be established within the analysis budget, disable the additional percentage sampling
and report the reason. Charts that cannot be prepared remain N/A; charts never reached before a scan stops remain
pending, without a claimed complexity result.

The chart coordinator passes the fresh decision to its workers before partitioning work. Independently launched
CI shards must also recompute against their prepared chart snapshot and agree on the resulting selection policy.
Workers do not recompute complexity for individual cases. Report complexity-analysis time separately from dependency
preparation and property-test execution.

## Selection policy

For each chart, after the existing filters:

1. Use the freshly recomputed complexity result for this chart visit to select a matching calibration.
2. Start with 70% of eligible cases, rounding up to a whole case.
3. Raise that count to the calibrated sample floor and preserve all protected cases.
4. Add cases in the same seeded order until the calibrated minimum number of distinct eligible values paths is covered.
   If either requirement exceeds what the eligible population can supply, keep it all.
5. Select globally before traversal and sharding. Workers execute their partitions without sampling again.

For generated suites, a sampled case is a path property. For finite permutation plans, it is a complete configuration;
count distinct changed paths separately rather than treating configurations as fields. Measure each mode independently.
These counts describe the selected plan; timeouts can prevent the selected cases from completing.

If complexity is unknown, calibration is missing or outside its measured range, or the audit snapshot is stale,
apply `--filter` without additional percentage sampling and report the reason. A lower bound on complexity cannot
justify a smaller minimum. Calibration must also match any additional trimming settings, since earlier filters
change the population from which sampling selects.

## Report the decision

Dry runs and execution reports should include the audit metric/version and status, chart fingerprint, computation time, calibration
version, selection unit, requested percentage, derived sample and field floors, eligible and retained counts,
protected cases, distinct selected fields, seed, and any fallback reason. Execution reports should also distinguish
selected coverage from completed coverage. Shard aggregation must verify that every shard used the same decision.

The minimum is an empirical sampling policy, not a proof of defect recall. Exact output bounds justify the audit's
complexity result; they do not establish that randomly omitted inputs are free of defects.

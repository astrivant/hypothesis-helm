# Aggressive filtering

[Execution](../execution/README.md#percentage-sampling) · [Audit complexity](../inputs/README.md#potential-output-complexity)

`--filter-aggressive` applies `--filter`, then uses measured chart profiles to retain about **70% of the remaining cases**.
It raises that count when needed to meet calibrated case and field floors, and always preserves protected topology representatives.
Unmatched or unsupported charts keep ordinary filtering without additional percentage sampling.

```sh
helm hypothesis test ./charts --filter-aggressive --seed 2026
helm hypothesis scan https://github.com/example/charts.git --filter-aggressive
```

Use this preset instead of `--filter` or its individual topology/expansion flags. It also excludes explicit
`--sample-random` and `--sample-min-cases` overrides. `--trim` remains composable, but changes the calibration context;
a context without measurements disables the additional sampling.

## What determines the minimum?

The audit reports the maximum supported manifest breadth × depth, input-field count, finite domain sizes and types,
gate depth, and template input fan-in. The planner adds the reachable symbolic region sizes before and after filtering.
A gate is a template `if` condition; gate depth counts nested conditions required to reach a branch.
Template fan-in is a conservative interaction descriptor: it counts referenced fields in a template, not a proven minimal interaction order.

The [calibration study](../../benchmarks/calibration-variation/README.md) measures case floors and changed-field floors separately.
A configuration can change several fields; a complexity score is neither a case count nor a field count.
The selected field floor counts distinct paths whose effective values differ from the defaults. Lists count as one changed path.

Matching prefers an exact descriptor. Nearby matching is available only when the calibration's
[evidence matrix](../../benchmarks/calibration-variation/MATRIX.md) enables it. It requires compatible domain types, domain
cardinalities and filter settings. Every numeric coordinate must lie within the measured range. Distance is the largest
relative coordinate difference, `abs(a - b) / max(abs(a), abs(b))`, with two zero coordinates treated as equal.
The policy uses the largest case floor and the largest field floor among all neighbors within its measured radius.
It does not extrapolate beyond measured ranges.

The radius is selected using the same generated fixtures with each target's exact matches excluded from lookup.
This is a calibration cross-check, not independent validation. It does not guarantee bug recall on another chart.

The packaged study covers 30 variants with maximum output score 24. Ordinary filtering leaves 886 cases across these variants;
exact-profile sampling retains 875, with all known defects found across 100 seeds per variant. Nearby matching remains disabled:
only one variant gained additional reduction, below the activation requirement of two. These results do not calibrate other output scores.

## Recompute before visiting each chart

Each chart receives a fresh compiler analysis before property-test selection, after dependency preparation and baseline checks.
A previous audit or cached test result does not replace that calculation. Reports include the source fingerprint,
analysis time, maximum complexity and matching decision.

If source bytes change during analysis or selection, additional sampling is disabled. Unsupported template code,
unknown maxima, unresolved regions, missing calibration and unmatched profiles also retain the ordinary filtered plan.
The report records the reason. Baseline failures and charts that cannot be prepared do not reach property selection.

This calibration applies to finite configuration plans. Non-finite path-property testing keeps ordinary filtering and
reports that no path-property calibration is available. The preset uses the same finite-plan execution restrictions as
`--filter`; it is not an additional sampling mode for exported pytest suites or their shards.

## Selection and evidence

For each eligible plan, selection proceeds as follows:

1. Reserve every protected case.
2. Raise the quota to the larger of 70% (rounded up), the calibrated case floor and the protected-case count.
3. Fill the quota using a reproducible hash ranking based on case identity and seed.
4. Continue through that ranking until the calibrated changed-field floor is met.
   If the floor cannot be met, retain the entire eligible plan.

Defaults remain a separate baseline check. Failure expansion retains access to the original plan. Traversal orders the selected cases
for execution; a timeout can prevent some selected cases from completing.
Reports distinguish eligible, selected, omitted and protected cases, selected fields, calibration ID and matching distance.

See the [proof obligations and regression matrix](TESTS.md) for the deterministic properties checked by tests.
The [benchmark matrix](../../benchmarks/calibration-variation/MATRIX.md) shows empirical case reduction and known-bug discovery.
Protected symbolic output regions can account for complete bug discovery in these fixtures; the graphs do not establish the
same result for random sampling alone.

## Reproduce the study

```sh
pip install 'hypothesis-helm[benchmarking]'
hypothesis-helm-benchmark calibration --output benchmarks/runs/calibration --time-limit 9m
```

The command reuses one generated chart across 30 parameter recipes, renders every finite input with Helm,
and compares those outputs to the injected-defect oracle. It evaluates 100 seeds per fixture and writes PNG/SVG graphs,
CSV/JSON measurements and a readable matrix. The full refresh includes this study. Use `--plot-only` with its output directory
to redraw figures without rerendering charts.

`--sampling-calibration path/to/calibration.json` replaces the packaged calibration for an aggressive run.
A completed study records its source digest and Helm version. Regenerating benchmark evidence does not silently replace the
packaged runtime policy; changes to that policy should be reviewed alongside the matrix.

## Computational cost

These bounds describe filtering **after candidate generation**, excluding Helm execution. Let `N` be the candidate count,
`V` the values-document size, `T` the template-analysis work per case, `P` the number of calibration profiles, and `D` their descriptor size.
`A` is the cost of fresh maximum-complexity and profile analysis for the chart.

| Option | Filtering time |
| --- | --- |
| `--sample-random` | `O(N log N + NV)` for seeded ranking and case identities |
| `--filter` | `O(NT + N log N + NV)` for symbolic regions, identities and selection |
| `--filter-aggressive` | `O(A + PD + NT + N log N + NV)` including calibration lookup and changed-field floors |

Exact and nearby lookup both scan the calibration: `O(PD)`. The packaged calibration has 30 profiles. Nearby lookup does not
enumerate chart values again. The field-floor check can inspect every remaining case, including cases it ultimately omits.
Cases and their identities use `O(NV)` storage; calibration and compiler tables add their own storage.

`A` can be exponential in the number of independently varying fields. With `F` Boolean fields, the input space has `2^F`
assignments. Component tables restrict enumeration to the fields each template uses, and branch-and-bound can skip many assignments.
Its bounds rescan those tables, so the worst case can cost more than one exhaustive pass. There is no polynomial-time guarantee.
The maximum search currently allows 4,096 charged evaluations and targets a five-second budget, checked between work units;
source loading, profiling and later topology selection add overhead. An incomplete maximum disables additional percentage sampling.
These are the costs of establishing a maximum. The budget limits effort by allowing an unknown result; it does not turn exact maximization
into a polynomial-time algorithm.

Execution adds roughly `K × H`, where `K` is the number of cases actually tested and `H` their average Helm/property-test cost.
Failure expansion can increase `K` toward the original plan. Thus filtering reduces typical execution volume without improving
its worst-case asymptotic bound. The measured matrix records case counts; it is not a runtime speedup benchmark.

### Conditions behind the comparison

These are bounds for a finite, already generated plan. Variable-size values and templates are represented by `V` and `T`;
calling the pass simply `O(N log N)` assumes their sizes stay bounded. The load test includes candidate generation in planning,
so its total runtime is not a direct measurement of the filtering pass alone.

For unique non-default inputs, the number retained before execution is more precise than a complexity class:

| Method | Retained non-default cases | Conditions |
| --- | --- | --- |
| Random 70% | `min(N, max(128, ceil(0.7N)))` | Default case floor; no additional protected cases or preceding filters |
| `--filter` | `sum(ceil(n_j / 16))` | Topology depth two, supported groups of sizes `n_j`, no extra trim or failure expansion yet |
| Aggressive | At least `min(M, max(ceil(0.7M), case_floor, protected_count))` | A matching calibration; `M` is the ordinary filtered count |

Aggressive selection can add further cases to meet its field floor. An unmatched chart retains `M`. Unknown topology cases are
retained in addition to the supported-group sum. Each method also checks the baseline. Timeouts can leave planned cases unexecuted,
and failing properties can trigger expansion beyond these initial counts.

If there are `R` supported groups, ordinary filtering retains at least `R` cases. It is useful when many inputs share a group;
when nearly every input has its own group, filtering has little work to remove. Aggressive sampling is useful only if its
additional saved execution exceeds the cost of fresh analysis and selection:

`(ordinary_completed - aggressive_completed) × average_test_cost > additional_planning_cost`

This break-even approximation assumes comparable per-case costs and completed runs. It does not apply directly to censored timings
or when the selected inputs have materially different render costs.
The current load test uses native Helm/render checks without external kubeconform or kubesec validation; those checks can change the per-case cost.

Preserving a representative can preserve a failure **if** exact manifest equivalence is established, the property depends only on
those manifests, the render context is fixed, and the representative is actually tested. Similar topology descriptors alone do not
establish equivalence or guarantee recall.

Under an ideal uniform sample without replacement, with `B` erroneous inputs among `N` fixed inputs, the probability of missing all
of them in `k` tests is `C(N-B, k) / C(N, k)`. This is a model for percentage sampling, not a guarantee supplied by a deterministic seed.
Protected representatives and adaptive field floors make aggressive sampling nonuniform, so that formula cannot be applied to it unchanged.

For independent, uniformly chosen Boolean fields, a specified chain of `g` gates is reached with probability `2^-g`.
Constraints or correlated fields invalidate that calculation. The load fixture has unconstrained Boolean fields; its gate depths
therefore provide controlled changes in branch rarity and symbolic region structure.

See the [real Helm load test](../../benchmarks/filtering/README.md) for runtime, planning, completed-work and phase graphs.
Reproduce it with `hypothesis-helm-benchmark filtering --output benchmarks/runs/filtering --time-limit 9m`.

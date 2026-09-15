# Adaptive filtering

[Execution](../execution/README.md#percentage-sampling) · [Audit complexity](../inputs/README.md#potential-output-complexity)

`--filter-adaptive` starts with `--filter`, then aims to test about **70% of the
remaining input configurations**. It uses benchmark measurements to decide whether
that extra reduction is supported for the current chart. When necessary, it keeps
more tests to meet a measured minimum or preserve examples of different predicted
outputs. If suitable measurements are unavailable, it keeps the ordinary filtered
selection.<sup>[\[1\]](#what-determines-the-minimum)</sup>

Recommended workflow: use `--filter-adaptive` on **MRs/PRs**, `--filter` on **main**, and
an unfiltered `--exhaustive` search **before tagging**. The pre-tag run must complete its supported
finite domain; see the [CI workflow](../ci/README.md#recommended-workflow) for commands and coverage requirements.

```sh
helm hypothesis test ./charts --filter-adaptive --seed 2026
helm hypothesis scan https://github.com/example/charts.git --filter-adaptive
```

Use this preset instead of `--filter` or its individual topology/expansion flags. It also excludes explicit
`--sample-random` and `--sample-min-cases` overrides. You can also use `--trim`, but
the benchmark evidence must cover that combination of settings. Otherwise the
additional percentage sampling is disabled.

## What determines the minimum?

The tool builds a **chart profile**, a set of measurements it compares with charts
used in the benchmark. The profile includes:

- **Maximum output complexity:** how wide and deeply nested the output can become.<sup>[\[2\]](../inputs/README.md#potential-output-complexity)</sup>
- **Input choices:** the number of fields, their types, and how many allowed values
  each field has. An allowed set of values is called a **domain**.
- **Gate depth:** how many nested `if` conditions must be satisfied to reach a
  template branch. A **gate** is one such condition.
- **Template fan-in:** how many input fields a template reads. This indicates
  where interactions may occur; it does not prove those fields interact.
- **Region sizes:** how many configurations the compiler groups together because
  they have matching predicted output and branch choices, before and after filtering.<sup>[\[3\]](../execution/README.md#optional-trimming)</sup>

The benchmark determines two separate minimums, also called **floors**: how many
configurations to test, and how many different fields those configurations must
change from the defaults. One configuration can change several fields. A list
counts as one changed path. These minimums come from measured bug discovery, not
from treating the complexity score as a number of tests.<sup>[\[4\]](../../studies/calibration-variation/README.md)</sup>

The tool first looks for a measured profile that matches exactly. **Nearby matching**
can use similar profiles, but only if the benchmark evidence enables that policy.
Input types, numbers of allowed choices and filter settings must be compatible.
Every numerical measurement must fall within the range covered by the study.

Similarity is measured one quantity at a time: the relative difference is
`abs(a - b) / max(abs(a), abs(b))`; two zeros have no difference. The largest of
these differences determines whether a profile is close enough. The allowed
difference is called the **radius**. Among all matching profiles, the tool takes
the largest minimum test count and the largest minimum changed-field count.
It does not extend the evidence beyond the measured ranges.<sup>[\[5\]](../../studies/calibration-variation/MATRIX.md)</sup>

To evaluate a radius, the study removes a chart's exact matches and checks whether
nearby profiles still find enough of its known bugs. This reuses the generated
benchmark charts; it is not a test on independent charts and does not guarantee
the same fraction of bugs will be found in your chart.

The packaged study covers 30 variants with maximum output score 24. Ordinary filtering leaves 886 cases across these variants;
exact-profile sampling retains 875, with all known defects found across 100 seeds per variant. Nearby matching remains disabled:
only one variant gained additional reduction, below the activation requirement of two. These results do not calibrate other output scores.

## Recompute before visiting each chart

Each chart receives a fresh compiler analysis before property-test selection, after dependency preparation and baseline checks.
A previous audit or cached test result does not replace that calculation. Reports include the source fingerprint,
analysis time, maximum complexity and matching decision.

If source bytes change during analysis or selection, additional sampling is disabled. Unsupported template code,
an unknown maximum, configurations the compiler cannot classify, missing benchmark
evidence or a profile with no match also retain the ordinary filtered plan.
The report records the reason. Baseline failures and charts that cannot be prepared do not reach property selection.

This calibration applies to finite configuration plans. Non-finite path-property testing keeps ordinary filtering and
reports that no path-property calibration is available. The preset uses the same finite-plan execution restrictions as
`--filter`; it is not an additional sampling mode for exported pytest suites or their shards.

## Selection and evidence

For each eligible plan, selection proceeds as follows:

1. Keep every **protected case**: configurations the compiler cannot classify and
   at least one example from each supported group of predicted outputs.
2. Choose the largest of three counts: 70% of the remaining plan (rounded up),
   the measured minimum test count, or the number of protected cases.
3. Fill that count in a reproducible random order determined by the inputs and seed.
4. Add more cases in that order until enough different fields have been changed.
   If that minimum cannot be met, keep the entire eligible plan.

Defaults remain a separate baseline check. Failure expansion retains access to the original plan. Traversal orders the selected cases
for execution; a timeout can prevent some selected cases from completing.
Reports distinguish eligible, selected, omitted and protected cases, selected fields, calibration ID and matching distance.

See the [proof obligations and regression matrix](TESTS.md) for the deterministic properties checked by tests.
The [benchmark matrix](../../studies/calibration-variation/MATRIX.md) shows empirical case reduction and known-bug discovery.
Keeping examples from every predicted output group can explain why all known bugs
were found in these benchmark charts. The graphs do not show that random sampling
alone would achieve the same result.

## Reproduce the study

```sh
pip install 'hypothesis-helm[benchmarking]'
hypothesis-helm-benchmark calibration --output benchmarks/runs/calibration --time-limit 9m
```

The command reuses one generated chart across 30 parameter recipes, renders every finite input with Helm,
and compares those outputs to the injected-defect oracle. It evaluates 100 seeds per fixture and writes PNG/SVG graphs,
CSV/JSON measurements and a readable matrix. The full refresh includes this study. Use `--plot-only` with its output directory
to redraw figures without rerendering charts.

`--sampling-calibration path/to/calibration.json` replaces the packaged calibration for an adaptive run.
A completed study records its source digest and Helm version. Regenerating benchmark evidence does not silently replace the
packaged runtime policy; changes to that policy should be reviewed alongside the matrix.

## Computational cost

The table describes how filtering work grows as the problem gets larger. It starts
**after the input configurations have been generated** and excludes running Helm.
`O(...)` describes growth in work, not a predicted duration in seconds.

| Symbol | Meaning |
| --- | --- |
| `N`, `K` | Configurations considered and configurations kept for execution |
| `V` | Size of one values document |
| `T` | Template-analysis work for one configuration |
| `P`, `D` | Measured profiles available and measurements compared per profile |
| `A` | Fresh complexity search and profile analysis for the chart |
| `I`, `C` | Initial template parsing and analysis, then output prediction for one configuration |
| `Kᵢ` | Configurations kept from output group `i` |

The complexity search has its own budget and can return an unknown maximum.<sup>[\[6\]](../inputs/README.md#how-the-maximum-is-found)</sup>

| Option | Filtering time |
| --- | --- |
| No filtering | No additional filtering pass; execute all `N` planned cases |
| `--trim-random` | `O(N + K log K)` to shuffle indices and restore retained cases to execution order |
| `--trim-topology` | `O(I + NC + Σ(Kᵢ log Kᵢ))` to classify candidates and sample within regions |
| Both trims | Same form as topology trimming; add levels within each region and retain unclassified cases |
| `--sample-random` | `O(N log N + NV)` for seeded ranking and case identities |
| `--filter` | `O(NT + N log N + NV)` for symbolic regions, identities and selection |
| `--filter-adaptive` | `O(A + PD + NT + N log N + NV)` including calibration lookup and changed-field floors |

Exact and nearby lookup both scan the calibration: `O(PD)`. The packaged calibration has 30 profiles. Nearby lookup does not
enumerate chart values again. The field-floor check can inspect every remaining case, including cases it ultimately omits.
All modes retain the full plan. Cases and their identities use `O(NV)` storage; random trimming also uses `O(N)` indices.
Topology membership, predicted outputs, calibration and compiler tables add their own storage. The trimming bounds assume
bounded-size values; larger values add copying and serialization work, including the work represented by `C`.

`A` can be exponential in the number of independently varying fields. With `F` Boolean fields, the input space has `2^F`
assignments. Component tables restrict enumeration to the fields each template uses, and branch-and-bound can skip many assignments.
Its bounds rescan those tables, so the worst case can cost more than one exhaustive pass. There is no polynomial-time guarantee.
The maximum search currently allows 4,096 charged evaluations and targets a five-second budget, checked between work units;
source loading, profiling and later topology selection add overhead. An incomplete maximum disables additional percentage sampling.
These are the costs of establishing a maximum. The budget limits effort by allowing an unknown result; it does not turn exact maximization
into a polynomial-time algorithm.

Total runtime adds candidate generation and roughly `K × H` for execution, where `H` is the average Helm/property-test cost.
A completed unfiltered plan has `K = N`. These expressions omit the single defaults check. Planning may dominate: full enumeration grows
with the product of field-domain sizes, while strength-t planning must cover every valid assignment to each set of t fields.
Trimming happens after planning and does not reduce that cost. Failure expansion can increase `K` toward the original plan. Thus filtering reduces typical execution volume without improving
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
| Adaptive | At least `min(M, max(ceil(0.7M), case_floor, protected_count))` | A matching calibration; `M` is the ordinary filtered count |

Adaptive selection can add further cases to meet its field floor. An unmatched chart retains `M`. Unknown topology cases are
retained in addition to the supported-group sum. Each method also checks the baseline. Timeouts can leave planned cases unexecuted,
and failing properties can trigger expansion beyond these initial counts.

If there are `R` supported groups, ordinary filtering retains at least `R` cases. It is useful when many inputs share a group;
when nearly every input has its own group, filtering has little work to remove. Adaptive sampling is useful only if its
additional saved execution exceeds the cost of fresh analysis and selection:

`(ordinary_completed - adaptive_completed) × average_test_cost > additional_planning_cost`

This break-even approximation assumes comparable per-case costs and completed runs. It does not apply directly to censored timings
or when the selected inputs have materially different render costs.
The current load test uses native Helm/render checks without external kubeconform or kubesec validation; those checks can change the per-case cost.

Preserving a representative can preserve a failure **if** exact manifest equivalence is established, the property depends only on
those manifests, the render context is fixed, and the representative is actually tested. Similar topology descriptors alone do not
establish equivalence or guarantee recall.

Under an ideal uniform sample without replacement, with `B` erroneous inputs among `N` fixed inputs, the probability of missing all
of them in `k` tests is `C(N-B, k) / C(N, k)`. This is a model for percentage sampling, not a guarantee supplied by a deterministic seed.
Protected representatives and adaptive field floors make adaptive sampling nonuniform, so that formula cannot be applied to it unchanged.

For independent, uniformly chosen Boolean fields, a specified chain of `g` gates is reached with probability `2^-g`.
Constraints or correlated fields invalidate that calculation. The load fixture has unconstrained Boolean fields; its gate depths
therefore provide controlled changes in branch rarity and symbolic region structure.

See the [real Helm load test](../../studies/filtering/README.md) for runtime, planning, completed-work and phase graphs.
Reproduce it with `hypothesis-helm-benchmark filtering --output benchmarks/runs/filtering --time-limit 9m`.

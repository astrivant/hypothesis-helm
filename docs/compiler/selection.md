# Selection and execution passes

[Compiler](README.md) · [Analysis passes](analysis.md) · [Export passes](exports.md)

These policies use different evidence. Their counters remain separate so a report
can distinguish a tested input, an established equivalent output, an explicit
input rejection, and an input omitted by sampling.

| Policy | Evidence | Effect |
| --- | --- | --- |
| Topology trimming | Predicted output and branch regions. | Retains a sample within each supported region; no success is inferred. |
| Exact-equivalence pruning | Exact match to a successful output witness. | Reuses manifests and replays candidate assertions. |
| Rejection filtering | Chart requirement checked against Helm. | Adjusts or excludes inferred inputs; retains schema conflicts. |
| Failure expansion | An actual test failure in a classified region. | Adds omitted members of that region to the execution queue. |

## Topology trimming

[`topology.py`](../../pkg/hypothesis_helm/compiler/passes/topology.py) specializes
supported templates for each candidate. Inputs with the same symbolic output and
executed branch decisions form a **region**. Selection keeps at least one member
of each region and applies seeded thinning within it.

`--trim-topology N` retains roughly one quarter of each region per step, rounding
up so a nonempty region remains represented. Combined random trimming adds steps
within these same regions. Unsupported candidates stay selected. If the chart
changes during analysis, the pass retains the original selection.

Unlike exact-equivalence pruning, this pass selects cases before observing their
test results. It reports `coverage_guarantee: false`. Baseline handling and other
sampling policies are coordinated by the planner.<sup>[\[1\]](../execution/README.md#optional-trimming)

## Exact-equivalence pruning

[`pruning.py`](../../pkg/hypothesis_helm/compiler/passes/pruning.py) admits a
restricted deterministic chart and schema subset, snapshots its source, and
compiles supported templates. For each schema-valid candidate it constructs a
witness from symbolic output, branch decisions, and the fixed render context.

A matching witness from a previously successful candidate establishes equality
bounds `[0, 0]`. No match, unsupported behavior, or changed source means that Helm
must run. The unproved comparison has bounds `[0, 1]`; different symbolic text
does not prove different parsed manifests.

A representative becomes reusable only after rendering, validation, empty-output
checks, and custom assertions succeed. Reuse supplies fresh copies of its
manifests, replays candidate assertions, and emits the manifest stream. Failures
and pending work cannot authorize reuse. Certificates describe these decisions;
they are local to the run and are not a machine-checked proof of Helm.

The [full contract](../safe-pruning.md) documents schema restrictions, source and
environment checks, bounds, and soundness assumptions. `--prune-equivalent` is
separate from the `--filter` presets.

## Rejection-guided generation

[`rejections.py`](../../pkg/hypothesis_helm/compiler/passes/rejections.py) applies
the conditions found by the [rejection analysis](analysis.md#explicit-rejection-discovery).
With filtering enabled, the first two distinct predicted rejections for each
requirement are checked against Helm. Dependency charts require confirmation for
every predicted rejection because imports and coalescing can alter the context.
A disagreement disables filtering for that requirement. An unexpected native
rendering failure remains a failure.

Automatic exclusions apply to inferred domains. If an authored
`values.schema.json` admits an input that a template rejects, testing retains the
failure and reports a schema/validation conflict. Template guards do not silently
narrow the declared contract, and supplied defaults receive normal validation.

Sampled path tests can try up to 32 single-field adjustments using supplied
defaults, Boolean alternatives, and nearby integers. They preserve the selected
path's value and the original schema. A replacement still has to render and pass
testing. Finite permutation assignments are preserved; rejected assignments have
their own counters. Unknown conditions remain eligible for ordinary testing.

## Failure expansion

[`expansion.py`](../../pkg/hypothesis_helm/compiler/passes/expansion.py) records
region memberships and already scheduled candidate indices. After a real failure,
`FailureExpansion.failed` schedules every omitted member of that region once.
Membership does not imply that those additional inputs will also fail.

The executor still respects its deadline, so expansion may leave unfinished work.
Unsupported inputs have no inferred region to expand. The report distinguishes
initially selected work from additional cases.<sup>[\[2\]](../execution/README.md)

## Where the passes run

[`charts/planning.py`](../../pkg/hypothesis_helm/charts/planning.py) assembles finite
plans using the schema, dependency interactions, trimming, and sampling policies.
The planner applies the requested seeded traversal after selection. Per-path
repository testing uses its own planning route; finite topology regions require a
supported finite domain.

[`charts/candidates.py`](../../pkg/hypothesis_helm/charts/candidates.py) coordinates
schema checks, rejection verification, equivalence lookup, actual rendering, and
assertions. The [execution guide](../execution/README.md) describes mode-specific
parallelism and time limits. Enabling one analysis does not enable every policy
in this page.

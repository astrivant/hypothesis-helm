# Selection and execution passes

<!-- toc:start -->
**Table of contents**

- [Topology filtering](#topology-filtering)
- [Exact-equivalence pruning](#exact-equivalence-pruning)
- [Rejection-guided generation](#rejection-guided-generation)
- [Failure expansion](#failure-expansion)
- [Where the passes run](#where-the-passes-run)
<!-- toc:end -->

[Compiler](README.md) · [Analysis passes](analysis.md) · [Export passes](exports.md)

These policies use different evidence. Their counters remain separate so a report
can distinguish a tested input, an established equivalent output, an explicit
input rejection, and an input omitted by sampling.

| Policy | Evidence | Effect |
| --- | --- | --- |
| Topology filtering | Predicted output and branch regions. | Retains a sample within each supported region; no success is inferred. |
| Exact-equivalence pruning | Exact match to a successful output witness. | Reuses manifests and replays candidate assertions. |
| Rejection filtering | Chart requirement checked against Helm. | Adjusts or excludes inferred inputs; retains schema conflicts. |
| Failure expansion | An actual test failure in a classified region. | Adds omitted members of that region to the execution queue. |

## Topology filtering

[`topology.py`](../../pkg/hypothesis_helm/compiler/passes/topology.py) specializes
supported templates for each candidate. Inputs with the same symbolic output and
executed branch decisions form a **region**. Selection keeps at least one member
of each region and applies seeded thinning within it.

`--filter-topology N` retains roughly one quarter of each region per step, rounding
up so a nonempty region remains represented. Combined random filtering adds steps
within these same regions. Unsupported candidates stay selected. If the chart
changes during analysis, the pass retains the original selection.

Unlike exact-equivalence pruning, this pass selects cases before observing their
test results. It reports `coverage_guarantee: false`. Baseline handling and other
sampling policies are coordinated by the planner.<sup>[\[1\]](../execution/README.md#optional-filtering)

## Exact-equivalence pruning

[`pruning.py`](../../pkg/hypothesis_helm/compiler/passes/pruning.py) admits a
restricted deterministic chart and schema subset, snapshots its source, and
compiles supported templates. For each schema-valid candidate it constructs a
witness from symbolic output, branch decisions, and the fixed render context.

A matching witness from a previously successful candidate establishes equality
bounds `[0, 0]`. No match, unsupported behavior, or changed source means that Helm
must run. The unproved comparison has bounds `[0, 1]`, because different symbolic text
can produce identical parsed manifests.

A representative becomes reusable only after rendering, validation, empty-output
checks, and custom assertions succeed. Reuse supplies fresh copies of its
manifests, replays candidate assertions, and emits the manifest stream. Failures
and pending work cannot authorize reuse. Certificates describe these decisions;
they are local to the run and record the compiler's assumptions and evidence.
See the [soundness argument](../safe-pruning.md#soundness-argument-and-assumptions).

The [full contract](../safe-pruning.md) documents schema restrictions, source and
environment checks, bounds, and soundness assumptions. `--prune-equivalent` is
separate from the `--filter` presets.

## Rejection-guided generation

[`rejections.py`](../../pkg/hypothesis_helm/compiler/passes/rejections.py) applies
the conditions found by the [rejection analysis](analysis.md#explicit-rejection-discovery).
With filtering enabled, the first two distinct predicted rejections for each
requirement are checked against Helm. Dependency charts, inferred enum choices and
[modeled transformations](analysis.md#transformed-input-domains)
require confirmation for every predicted rejection. Imports and coalescing can
alter dependency contexts; enum guidance must confirm the actual rejected value.
A disagreement disables filtering for that requirement. An unexpected native
rendering failure remains a failure.

Automatic exclusions apply to inferred domains. A partial `values.schema.json`
can leave a preset field undeclared; a supported helper can guide that field.
Explicitly declared fields retain schema/validation conflicts as failures.
References, schema composition and ambiguous declarations conservatively prevent
enum guidance. Template guards do not silently narrow an authored domain, and
supplied defaults receive normal validation.

Sampled path tests search at most 48 distinct candidates, with up to three related
field changes and at most 16 alternatives from each intermediate candidate. They
use supplied defaults, Boolean alternatives, nearby integers, `example` for an
empty string, and bounded list lengths using existing elements. Source-backed enum choices
and verified preimage proposals are tried first. Enum choices use a deterministic
order derived from the candidate. This keeps
the resource enabled when a valid preset suffices. A sampled scalar target may
change to one of those choices or a verified preimage; other selected paths remain protected. Every
replacement still has to satisfy the generation schema, render and pass testing.
The search reevaluates guards after each change, including requirements that were
previously hidden by Boolean short-circuiting. It can satisfy several requirements
together while keeping the selected feature enabled. This is a bounded search;
it may miss a valid configuration or one requiring different replacement values.
Finite permutation assignments are never repaired; rejected assignments
have their own counters. Unknown conditions remain eligible for ordinary testing.

## Failure expansion

[`expansion.py`](../../pkg/hypothesis_helm/compiler/passes/expansion.py) records
region memberships and already scheduled candidate indices. After a real failure,
`FailureExpansion.failed` schedules every omitted member of that region once.
Membership does not imply that those additional inputs will also fail.

The executor still respects its deadline, so expansion may leave unfinished work.
Unsupported inputs have no inferred region to expand. The report distinguishes
initially selected work from additional cases.<sup>[\[2\]](../execution/README.md)

## Where the passes run

[`charts/testing/planning.py`](../../pkg/hypothesis_helm/charts/testing/planning.py) assembles finite
plans using the schema, dependency interactions, filtering, and sampling policies.
The planner applies the requested seeded traversal after selection. Per-path
repository testing uses its own planning route; finite topology regions require a
supported finite domain.

[`charts/testing/candidates.py`](../../pkg/hypothesis_helm/charts/testing/candidates.py) coordinates
schema checks, rejection verification, equivalence lookup, actual rendering, and
assertions. The [execution guide](../execution/README.md) describes mode-specific
parallelism and time limits. Enabling one analysis does not enable every policy
in this page.

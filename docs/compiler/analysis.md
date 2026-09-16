# Analysis passes

<!-- toc:start -->
**Table of contents**

- [Branch knowledge](#branch-knowledge)
- [Input inventory](#input-inventory)
- [Dependency discovery and activation](#dependency-discovery-and-activation)
- [Explicit rejection discovery](#explicit-rejection-discovery)
- [Maximum output complexity](#maximum-output-complexity)
- [Sampling profile](#sampling-profile)
<!-- toc:end -->

[Compiler](README.md) · [Syntax trees](syntax-trees.md) · [Selection passes](selection.md)

These passes describe what the chart can consume or produce. Their results guide
testing and populate audits; an analysis result alone is not a passed chart test.

## Branch knowledge

[`branches.py`](../../pkg/hypothesis_helm/compiler/passes/branches.py) narrows possible values inside supported conditions,
removes contradictory nested branches, and merges the surviving alternatives before analyzing later statements.
It runs after literal folding in the exact-equivalence compiler, which is also used by maximum-output analysis.
The [branch knowledge lattice](lattice.md) defines the operations, supported conditions and uncertainty rules.
Audits expose source-level decisions under `complexity.branch_analysis`; test reports include them under `pruning.branch_analysis`.

## Input inventory

[`inputs.py`](../../pkg/hypothesis_helm/compiler/passes/inputs.py) compares three
sources: supplied values, declared schema fields, and references found in
templates. `InputInventory.build` binds these paths to the shared values model
and records their source locations.

The result separates referenced fields missing from values or schema from supplied
fields with no known reference. Dynamic map access, unresolved helper contexts,
and dependency forwarding remain explicit uncertainties. An unmatched field is
not automatically unused.

`known_fields` retains the most specific named references: a parent container is
not counted again when a referenced descendant is known. This supplies a lower
bound for input coverage, not proof that every possible input path was discovered.
`FieldCoverage` records which of those paths changed during testing.<sup>[\[1\]](../inputs/README.md)

## Dependency discovery and activation

[`dependencies.py`](../../pkg/hypothesis_helm/compiler/passes/dependencies.py)
reads chart metadata and installed child charts, including archives. It records
child inputs under their dependency name or alias, ordered Boolean conditions,
shared tag controls, and the parent dependencies that must also be enabled.
The data records live in
[`asts/dependencies.py`](../../pkg/hypothesis_helm/compiler/asts/dependencies.py).

This catches enablement settings that appear only in `Chart.yaml`. For a selected
child field, generation can propose a context that enables the child while
preserving that field's chosen value and the parent schema. The original context
also remains eligible because parent templates can read child values even when
the child is disabled. Finite planning proposes corresponding interaction groups
within its existing group-size budgets.

Missing child sources, ambiguous imports, and unsupported forwarding are reported.
Activation states are predictions checked through Helm execution. They do not
authorize skipping renders: charts with dependencies are outside the current
exact-equivalence and topology proof contract.<sup>[\[2\]](../scanning/README.md#discovery-and-testing)

## Explicit rejection discovery

[`Contracts.build`](../../pkg/hypothesis_helm/compiler/asts/contracts.py) locates
calls to `fail` and `required` in parsed expressions. It follows supported named
helper calls and evaluates the branches that lead to those calls for a candidate.
It does not classify failures by searching comments or error-message keywords.

A prediction identifies the requirement, its location, and the input values read
while reaching it. Unsupported expressions, ambiguous helper definitions, dynamic
contexts, and recursion beyond the evaluator's limit cannot establish a rejection.
The [rejection policy](selection.md#rejection-guided-generation) verifies predictions
with Helm before using them to filter inferred inputs.

## Maximum output complexity

[`complexity.py`](../../pkg/hypothesis_helm/compiler/passes/complexity.py) searches
for the largest supported manifest structure that allowed values can produce.
Its score is **breadth × depth**: breadth counts the largest number of nodes on
any one level of the output tree; depth counts the longest path from the bundle
root. Resources, field values, and array entries contribute nodes. Longer scalar
text does not increase the score.<sup>[\[3\]](../inputs/README.md)

The deterministic search proceeds as follows:

1. Split a supported finite input domain into factors, each with allowed choices.
2. Identify the factors each template reads and evaluate that template's local
   assignments. Store the resulting output shapes in a component table.
3. Assign factors in a stable order that prioritizes shared uses and conditions.
   For each partial assignment, compute an upper bound from compatible table rows.
4. Skip a subtree when its bound cannot improve the best valid complete output
   already found. Validate complete assignments and their assembled resource
   bundles before accepting a new best result.

This is **branch-and-bound**: a bound can rule out many assignments without
visiting each one. It does not assume that enabling every Boolean independently
produces the largest valid chart.

Complete component tables and a completed search establish `compiled-maximum`
within the supported model. Unsupported operations or an exhausted budget produce
`unknown`; any retained lower bound comes from a checked complete configuration.
The analysis uses compiled output, without invoking Helm or Kubernetes API schema
validation. It measures potential output structure, not bug count or runtime.
[`compiler/complexity.py`](../../pkg/hypothesis_helm/compiler/complexity.py) supplies
the tree metric and size-based theoretical ceiling.

## Sampling profile

[`sampling.py`](../../pkg/hypothesis_helm/compiler/passes/sampling.py) combines a
fresh complexity result with input domain sizes, scalar kinds, conditional nesting
depth, and the largest number of distinct direct values references in a template.
The latter is reported as `interaction_order`; it is a structural descriptor,
not a measured causal interaction between every referenced input.

A **gate** in these records means a conditional decision. Gate depth counts how
many such decisions can enclose a template statement. A source fingerprint binds
the profile to the analyzed chart. Unknown complexity or changing source bytes
prevents a supported profile.

The adaptive sampling policy uses this profile to seek applicable benchmark
calibration. `sampling.py` describes the chart; it does not choose a sample size
by itself. Unsupported or unmatched profiles retain ordinary filtering instead
of assuming a bug-discovery rate.<sup>[\[4\]](../adaptive-filtering/README.md)

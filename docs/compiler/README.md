# Compiler

<!-- toc:start -->
**Table of contents**

- [Flow](#flow)
- [Guide](#guide)
- [Code map](#code-map)
- [Measured output sensitivity](#measured-output-sensitivity)
<!-- toc:end -->

[Documentation](../README.md) · [Architecture](../architecture/README.md) · [Project](../../README.md)

The compiler identifies the values a chart uses, the conditions that change its
output, and the relationships between them. Test planning uses this information
to choose inputs. Helm renders those inputs, and validators check the manifests.

A **pass** is an analysis or transformation with a particular job, such as finding
input references or grouping inputs by their predicted output. The implementation
shares syntax trees and a typed values model across these passes. Commands invoke
the passes required for the selected operation.

## Flow

The arrows show how information reaches planning and execution. Dashed arrows
show optional reuse or feedback from a running test.

```mermaid
flowchart TD
    Templates[Helm templates] --> Parse[Parse template structure]
    Values[Values and values schema] --> Model[Build typed values model]
    Metadata[Chart metadata and installed dependencies] --> Dependencies[Resolve dependency controls and child inputs]
    Parse --> Inventory[Inventory referenced inputs]
    Model --> Inventory
    Dependencies --> Inventory
    Parse --> Contracts[Identify explicit fail and required conditions]
    Parse --> Branches[Narrow branch facts and merge alternatives]
    Model --> Branches
    Branches --> Output[Compile supported output behavior]
    Inventory --> Plan[Generate and select candidate values]
    Output --> Plan
    Plan --> Check[Check one candidate]
    Contracts --> Check
    Output --> Check
    Check --> Helm[Render with Helm]
    Check -. proved equal to a successful input .-> Reuse[Reuse validated manifests]
    Check --> Rejected[Record an established input rejection]
    Helm --> Validate[Validate manifests and run assertions]
    Reuse --> Assertions[Replay candidate assertions and manifest stream]
    Validate --> Report[Record results and coverage]
    Assertions --> Report
    Rejected --> Report
    Validate -. failure with expansion enabled .-> Expand[Schedule omitted inputs from the same region]
    Expand -. additional work .-> Plan
```

The rejection route has its own Helm verification policy. It does not turn a
template rejection into a passing test. Reuse requires the separate
exact-equivalence contract. Unsupported analysis keeps the relevant candidate
eligible for execution; it cannot establish a successful result.<sup>[\[1\]](selection.md)</sup>

## Guide

| Page | What it explains |
| --- | --- |
| [Syntax trees and values model](syntax-trees.md) | Parsed templates, field types, and representations for discovery and proof. |
| [Helm builtin functions](functions.md) | Complete pinned function inventory, effects, supported models and conservative fallbacks. |
| [Decisions, panel by panel](decisions.md) | Matched diagrams showing why branches are visited, inputs retained, or work skipped. |
| [Analysis passes](analysis.md) | Input inventory, dependencies, rejection conditions, maximum output complexity, and sampling profiles. |
| [Branch knowledge lattice](lattice.md) | Possible values, branch narrowing, merging and conservative handling of unknown operations. |
| [Selection and execution passes](selection.md) | Filtering, equality proofs, rejection filtering, and failure expansion. |
| [Export passes](exports.md) | Input inventories, topology graphs, minimal values, and their verification records. |
| [Exact-equivalence contract](../safe-pruning.md) | Supported Helm operations, equality bounds, assumptions, and proof evidence. |

Audit consumes analysis results without running the property-test suite. Test and
scan use those results to plan execution; export commands also use them to produce
artifacts. The [input guide](../inputs/README.md) describes the corresponding CLI
options and report fields.

## Code map

| Location | Responsibility |
| --- | --- |
| [`compiler/asts/`](../../pkg/hypothesis_helm/compiler/asts) | Tokens, template nodes, rejection expressions, and dependency records. |
| [`compiler/passes/`](../../pkg/hypothesis_helm/compiler/passes) | Analyses, selection policies, and exports described in this guide. |
| [`compiler/constants.py`](../../pkg/hypothesis_helm/compiler/constants.py) | Shared function families, aliases, numeric bounds, and typed zero factories. |
| [`passes/discovery_functions/`](../../pkg/hypothesis_helm/compiler/passes/discovery_functions) | A small dispatcher with separate scalar, collection, and selection handlers. |
| [`asts/native_operations.py`](../../pkg/hypothesis_helm/compiler/asts/native_operations.py) | Bounded, cached calls to the selected Helm binary for Go regexes and serialization. |
| [`asts/transformations.py`](../../pkg/hypothesis_helm/compiler/asts/transformations.py) | Concrete operations, grouped into formatting, selection, collections, text, and integer handlers. |
| [`passes/domain_interpreter.py`](../../pkg/hypothesis_helm/compiler/passes/domain_interpreter.py) | Symbolic evaluation with separate helpers for calls, mutations, and branch joins. |
| [`passes/domain_constraints.py`](../../pkg/hypothesis_helm/compiler/passes/domain_constraints.py) | Backward constraint propagation for input paths, maps, transformations, and selected branches. |
| [`schemas/model.py`](../../pkg/hypothesis_helm/schemas/model.py) | Shared schema-derived values tree and attrs/cattrs conversion. |
| [`charts/inspection/templates.py`](../../pkg/hypothesis_helm/charts/inspection/templates.py) | Scope-aware reference discovery using the action tree. |
| [`charts/testing/planning.py`](../../pkg/hypothesis_helm/charts/testing/planning.py) | Finite candidate planning and selection orchestration. |
| [`charts/testing/candidates.py`](../../pkg/hypothesis_helm/charts/testing/candidates.py) | Candidate checks and verified witnesses. |

These modules analyze Helm; they do not implement its full rendering language.
Each result states its supported scope and any unresolved behavior.

Function-family constants describe the operations these handlers support. The source-derived
[`builtins.py`](../../pkg/hypothesis_helm/compiler/builtins.py) registry remains the source of upstream function effects
and result shapes; knowing a result's shape does not prove its value or make it safe to prune.

When changing a handler, keep lazy helper and Boolean calls ahead of eager argument evaluation. Preserve scope restoration
after helper failures, and retain unknown results instead of substituting Python coercions. Inline comments mark these
boundaries in the evaluators.

## Measured output sensitivity

[Mutation sensitivity](sensitivity.md) measures individual changes, pairwise interactions and cumulative output displacement
with Helm. This is an optional runtime diagnostic; it does not weaken the compiler equivalence requirements for pruning.

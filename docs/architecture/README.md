# Architecture

[Documentation](../README.md) · [Project](../../README.md)

```mermaid
flowchart LR
    Values[values.yaml] --> Coalesce[Round-trip YAML coalescing]
    Templates[Helm templates] --> AST[Template action AST]
    AST --> Coalesce
    AST --> Contracts[Explicit rejection contracts]
    Schema[values.schema.json] --> Paths[Schema path enumeration]
    Coalesce --> Paths
    Paths --> Strategies[Typed Hypothesis strategies]
    Strategies --> Tests[Generated Python tests]
    Contracts --> Guidance[Dependent-field generation and rejection witness checks]
    Guidance --> Helm
    Tests --> Helm[Temporary chart rendering]
    Helm --> Assertions[Resource assertions and counterexamples]
```

## Input discovery and test generation

The compiler resolves template references to values paths and combines those
references with supplied values and schema constraints. Each supported path gets
a typed input-generation strategy. Generated Python properties use those strategies
to construct complete inputs that satisfy the values schema.

## Execution and validation

Each property tests generated values against an isolated copy of the chart. Helm
renders the templates, then resource assertions and optional Kubernetes schema
validation check the output. When a check fails, Hypothesis attempts to simplify
the failing input while preserving the failure.

A property can test multiple inputs and render multiple manifests. JUnit records
the property's result; execution reports retain the input and render counts.
Selection, caching, traversal, and sharding determine which properties execute.

The chart runner coordinates separate modules: `charts/model.py` owns loaded contracts,
`charts/planning.py` builds finite plans and estimates, `charts/candidates.py` evaluates one candidate,
`charts/rendering.py` owns Helm rendering, and `charts/audit.py` assembles audit findings.

`execution/processes.py` owns worker process groups until descendants have stopped and direct children
have been joined. Communication errors trigger cleanup; a failed cleanup retains the unresolved ownership
record while other children are still joined. Benchmark commands pass arguments and chart workspace owners
explicitly, without changing the process command line or selecting a workspace through ambient context.

## Syntax trees and compiler passes

`pkg/hypothesis_helm/compiler/asts/` holds template nodes, expression trees, helper
definitions, and conservative evaluators. Discovery and symbolic compilation share one lexer. Template syntax forms a tree; named
helper calls connect those trees into a graph. Source filenames and line numbers
connect analysis results back to chart code.

`pkg/hypothesis_helm/compiler/passes/` holds input discovery, topology analysis,
equivalence pruning, rejection-guided generation, and export passes. Constants
remain at the compiler root. Rejection analysis navigates parsed nodes rather than searching
comments or message strings for words such as `fail`.

Dependency records live in `compiler/asts/dependencies.py`; their discovery and
generation pass lives in `compiler/passes/dependencies.py`. The pass reads installed
child directories and archives, qualifies child inputs by alias, and records ordered
Boolean conditions and shared tag controls. It discovers these controls even when
they appear only in chart metadata. Nested dependencies retain their ancestor gates.

Path generation proposes an enabled context for child settings while preserving
the selected value and original parent-schema constraints. The original context
remains eligible because parent templates may read child values independently of
activation. Finite planning proposes groups containing one child field and its
activation chain; existing group-size budgets still apply.

Graph exports connect controls to dependency instances and child templates.
Activation states are predictions, and every scheduled candidate is rendered by
Helm. Missing or ambiguous sources, unresolved imports, and unsupported forwarding
remain explicit limitations. Dependency activation never authorizes skipping a
render: exact-equivalence and topology proofs still exclude charts with dependencies.

With `--filter`, local tests and repository scans evaluate supported branches
leading to explicit `fail` and `required` calls, including statically named helper
calls. The first two distinct rejected inputs for each requirement are checked
against Helm; charts with dependencies require native confirmation for every
predicted rejection because coalescing and imports may alter the input context.
A different native outcome disables that requirement's filtering;
an unexpected rendering failure remains a failure.

Automatic exclusions apply to inferred input domains. When an authored
`values.schema.json` admits an input that a template rejects, the tool retains the
failure and reports the requirement as a schema/validation conflict. Template
guards do not silently narrow the declared contract.

Sampled path tests try at most 32 single-field adjustments using supplied defaults,
Boolean alternatives, and adjacent integers. They preserve the selected path and
the original schema, then render and test any replacement. Finite permutation
assignments are preserved; rejected assignments are counted separately. Supplied
defaults always receive normal validation.

Unknown expressions, dynamic helper contexts, unsupported scope mutation, and
recursive helper calls beyond the bounded evaluator remain ordinary test inputs.
These contracts describe chart-authored validation, not proof that its rules are
correct. This generation policy is separate from proved output equivalence.

## Finite permutation planning

When fields have finite value choices, the planner can select complete input
configurations for the requested interaction coverage or enumerate a small space.
Optional trimming reduces the planned cases. Exact-equivalence pruning skips a
render only when the compiler establishes that its output matches an input that
has already passed validation.

See [execution and coverage](../execution/README.md), the
[pruning contract](../safe-pruning.md), and the
[introductory example](../../README.md#example-catch-a-failure-hidden-by-defaults).

# Compiler decisions, panel by panel

<!-- toc:start -->
**Table of contents**

- [Which branch does the compiler visit?](#which-branch-does-the-compiler-visit)
- [When may an equal output skip Helm?](#when-may-an-equal-output-skip-helm)
- [Why does an unsupported branch sometimes still permit analysis?](#why-does-an-unsupported-branch-sometimes-still-permit-analysis)
- [Why keep some region members and restore others later?](#why-keep-some-region-members-and-restore-others-later)
- [Why can the same template rejection have different outcomes?](#why-can-the-same-template-rejection-have-different-outcomes)
- [Why can the maximum-complexity search drop a whole subtree?](#why-can-the-maximum-complexity-search-drop-a-whole-subtree)
<!-- toc:end -->

[Compiler](README.md) · [Analysis passes](analysis.md) · [Selection passes](selection.md)

Each row of panels follows one decision. Green marks an executed or retained
route, gray marks a skipped route, and amber marks work that still needs Helm.
The labels carry the same meaning without color. These are explanatory diagrams,
not measured benchmark results.

## Which branch does the compiler visit?

Consider a ConfigMap whose `data.label` is the supplied `label` when `enabled` is
true, and the literal `off` otherwise. Its schema allows a Boolean `enabled` and
the labels `blue` and `green`. The rest of the manifest is fixed.

The compiler walks only the active branch **for this candidate**. The other
branch remains part of the chart and can be visited by a later candidate.

```mermaid
flowchart LR
    subgraph A["A. Both branches exist in the template"]
        direction TB
        a{enabled?} -->|true| at[Read label]
        a -->|false| af[Emit literal off]
    end
    subgraph B["B. Candidate: enabled=false, label=blue"]
        direction TB
        b{enabled is false} -. inactive .-> bt[Skip label lookup]
        b -->|active| bf[Emit literal off]
    end
    subgraph C["C. Candidate: enabled=true, label=blue"]
        direction TB
        c{enabled is true} -->|active| ct[Read label and emit blue]
        c -. inactive .-> cf[Skip literal off]
    end
    A --> B --> C
    classDef active fill:#e3f3e8,stroke:#247047,color:#163b29
    classDef skipped fill:#eeeeee,stroke:#777777,color:#444444,stroke-dasharray:5 5
    class bf,ct active
    class bt,cf skipped
```

In panel B, changing `label` cannot change this template's output because that
lookup never executes. The candidate still contains `label`, and schema
validation still checks it. In panel C, `label` contributes to the output witness.
This is candidate specialization, not a permanent deletion of a values path.
See [output compilation stages](syntax-trees.md#output-compilation-stages).

## When may an equal output skip Helm?

Use two inputs from the same false branch: A has `label=blue`, B has `label=green`.
Both predict `off`. Assume the complete chart and schema satisfy the
[equivalence contract](../safe-pruning.md), and all other output and render context
are identical. Equality alone is insufficient: a successful witness must exist.

```mermaid
flowchart LR
    subgraph P["A. No successful witness yet"]
        direction TB
        p1[Input A predicts off] --> p2[No validated representative]
        p2 --> p3[Render A and run its checks]
    end
    subgraph F["B. If A fails"]
        direction TB
        f1[A failed validation] --> f2[Do not remember A as successful]
        f2 --> f3[If B is attempted, it still needs Helm]
    end
    subgraph S["C. If A passes"]
        direction TB
        s1[A passed every required check] --> s2[B has the same exact witness]
        s2 --> s3[Skip Helm for B; copy A manifests]
        s3 --> s4[Run B assertions and emit its manifests]
    end
    P --> F
    P --> S
    classDef render fill:#fff3d6,stroke:#926000,color:#513900
    classDef reuse fill:#e3f3e8,stroke:#247047,color:#163b29
    class p3,f3 render
    class s3,s4 reuse
```

Panel C establishes distance bounds `[0, 0]` against A. Without that successful
match, the bounds remain `[0, 1]` and Helm runs. A candidate with `enabled=true`
has a different branch signature; this witness cannot justify its reuse.
Custom assertions on B still run and can fail.

## Why does an unsupported branch sometimes still permit analysis?

Now suppose the true branch uses `tpl`, which the output-equivalence evaluator
does not interpret. An ordinary unsupported expression in an inactive branch
need not prevent analysis of the active one. Reaching it does.

```mermaid
flowchart LR
    subgraph I["A. Candidate keeps tpl inactive"]
        direction TB
        i{enabled=false} -. inactive .-> ix[tpl expression: not visited]
        i -->|active| iy[Known literal output]
        iy --> iz[Equality analysis can continue]
    end
    subgraph R["B. Candidate reaches tpl"]
        direction TB
        r{enabled=true} -->|active| rx[tpl expression: unsupported]
        r -. inactive .-> ry[Literal output: not visited]
        rx --> rz[Output unknown: render with Helm]
    end
    I --> R
    classDef active fill:#e3f3e8,stroke:#247047,color:#163b29
    classDef skipped fill:#eeeeee,stroke:#777777,color:#444444,stroke-dasharray:5 5
    classDef unknown fill:#fff3d6,stroke:#926000,color:#513900
    class iy,iz active
    class ix,ry skipped
    class rx,rz unknown
```

This rule does not extend to every unsupported construct. Named definitions and
`block` can affect parsing across templates, so they disable the current proof
contract even when apparently nested in an inactive branch. Dependency charts are
also outside that contract. An unknown analysis result is never a passing test.

## Why keep some region members and restore others later?

Topology trimming selects tests before their outcomes are known. Suppose four
eligible inputs share a supported output-and-branch region, another input belongs
to a second region, and one input cannot be classified. One topology trim step
keeps one of the four, the second region's sole member, and the unknown input.
The chosen member depends on the seed; A is the illustrative choice here.

```mermaid
flowchart LR
    subgraph G["A. Classify the eligible inputs"]
        direction TB
        g1[Region 1: A, B, C, D]
        g2[Region 2: E]
        gx[Unclassified: X]
    end
    subgraph K["B. Trim within each region"]
        direction TB
        k1[Keep A; omit B, C, D]
        k2[Keep E: preserve its region]
        kx[Keep X: analysis is unknown]
    end
    subgraph E["C. A fails and expansion is enabled"]
        direction TB
        e1[Observed failure for A] --> e2[Schedule B, C, D once each]
        e2 --> e3[Render and test each within remaining time]
    end
    g1 --> k1
    g2 --> k2
    gx --> kx
    k1 --> e1
    classDef kept fill:#e3f3e8,stroke:#247047,color:#163b29
    classDef unknown fill:#fff3d6,stroke:#926000,color:#513900
    class k1,k2,e2 kept
    class gx,kx,e3 unknown
```

Panel B makes no claim that the omitted cases passed. Panel C also makes no claim
that they will fail; their membership only explains why testing expands there.
If A passes, this expansion policy does not restore B, C, and D. A timeout can
leave restored cases unfinished. See [topology trimming](selection.md#topology-trimming)
and [failure expansion](selection.md#failure-expansion).

## Why can the same template rejection have different outcomes?

Suppose a chart explicitly rejects an input that disables a required component.
The treatment depends on the authored contract, not just the error message.
The following panels start from a supported rejection prediction whose required
native verification agrees.

```mermaid
flowchart LR
    subgraph Inferred["A. Input domain was inferred"]
        direction TB
        a1[Template explicitly rejects this input] --> a2[Try a permitted adjustment]
        a2 -->|replacement found| a3[Render and test the replacement]
        a2 -->|none found| a4[Record filtered rejection, not a pass]
    end
    subgraph Declared["B. Authored schema admits this input"]
        direction TB
        b1[Template explicitly rejects this input] --> b2[Schema and template disagree]
        b2 --> b3[Keep the failure in the report]
    end
    Inferred --> Declared
    classDef check fill:#fff3d6,stroke:#926000,color:#513900
    classDef retained fill:#e3f3e8,stroke:#247047,color:#163b29
    class a2,a3 check
    class a4,b3 retained
```

An adjustment cannot overwrite the selected path or violate the original schema.
If Helm contradicts a prediction, that requirement's filtering is disabled.
See [rejection-guided generation](selection.md#rejection-guided-generation) for
the two-witness policy and the stricter dependency-chart rule.

## Why can the maximum-complexity search drop a whole subtree?

The search assigns allowed values incrementally. A **partial assignment** leaves
some fields undecided. Its upper bound must cover every valid completion, so it
can be deliberately loose. The scores below illustrate the comparison; they are
not measurements from a particular chart.

```mermaid
flowchart LR
    subgraph Before["A. Partial assignments remain"]
        direction TB
        root[Unassigned inputs] --> left[Region L: upper bound 12]
        root --> right[Region R: upper bound 20]
        best[Best checked complete assignment: score 14]
    end
    subgraph After["B. Compare each bound with 14"]
        direction TB
        left2[Region L: at most 12] --> drop[Skip its remaining assignments]
        right2[Region R: may reach 20] --> visit[Visit higher-bound assignments first]
    end
    left --> left2
    right --> right2
    classDef skipped fill:#eeeeee,stroke:#777777,color:#444444,stroke-dasharray:5 5
    classDef retained fill:#e3f3e8,stroke:#247047,color:#163b29
    class left2,drop skipped
    class right2,visit retained
```

Nothing under L can improve 14, so dropping it preserves the maximum being sought.
R's bound of 20 does not establish that an assignment actually reaches 20; the
search must check feasible completions. A bound equal to 14 can also be dropped
when finding one maximum, rather than all maximizing assignments.

This pruning saves **analysis work**. It does not remove chart tests merely
because their outputs are smaller. The [complexity pass](analysis.md#maximum-output-complexity)
must finish within its supported model to report an established maximum.

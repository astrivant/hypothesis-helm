# Exact-equivalence pruning

This option skips a Helm render only when the compiler can establish that the
input would produce exactly the same parsed manifests as an input that already
passed validation. If the compiler cannot establish that match, Helm runs.
This differs from trimming or sampling, which deliberately leave some inputs
untested without proving their outputs equal.<sup>[\[1\]](execution/README.md#optional-trimming)</sup>

```sh
helm hypothesis test ./chart --permutations 2 --prune-equivalent
helm hypothesis test ./chart --prune-equivalent --dry-run
```

Pruning is opt-in and applies to whole-chart testing. Without an explicit coverage
mode, `--prune-equivalent` selects finite pairwise/automatic exhaustive planning.
`--whole-chart --prune-equivalent` applies the same conservative rule to sampled
candidates. Per-path suites do not enable this compiler.

## Contract and distance

Here, **distance** answers one question: are the complete parsed outputs equal?
Equal outputs have distance 0; different outputs have distance 1. This is not a
percentage similarity score. The rule applies to the configurations selected for
this run; it does not expand that selection to cover other allowed inputs.<sup>[\[2\]](usage.md#interaction-coverage)</sup>

For the generated candidate set D, let R(x) be the complete parsed manifest bundle
from a successful Helm invocation in a fixed chart and renderer environment.
The distance is discrete: d(a,b) = 0 if the bundles are exactly equal, and 1
otherwise. The threshold is fixed at epsilon = 0.5, so no distinct output may be
intentionally discarded. This is not a weighted similarity metric.

The runtime retains a subset S of **actually rendered, successful** candidates.
A candidate may skip Helm only when its symbolic equality key matches a member
of S. The resulting guarantee is:

    for every successfully covered x in D,
    there exists a successfully rendered s in S with R(x) = R(s).

This does not claim coverage of inputs outside D. Testing every pair of input
choices does not necessarily produce every possible output. Full finite
enumeration supplies every configuration in the supported finite input space.

## Compiler stages

The compiler uses a structured representation of the template, called an
**intermediate representation (IR)**, to track the text and values each branch
would output. **Symbolic** evaluation means reasoning about that output from the
template and candidate values, before asking Helm to render it. **Opaque** code
is code this analysis cannot interpret; reaching it forces a render.<sup>[\[3\]](compiler/syntax-trees.md)</sup>

1. **Parse/lower:** a separate text-preserving lexer and balanced-block IR retain
   literal output, source locations, Go whitespace trimming and opaque actions.
   The existing discovery AST is not used as a proof of execution behavior.
2. **Constant propagation and dead branches:** literal `true`/`false` conditions
   select their reachable branch. Candidate specialization binds supported field
   references and eliminates only branches proved inactive for that candidate.
   Chart defaults are never assumed constant across candidate assignments.
3. **Unused inputs:** the equality key contains only executed field influences;
   unreferenced and inactive fields disappear from that key. They remain in the
   full candidate and still undergo schema validation.
4. **Control-flow partitions:** executed Boolean decisions form per-file path
   signatures. Representatives are compared within the same signature.
5. **Symbolic output:** literal text, typed scalar identities and fixed context
   references form an output sequence. This avoids reimplementing Go scalar
   formatting: equal typed scalars necessarily print identically. The compiler
   does not predict or parse approximate YAML output.
6. **Influence matrix:** shared `ValuesModel` nodes map input paths to surviving
   template output spans, annotated as control or scalar-copy influences. These
   are source spans, not guessed Kubernetes JSON pointers. The matrix is partial
   where code is opaque and cannot authorize pruning on its own.
7. **Bounds:** a matching successful witness yields [L,U] = [0,0]. Otherwise the
   compiler returns the sound but uninformative interval [0,1]. U < epsilon
   discards the Helm invocation; all unproved comparisons render. The bounds
   dispatcher also supports L > epsilon, but this first compiler does not claim
   positive separation merely because symbolic text differs: distinct YAML text
   can still describe identical manifests.

The current subset supports literal text, direct declared `.Values.a.b` scalar
lookups (Boolean, integer, string), Boolean `if`/`else`, Boolean constants, `not` on Boolean paths,
and `eq`/`ne` between a direct values path and a same-type unescaped string or Boolean literal, plus
fixed `.Release.Name`/`.Release.Namespace` output references. Equal output text
is a stronger sufficient condition than equal parsed manifests, so some genuinely
equivalent candidates conservatively render.

## Soundness argument and assumptions

For an admitted chart and candidate, the proof is by structural induction on the
executed IR. Literal nodes emit the same bytes. Scalar nodes with equal typed
values produce equal Go template output. Fixed context nodes have equal renderer
inputs. Equal Boolean branch decisions select the same inductively equivalent
subtrees. Supported same-type string/Boolean equality and Boolean negation have the same deterministic predicate results.
Before specialization, the [branch knowledge pass](compiler/lattice.md) narrows schema-admitted possibilities,
removes contradictory alternatives and merges branch exits. Unknown operations discard facts rather than preserving stale assumptions.
Concatenation and lexical whitespace trimming preserve equality.
Consequently, equal per-file output witnesses imply the same complete manifest
bundle under the fixed Helm renderer. An opaque executed node prevents the
induction and forces rendering.

Validation is part of the contract. The compiler independently validates the
candidate against its frozen original schema before lookup. It admits only a
conservative common subset of Python/Helm schema constraints. Formats, regexes,
references, compositions, unknown extensions, floating-point numeric constraints
and inexact enum constants force rendering. Integer values and bounds are limited
to the exactly representable JSON range. Null deletion and map/scalar coalescing
conflicts force rendering. YAML defaults must have compatible 1.1/1.2 resolution
and unambiguous scalar forms; directives, aliases, merge keys and application tags
are rejected. Empty release names or namespaces also disable pruning.
These gates prevent schema errors or YAML interpretation differences from being
hidden by output equivalence.

Subcharts, library charts, `.helmignore`, symlinks, parse-global named definitions
and oversized chart snapshots are outside the proof contract. Executed loops,
`with`, function pipelines, `include`, `tpl`, mutation, randomness, time and
`lookup` are opaque. These restrictions reduce pruning opportunities, not the
candidate coverage. Safely inactive ordinary opaque expressions may be eliminated;
parse-global definitions are rejected even in apparently dead code.

Certificates assume trusted, unchanged Helm/validator implementations, immutable
validator schema snapshots, and no concurrent filesystem mutation during an
individual render/proof operation. Exact chart bytes are checked before lookup
and before committing representatives; renderer options and the process environment
are part of the equality key. Changed observed inputs invalidate reuse. The
fingerprint in the report is for auditing; hash collisions cannot authorize a
prune because equality decisions use complete canonical keys and exact source bytes.

This is a handwritten conservative semantic model with differential Helm tests,
not a machine-checked proof of Helm or its dependencies. Reports explicitly set
`formally_verified: false`. OS failures, resource exhaustion, nondeterministic
custom binaries, concurrent mutation and compiler implementation bugs are outside
the mathematical equality argument. Unsupported behavior is never estimated with
embeddings or probabilistic rejection.

## Runtime behavior and evidence

A candidate is committed as a representative only after actual rendering,
standard validation, the empty-output check and all custom assertions succeed.
Failed and pending candidates cannot authorize discards. Every pruned candidate
replays fresh copies of the representative's pristine manifests through its
empty-output check, custom assertions and manifest stream. Stateful assertions
can still fail; callback mutation cannot contaminate later candidates.

`report.json` includes `pruning` with:

- actual renderer invocation attempts and pruned candidate counts;
- compiler version, chart fingerprint, scope and fallback reasons;
- the sparse input-to-output influence matrix;
- source-level branch narrowing and removal decisions;
- individual candidate/representative iteration links, exact bounds, partitions,
  live inputs and eliminated inputs.

Ordinary progress counts completed **candidate checks**, including equivalence
proofs, rather than only Helm invocations. Render-hash counters count actual
rendered bundles. The original input interaction plan is retained. Dry runs
compile and report the static contract but neither render nor claim certificates.
Certificates remain run-local and are not restored as successes from history.

The lexical and evaluation rules are based on the [Go text/template contract](https://pkg.go.dev/text/template).
The merge boundary follows Helm's [values-file semantics](https://docs.helm.sh/docs/v3/chart_template_guide/values_files/).

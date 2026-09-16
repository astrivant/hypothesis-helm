# Input inventory and minimal values

<!-- toc:start -->
**Table of contents**

- [Declared and inferred types](#declared-and-inferred-types)
- [Inventory values](#inventory-values)
- [Inspect the baseline](#inspect-the-baseline)
- [Verification record](#verification-record)
- [Export beside every chart](#export-beside-every-chart)
- [Export the input-to-output graph](#export-the-input-to-output-graph)
  - [Render the mathematical graph](#render-the-mathematical-graph)
- [Deterministic type constants](#deterministic-type-constants)
  - [Why can minimal values be invalid?](#why-can-minimal-values-be-invalid)
- [Potential output complexity](#potential-output-complexity)
  - [How the maximum is found](#how-the-maximum-is-found)
<!-- toc:end -->

[Documentation](../README.md) · [Project](../../README.md)

## Declared and inferred types

**Declared types** are rules the chart author writes in `values.schema.json`, using
JSON Schema. For example, `"type": "integer"` declares a whole-number setting;
`"minimum": 1` restricts its allowed values. The schema must describe an object at
its root. Schema references (`$ref`) must point within the same document.

**Inferred types** are derived from existing values when a declaration is missing.
For example, `replicaCount: 2` in `values.yaml` provides evidence of an integer,
but does not establish a minimum, maximum, or list of allowed values. The tool also
examines template references and supported literal fallbacks. Inference supplies
test inputs; it does not establish the chart author's intended contract.

| Input | Accepted format | Purpose |
| --- | --- | --- |
| `values.schema.json` | JSON Schema written as JSON | Declares types and constraints for chart settings. |
| `values.yaml` | YAML mapping of setting names to values | Supplies defaults and evidence for type inference. `--values FILE` selects an alternative values file. |
| `templates/` | Helm's Go templates | Identifies referenced settings and supported literal fallbacks. |

Values can contain strings, booleans, numbers, lists, nested mappings, and nulls.
A null default alone does not establish a type, and an empty list alone does not
establish its item type. See [generated suites](../usage.md#inspect-and-rerun-generated-suites)
for the generated artifacts and their review workflow.

## Inventory values

```sh
helm hypothesis audit ./chart --export-minimal-values
helm hypothesis audit ./chart --export-minimal-values ./review/minimal.yaml
helm hypothesis scan https://github.com/bitnami/charts.git --filter --report --export-minimal-values
```

The compiler reads which values the templates use, then compares those paths with
the original `values.yaml` and, when present, `values.schema.json`. A path identifies
a setting, such as `.service.port`. The audit reports:

- **Missing values:** referenced paths absent from `values.yaml`, including paths
  with template fallbacks. Absence is not necessarily an invalid configuration.
- **Undocumented template fields:** referenced paths absent from the schema.
  **Template-only fields** are absent from both schema and values.
- **Unreferenced values:** supplied fields with no matching resolved reference.
  These are candidates for review; dynamic access and helpers can make their use
  unknown. They are not automatically classified as invalid or proven unused.

`lower_bound_fields` is the number of specific values paths the compiler could
identify in the templates. If it finds `.service.port`, it counts that field
without counting `.service` again as another field. It first removes branches
that a literal `if true` or `if false` makes unreachable.

This count is a **lower bound**: the chart may read additional fields through
computed keys or template code the compiler cannot resolve. Those unknowns are
listed separately. The count tells you what the audit found, not how many fields
are guaranteed to change the rendered output.<sup>[\[1\]](#export-the-input-to-output-graph)</sup>

Whole-chart tests and scans measure against the same inventory. `present_count`
counts fields supplied to a render attempt. `varied_count` counts fields whose
merged values changed or were removed relative to the original baseline.
Unchanged defaults do not count as variation. Failed render attempts count;
candidates skipped because their output is proven equivalent do not. Across testing
phases, each field is counted only once. Unvaried paths stay visible.
A zero-field inventory has no percentage, rather than reporting 100% coverage.
These measurements do not prove branch, interaction, or output coverage.
Generated path suites record the inventory and planned known fields in
`paths.json`; planning is not reported as executed variation.

## Inspect the baseline

`--export-minimal-values [FILENAME]` is available on `audit`, `generate`, `test`,
and `scan`. The default filename is `values-minimal-<checksum>-<epoch>.yaml`:
`checksum` is the full SHA-256 of the exported YAML bytes, and `epoch` is the Unix
export time in seconds. The checksum is recorded in the companion proof; the
export time is included in the CLI report.

Single-chart commands write to the current working directory; an optional filename
or path overrides the destination. Scans default to each chart's artifact directory.
For a scan, `--export-minimal-values ./review/minimal.yaml` writes
`./review/<chart-relative-path>/minimal.yaml`, keeping each chart's export separate.

Each export contains two YAML documents separated by `---`: the first holds the
baseline values; the second lists `missing_values` with template references and
`schema_fields_without_values`. No placeholder values are invented. Use the first
document when supplying values to Helm; the second is diagnostic metadata. The
filename checksum covers both documents. Missing-field metadata describes the
original source values, before any typed gaps are filled in the example.

An adjacent `.proof` file replaces the former `.inventory.json` sidecar. It retains
the full lower-bound field list, source locations, and reasons for retained values. `audit` also works without a values schema.
During scans, the selected
`--values` file supplies the original baseline being inspected.

The exporter uses supplied values first, then explicit schema `default` or `const`
values, then the type's constant for missing required or referenced fields. It
does not infer downstream API bounds or search for replacement values. Fields
whose types are unknown stay unresolved in the inventory; no placeholder is invented.

Validation runs in an isolated chart copy with `values.yaml` replaced, so Helm
cannot silently fill removed keys back in from the original defaults. Checks cover
the values schema, Helm lint, rendering, and manifest envelopes. Configured
Kubeconform validation also applies. If the example passes, the existing bounded
reduction removes unnecessary entries while keeping valid, nonempty output.

If validation fails, **the illustrative YAML is still exported**, with
`verified: false` and the error in the `.proof` file. For example,
an integer without a supplied value or declared default gets `0`, even when a
schema requires at least `1`; validation flags that mismatch for the engineer.
This file demonstrates configuration and is not a deployment certificate.

`--minimal-values-timeout 30s` bounds verification and reduction. A completed,
verified reduction establishes **deletion-minimality**: no remaining entry can be
removed on its own while still passing those checks. It does not prove that a
different set of values, or removing several entries together, could not produce
a smaller valid configuration.<sup>[\[2\]](#verification-record)</sup>
A timeout preserves the last verified candidate, or the deterministic example
if verification never completed. Elapsed time stays in the CLI/run report so
repeated completed YAML and proof exports remain stable. Original chart inputs are untouched.

## Verification record

`values-minimal.yaml` has a companion **`values-minimal.proof`** containing JSON.
A custom YAML basename produces a matching `.proof` basename. The proof records:

- The exported YAML's SHA-256 checksum, covering both YAML documents.
- Validation success or failure, completed checks, and validation errors.
- The search budget, number of candidates checked, and whether reduction completed.
- Deletion-minimality and explicit limits on global minimality and render equivalence.
- The full input-field inventory and source references.

Verification metadata lives in the proof; missing-field metadata remains after
`---` in the YAML. The proof is an evidence record, not an assertion that every
export is valid or globally minimal. It uses a versioned JSON format and is
published after the YAML, with the checksum binding it to those exact YAML bytes.
Export timestamps and elapsed time remain in the CLI/run report, outside the
committed proof. Pre-commit and optional CI commit-back keep both files together.

## Export beside every chart

```sh
helm hypothesis export-minimal-values ./charts
helm hypothesis export-minimal-values ./charts --filename values-review.yaml
```

This export-only command defaults to **`values-minimal.yaml` in every discovered
chart directory**. `--filename` accepts a basename, never a directory override.
Library charts are N/A; export errors are reported while discovery continues.
Example validation failures are recorded in the exported files. See [pre-commit and optional CI commit-back](../ci/README.md#minimal-values-in-ci).

## Export the input-to-output graph

```sh
helm hypothesis audit ./chart --export-topological-graph ./review/topology.json
helm hypothesis test ./charts --export-topological-graph
```

The JSON graph and adjacent Graphviz `.dot` file show where templates read values,
which conditions control their use, and which resources the default configuration
produces. A node represents a value, condition, template, resource or manifest field;
an arrow connects related nodes. The compiler removes branches it can prove will
never run. Computed lookups and code it cannot interpret are marked unresolved.

Reference edges describe potential influence, and rendered edges describe one
observed baseline. The graph does not claim exact per-field causality or complete
output-space coverage. It records paths and types rather than manifest values.
If the baseline cannot render, static evidence is still exported with output
observation marked unavailable. Default names are
`topological-graph-<checksum>-<epoch>.json`; scans keep each chart's graph separate.

### Render the mathematical graph

Install `hypothesis-helm[benchmarking]`, then render the exported graph with Matplotlib:

```sh
hypothesis-helm-benchmark topology --graph ./review/topology.json \
  --output ./review/topology --title "My chart"
```

This writes `topology.png`, `topology.svg`, `metrics.json`, and `positions.csv`.
The figure is a **directed multigraph**: arrows have a direction, and two nodes can
have more than one arrow between them when the compiler finds multiple references.
Every node and arrow from the export is retained. Node kinds distinguish values,
conditions, unresolved template logic, templates, manifests, and manifest fields.
The JSON/DOT export retains their identities and edge types; the coordinate CSV
maps every vertex to the drawing.

Reading left to right follows dependencies: a node is placed one column beyond
the most distant node that points to it. Vertical positions keep the drawing
reproducible; the distance between two nodes does not measure how similar their
outputs are. This layout is separate from the PCA benchmark plots.

The metrics count arrows into and out of each node (**degrees**), connected groups
when arrow direction is ignored (**weak components**), nodes with no arrows
(**isolates**), and the longest chain of arrows. That chain measures dependencies,
not nested `if` statements or manifest nesting. A cycle, where following arrows
leads back to a previous node, is reported as an error.

These are graphs of the compiler's available evidence. Potential references and
baseline observations do not prove exact causal influence; opaque access remains
explicitly unresolved.

The [topology catalog](../../studies/chart-topologies/README.md) contains rendered
graphs for the synthetic fixtures and the Bitnami and Prometheus chart collections.

## Deterministic type constants

The compiler's `constants.py` supplies these defaults for missing typed values:

| Declared input type | Constant |
| --- | --- |
| Boolean | `false` |
| Integer | `0` |
| Number | `0.0` |
| String | `""` |
| Array | `[]` |
| Object | `{}`, with required or referenced typed children filled recursively |
| Explicit null type | `null` |
| Unknown type | No invented value; recorded as unresolved |

Supplied values-including `false`, `0`, `""` and explicit null-are preserved.
Explicit schema defaults and constants take precedence over these type constants.
This policy is deterministic; it does not invent strings, choose enum alternatives,
or solve downstream constraints. Further validation catches invalid examples.

### Why can minimal values be invalid?

A type-correct constant is not necessarily valid for the chart or Kubernetes API.
For example, `0` may violate a field's minimum of `1`, and `""` may violate a
required name's length or pattern. Supplied values and explicit schema defaults
can also be invalid. The exporter does not search for a replacement in these
cases; its reduction search removes unnecessary entries from a verified baseline.

If no candidate passes verification, the deterministic example is still written
with `verified: false` and the validation error in its `.proof` file. Check that
record, provide an appropriate value in the source values file or a default in
the values schema, and rerun the export. Only checks that actually ran can flag
invalid values; enable Kubeconform to include Kubernetes API schema validation.

Export-only workflows can use the existing local Kubernetes schema validation:

```sh
helm hypothesis export-minimal-values ./charts --kubeconform --schema-version 1.35.0
# Reuse a prepared snapshot without fetching:
helm hypothesis export-minimal-values ./charts --kubeconform --schema-version 1.35.0 --schema-offline
```

Exports record whether API validation passed, was not confirmed, or did not run.
The GitHub action reuses API validation when `kubeconform` or `kubesec` is enabled.
API schema checks still omit some server-side checks; see
[Kubeconform's documented limits](https://github.com/yannh/kubeconform#limits-of-kubeconform-validation).

## Potential output complexity

`helm hypothesis audit ./chart` includes a `complexity` result. It asks: **how wide
and deeply nested could this chart's output become with different allowed values?**
The score is **breadth × depth**. It describes the structure of the output, not its
file size, expected bug count or testing time.

To calculate it, treat all rendered resources as trees beneath one imaginary
parent. Each resource starts at level 1. Moving into a field value or list item
adds one level. Objects and lists count as nodes themselves, as do individual
values such as strings and numbers. The imaginary parent is not counted.

- **Breadth:** count the nodes at each level across all resources, then take the
  largest count. This is the width of the busiest level, not the most children
  belonging to a single object.
- **Depth:** the deepest level reached by any value.

For example, this ConfigMap has a breadth of **4**, a depth of **3**, and a score of **12**:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: demo
data:
  mode: safe
```

| Level | Nodes counted | Count |
| --- | --- | --- |
| 1 | The ConfigMap object | 1 |
| 2 | `v1`, `ConfigMap`, the `metadata` object, the `data` object | 4 |
| 3 | `demo`, `safe` | 2 |

Field names such as `metadata` label the connections; they do not add separate
nodes. Changing `safe` to a longer string leaves the score unchanged. This output
tree is different from the graph showing which inputs affect which templates.<sup>[\[3\]](#export-the-input-to-output-graph)</sup>

The search includes resources disabled by the defaults. Its maximum must come
from one allowed configuration: it cannot combine the width of one configuration
with the depth of another if those settings cannot be used together.

- `compiled-maximum`: the analysis established the largest score across the supported, allowed value choices.
  `maximum_score`, `maximum_output` and `maximizing_values` record the greatest output and a configuration attaining it.
- `unknown`: an open-ended domain, unsupported operation, dependency, source change or analysis limit prevented a maximum.
  `lower_bound` records the largest score found so far, if any. A larger output may still be possible.
- `no-valid-output`: every supported configuration was checked, but none produced resources passing the basic manifest checks.

Analysis allows at most 4,096 evaluations of template inputs and complete configurations,
with a five-second budget checked between work units. It evaluates supported template
code itself; it does not call Helm or validate Kubernetes API schemas. Each field's
allowed choices and each template's input-to-output table must fit the analysis
limits, even when the number of complete configurations is much larger.
The `verification`, `reason` and `limits` fields state the scope of the result.

The installed `hypothesis-helm-complexity` command repeats the analysis with
adjustable `--chart`, `--max-cases` and `--time-limit` settings. Its `--nodes N`
mode instead asks how high the score could be for **any tree with N nodes**,
regardless of the chart. That ceiling is `(N + 1)² / 4` rounded down to an integer,
or zero for an empty tree. The bound follows from `breadth + depth - 1 <= N`:
the deepest path and the other nodes at the widest level must all fit within N.
The output's `size_ceiling` field uses this formula; your chart may never be able
to produce the tree shape that reaches it.

### How the maximum is found

The search uses **branch-and-bound**. First, it calculates what each template can
produce from the fields that template reads. Then it chooses values step by step.
Before trying every remaining choice, it calculates an upper bound: a score at
least as large as anything those choices could produce. If that bound cannot beat
an output already found, the search skips those choices.

The bound adds each template's largest possible count at each nesting level.
Those counts may come from incompatible choices, so the bound can overestimate
what is possible; it must never underestimate it. Actual candidate outputs use
one consistent configuration and must pass the values schema and basic manifest
checks. A fixed order of choices makes ties reproducible.

`template_evaluations`, `examined_configurations`, `search_nodes` and `pruned_configurations` report the work performed.
The candidate count includes inputs that may fail after merging with defaults.
An upper bound may be too generous to skip much work. If one template reads every
varying field, the search may still need to try exponentially many choices. Code
the compiler cannot interpret is never used as evidence to skip a candidate.

`--filter-adaptive` uses this score together with allowed input choices, nested
conditions and groups of predicted outputs to choose a minimum number of tests
and changed fields, based on benchmark measurements. The score alone does not
determine a suitable sample size. If no suitable measurements are available,
ordinary filtering still applies, but the extra sampling is disabled.<sup>[\[4\]](../adaptive-filtering/README.md#what-determines-the-minimum)</sup>

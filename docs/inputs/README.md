# Input inventory and minimal values

[Documentation](../README.md) · [Project](../../README.md)

```sh
helm hypothesis audit ./chart --export-minimal-values
helm hypothesis audit ./chart --export-minimal-values ./review/minimal.yaml
helm hypothesis scan https://github.com/bitnami/charts.git --filter --report --export-minimal-values
```

The compiler compares the original `values.yaml`, `values.schema.json` when
present, and scoped template references. It reports:

- **Missing values:** referenced paths absent from `values.yaml`, including paths
  with template fallbacks. Absence is not necessarily an invalid configuration.
- **Undocumented template fields:** referenced paths absent from the schema.
  **Template-only fields** are absent from both schema and values.
- **Unreferenced values:** supplied fields with no matching resolved reference.
  These are candidates for review; dynamic access and helpers can make their use
  unknown. They are not automatically classified as invalid or proven unused.

`lower_bound_fields` counts the identified, leaf-most named template selectors.
Parent containers are not counted again when a more specific named selector is
known. Literal `if true` / `if false` branches are simplified first. Wildcard
key spaces and unresolved contexts are reported separately; they do not create
an invented finite denominator. This is a lower bound on the static inventory,
not a proof of the number of inputs that influence rendered output.

Whole-chart tests and scans measure against the same inventory. `present_count`
counts fields supplied to a render attempt. `varied_count` counts fields whose
merged values changed or were removed relative to the original baseline.
Unchanged defaults do not count as variation. Failed render attempts count;
candidates skipped by equivalence pruning do not. Phase totals union field
identities, so the same field is counted once. Unvaried paths stay visible.
A zero-field inventory has no percentage, rather than reporting 100% coverage.
These measurements do not prove branch, interaction, or output coverage.
Generated path suites record the inventory and planned known fields in
`paths.json`; planning is not reported as executed variation.

## Inspect the baseline

`--export-minimal-values [FILENAME]` is available on `audit`, `generate`, `test`,
and `scan`. The default filename is `values-minimal-<checksum>-<epoch>.yaml`:
`checksum` is the full SHA-256 of the exported YAML bytes, and `epoch` is the Unix
export time in seconds. Both are recorded in the adjacent inventory file.

Single-chart commands write to the current working directory; an optional filename
or path overrides the destination. Scans default to each chart's artifact directory.
For a scan, `--export-minimal-values ./review/minimal.yaml` writes
`./review/<chart-relative-path>/minimal.yaml`, keeping each chart's export separate.

Each export contains two YAML documents separated by `---`: the first holds the
baseline values; the second lists `missing_values` with template references and
`schema_fields_without_values`. No placeholder values are invented. Use the first
document when supplying values to Helm; the second is diagnostic metadata. The
filename checksum covers both documents.

An adjacent `.inventory.json` retains the full lower-bound field list, source
locations, and reasons for retained values. `audit` also works without a values schema.
During scans, the selected
`--values` file supplies the original baseline being inspected.

The export searches an isolated chart copy, replacing its `values.yaml` so Helm
cannot fill removed fields back in from the original defaults. Each accepted
candidate passes the declared values schema, `helm lint`, `helm template`, and
manifest envelope checks. Configured Kubeconform validation also applies when
exporting through `test --kubeconform`. These are local checks, not an API-server
admission or deployment guarantee.

Values are concrete: `false` and `0` remain meaningful values, and missing fields
never become bare-key placeholders. Legitimate null values are written explicitly
as `null`. If the original defaults fail, a bounded schema-based search may find
an accepted starting configuration; no export is written without verification.
Optional `enabled` components can be disabled when that reduces resource count.
The search then removes entries while preserving valid, nonempty output without
increasing that count. It is allowed to change the original manifests.

`--minimal-values-timeout 30s` bounds each search. A completed search establishes
**deletion-minimality**: no single remaining entry can be removed under those
checks without increasing resource count. This is not a global minimum over all
value assignments or a proof of the fewest possible resources. An interrupted
search exports only its last verified candidate and records incomplete minimality.
Verification details appear in document 2 and the JSON sidecar. Volatile timing
statistics live only in JSON so repeated completed YAML exports stay stable.
The export does not change the original test domain or source values file.

## Export beside every chart

```sh
helm hypothesis export-minimal-values ./charts
helm hypothesis export-minimal-values ./charts --filename values-review.yaml
```

This export-only command defaults to **`values-minimal.yaml` in every discovered
chart directory**. `--filename` accepts a basename, never a directory override.
Library charts are N/A; other unverified charts report failures while discovery
continues. See [pre-commit and optional CI commit-back](../ci/README.md#minimal-values-in-ci).

## Export the input-to-output graph

```sh
helm hypothesis audit ./chart --export-topological-graph ./review/topology.json
helm hypothesis scan ./charts --export-topological-graph
```

The JSON graph and adjacent Graphviz `.dot` file connect named values to template
references and control flow, then templates to baseline manifests and their field
paths. Nodes use the compiler’s shared typed input model. Literal dead branches
are eliminated; supported symbolic regions include baseline partitions and proven
live references. Dynamic access and opaque regions remain explicitly unresolved.

Reference edges describe potential influence, and rendered edges describe one
observed baseline. The graph does not claim exact per-field causality or complete
output-space coverage. It records paths and types rather than manifest values.
If the baseline cannot render, static evidence is still exported with output
observation marked unavailable. Default names are
`topological-graph-<checksum>-<epoch>.json`; scans keep each chart’s graph separate.

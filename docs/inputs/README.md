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
filename checksum covers both documents. Missing-field metadata describes the
original source values, before any typed gaps are filled in the example.

An adjacent `.inventory.json` retains the full lower-bound field list, source
locations, and reasons for retained values. `audit` also works without a values schema.
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
`verified: false` and the error in document 2 and the JSON sidecar. For example,
an integer without a supplied value or declared default gets `0`, even when a
schema requires at least `1`; validation flags that mismatch for the engineer.
This file demonstrates configuration and is not a deployment certificate.

`--minimal-values-timeout 30s` bounds verification and reduction. A completed,
verified reduction establishes deletion-minimality under the observed checks,
not a global minimum over every value assignment or resource configuration.
A timeout preserves the last verified candidate, or the deterministic example
if verification never completed. Volatile timing statistics stay in JSON so
repeated completed YAML exports remain stable. Original chart inputs are untouched.

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

Supplied values—including `false`, `0`, `""` and explicit null—are preserved.
Explicit schema defaults and constants take precedence over these type constants.
This policy is deterministic; it does not invent strings, choose enum alternatives,
or solve downstream constraints. Further validation catches invalid examples.

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

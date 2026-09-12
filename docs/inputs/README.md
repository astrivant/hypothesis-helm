# Input inventory and minimal values

[Documentation](../README.md) · [Project](../../README.md)

```sh
helm hypothesis audit ./chart --dump-minimal-values
helm hypothesis audit ./chart --dump-minimal-values ./review/minimal.yaml
helm hypothesis scan https://github.com/bitnami/charts.git --filter --report --dump-minimal-values
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

`--dump-minimal-values [PATH]` is available on `audit`, `generate`, `test`, and
`scan`. Single-chart commands default to `minimal-values.yaml` in the current
working directory; `PATH` overrides that filename. Scans default to each chart's
artifact directory. For a scan, `PATH` is an output directory, with separate
`minimal-values.yaml` files beneath each chart's relative path.

Each YAML file has an adjacent `.inventory.json` containing the lower-bound
field list, source locations, missing fields, and the reason for any retained
values. `audit` also works without a values schema. During scans, the selected
`--values` file supplies the original baseline being inspected.

The dump projects existing values onto known references and dynamic subtrees.
Opaque contexts or dependency forwarding retain the original values; if a
projection violates the declared schema, the original values are retained.
Missing defaults are listed rather than filled with invented nulls or strings.
The source values file is never overwritten.

This is a conservative reduction, not a globally smallest valid configuration
or a certificate of identical rendering. The dump is not automatically applied
to testing; the original validation contract and generation strategy stay in use.

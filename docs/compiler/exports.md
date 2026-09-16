# Export passes

<!-- toc:start -->
**Table of contents**

- [Input inventory export](#input-inventory-export)
- [Minimal values](#minimal-values)
- [Topological graph export](#topological-graph-export)
- [Repository export](#repository-export)
<!-- toc:end -->

[Compiler](README.md) · [Analysis passes](analysis.md) · [Input and export CLI guide](../inputs/README.md)

Exports make compiler findings inspectable. Each artifact distinguishes static
references, observed output, and checks that actually passed.

## Input inventory export

[`inputs.py`](../../pkg/hypothesis_helm/compiler/passes/inputs.py) serializes field
locations, missing declarations, unresolved access, and coverage counts.
`InputInventory.dump` writes concrete values and a verification record supplied
by the minimal-values pass. Missing-field information follows the values document
after a YAML `---` separator.

The shared defaults in
[`constants.py`](../../pkg/hypothesis_helm/compiler/constants.py) fill missing
typed values deterministically. A typed zero can still violate a template or a
downstream Kubernetes constraint. The exporter records that result instead of
searching for arbitrary replacement values.<sup>[\[1\]](../inputs/README.md)

## Minimal values

[`minimum.py`](../../pkg/hypothesis_helm/compiler/passes/minimum.py) works in an
isolated chart copy. It tries the supplied defaults, then a deterministic example
with missing known fields filled. Each accepted candidate must pass the values
schema, Helm lint, rendering, resource-envelope checks, and configured Kubernetes
schema validation, and must produce nonempty resources.

From a valid baseline, the pass tries disabling optional `enabled` fields when
that removes resources. It then removes groups of entries, progressively trying
smaller groups. Accepted removals must preserve validity without increasing the
resource count.

A completed search establishes **deletion minimality**: no single remaining
entry can be removed under these checks. It does not prove the smallest possible
configuration over all values, or preserve the original rendered manifests.
Timeouts retain the best verified candidate. If neither starting candidate works,
the illustrative export remains available with failed verification recorded.

The `.proof` companion records the budget, checks, resource count, verification
status, and whether the search completed. Kubernetes API validation is explicitly
`not-run` when no validator was configured.

## Topological graph export

[`graph.py`](../../pkg/hypothesis_helm/compiler/passes/graph.py) emits JSON and a
DOT companion. Nodes represent values paths, conditions, dependency instances,
templates, resources, and manifest fields. Typed edges record references,
enablement controls, source associations, and containment.

The export combines static analysis with one baseline Helm render. Potential
references are labeled separately from supported baseline influences and observed
output. It does not infer complete field-level causality from an opaque template.
Paths and types are exported without copying input values or manifest field
contents. Rendering failures and unsupported analysis remain visible limitations.

The [graph guide](../inputs/README.md) explains how to interpret these relationships
and the matplotlib plots produced from them.

## Repository export

[`exports.py`](../../pkg/hypothesis_helm/compiler/passes/exports.py) applies minimal
export independently to every discovered application chart. It places the chosen
YAML basename in each chart directory, records individual outcomes, and can write
a NUL-delimited list of YAML and proof paths for CI staging. Library charts have
no standalone nonempty output and are marked not applicable.

This wrapper orchestrates exports; it adds no stronger minimality claim.

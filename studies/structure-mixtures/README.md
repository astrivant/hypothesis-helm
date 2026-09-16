# Mixed chart structures

<!-- toc:start -->
**Table of contents**

- [Nesting-depth distributions](#nesting-depth-distributions)
<!-- toc:end -->

[Benchmarking](../../docs/benchmarking/README.md) · [Depth sweep](../structure-depth/README.md)

Generate multiple structural components distributed throughout one chart:

```sh
hypothesis-helm-benchmark generate \
  --output .cache/mixed-chart --input-complexity 10 --output-bins 4 \
  --topology-components 12 --topology-seed 2026
```

The default samples uniformly from constraints, control flow, dependencies,
interactions, equivalence, and boundaries. Specify relative weights to change the mix:

```sh
hypothesis-helm-benchmark generate \
  --output .cache/weighted-chart --input-complexity 10 --output-bins 4 \
  --topology-components 12 --topology-seed 2026 \
  --topology-weight dependencies=3 --topology-weight interactions=2 \
  --topology-weight equivalence=1
```

With explicit weights, omitted types have zero probability. Weights need not sum
to one. Sampling is categorical: topology names have no meaningful numeric order
for a normal distribution. `--mean` and `--stddev` still control the separate
normal-quantile output projection.

Each component has unique resource names and sampled input wiring. Components
share paths, allowing dependencies and constraints to overlap. Boundary components
share a reserved three-valued integer input; other roles use Boolean inputs. At
least five inputs beyond the quantile selectors are required. `benchmark.json`
records requested probabilities, realized counts, the seed, and each component's
paths. Small samples need not match the requested proportions exactly.

`--structure NAME` still generates an isolated case. Mixtures cannot be combined
with `--structure`, `--topology`, `--topology-opaque`, or the interaction-fault mode
`--bug-percent`. The depth benchmark independently injects errors into a fixed
percentage of complete valid assignments after generating each chart.

The fixture oracle evaluates every component independently and checks the schema's
combined constraints. The depth benchmark verifies complete rendered manifests,
including resource multiplicity and Service/Ingress references. Unsupported
constructs can conservatively prevent trimming across the entire chart.

## Nesting-depth distributions

Add a fixed number of outer Boolean gates around every component with
`--topology-depth 1` or `--topology-depth 5`. To sample depths instead:

```sh
hypothesis-helm-benchmark generate \
  --output .cache/nested-chart --input-complexity 10 --output-bins 4 \
  --topology-components 12 --topology-seed 2026 \
  --topology-depth-weight 1=1 --topology-depth-weight 2=1 \
  --topology-depth-weight 3=1 --topology-depth-weight 4=1 \
  --topology-depth-weight 5=1
```

Depth weights are relative probabilities. The generator records each component's
realized gate depth and paths. Gate depths and gate ordering use separate seeded
streams from component types and original wiring. Deeper profiles take prefixes
of the same gate ordering, so changing the depth distribution preserves the other
fixture settings. Constraints remain global; depths count added outer gates,
not preexisting branches within a structural body. Omit both depth options to
retain the original ungated mixture behavior.

The [nesting matrix and shared-frame PCA](../nesting/README.md) hold
`--permutations 8` fixed while comparing shallow, deep, and mixed-depth charts.
Permutation strength, component count, chart nesting depth, and trim depth are
separate controls.

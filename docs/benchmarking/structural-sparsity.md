# Structural sparsity

<!-- toc:start -->
**Table of contents**

- [Structural sparsity](#structural-sparsity)
<!-- toc:end -->

[Results and plots](../../studies/structural-sparsity/README.md) · [Benchmark guide](README.md)

This extends the sparsity study in a different direction: enlarge the chart while keeping the
parts that affect output small. It asks whether irrelevant structure adds discovery cost or
causes filtering to miss interactions between distant fields.

The shared chart has four variable Boolean fields. All other leaves are fixed to `false` by
the schema. Every case therefore has the same 16 configurations, two pairwise defects, and
seven erroneous configurations. This isolates structural overhead; it does not simulate an
exponentially growing set of variable inputs.

| Control | Meaning |
| --- | --- |
| `--breadths` | Root branch counts; each branch ends in four Boolean fields. |
| `--depths` | Intermediate maps between each root branch and its terminal fields. |
| `--placements near` | All four relevant fields share a terminal map. |
| `split` | Relevant fields occupy two branches. |
| `far` | Relevant fields occupy four branches but share resource projections. |
| `disconnected` | The same four-branch placement, with separate resources for each interacting pair. |

Moving fields changes which leaves have a Boolean domain; it does not change the tree shape
or its size. Node count is `1 + breadth * (depth + 5)`. Relevant-node density is four divided by
that count. Distances count tree edges, not the positions of nodes in a drawing. Two leaves in
one terminal map are two edges apart; leaves in different root branches are `2 * (depth + 2)` apart.

The values tree and the input-to-resource dependency graph are different graphs. The values tree
always has a common root. Distant fields can still be connected through shared resources;
`disconnected` removes those shared references while retaining the same defect triggers.
The report includes a diagram of the two dependency arrangements.

```sh
hypothesis-helm-benchmark structural-sparsity --time-limit 9m --output .cache/benchmarks/structural-sparsity
```

The full refresh includes this command after the existing structure sparsity study. Defaults sweep
breadths 50, 200 and 800, depths 2, 8 and 24, all four placements, all seven matrix strategies,
and two paired repeats. The largest tree has 23,201 nodes but still only four variable fields.
Use a fresh output directory for new measurements; `--plot-only` redraws existing results.

```sh
hypothesis-helm-benchmark structural-sparsity --breadths 50 200 --depths 2 8 --repeats 2 \
  --time-limit 30s --output .cache/benchmarks/structural-sparsity-quick
```

Each run uses production selectors and real Helm renders, checked against an independent oracle.
Planning uses interaction strength four so the unfiltered reference covers all 16 configurations.
The same strength is passed to the filter presets; these are not measurements of the default pairwise setting.
Preset failure expansion remains enabled,
and adaptive sampling records any fallback rather than forcing a reduction on a small domain.
Fresh in-memory caches are used per method; OS caches may remain warm. Method order is shuffled
with the repeat seed. Results include the selection decisions and exact distances.

Total time includes chart loading, planning, compiler analysis, and execution. Chart loading
measures values/schema discovery; it does not include compiler analysis. Chart generation and
enumerating the independent reference, and report serialization are outside the measured phases. Execution timeouts leave
partial counts in the ledger, and incomplete cells are excluded from completed-time averages.
The execution ceiling does not limit planning time.

Plots show mean ±1 sample standard deviation across repeats. This is observed variation, not a
confidence interval or a guarantee of bug recall on arbitrary charts. The study reuses one
temporary chart and retains YAML recipes under `cases/`; refresh also includes those recipes
in its topology visualization inventory.

Replay a retained case through the common generator:

```sh
hypothesis-helm-benchmark generate --parameters .cache/benchmarks/structural-sparsity/cases/breadth-50-depth-2-far.yaml \
  --output /tmp/structural-sparsity-chart
```

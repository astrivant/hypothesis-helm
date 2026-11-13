# Mutation sensitivity

<!-- toc:start -->
**Table of contents**

- [Parameter interactions](#parameter-interactions)
- [Reproduce this study](#reproduce-this-study)
<!-- toc:end -->

Status: **complete**. Helm render attempts: **1223**.

Distance counts added and removed JSON path/value indicators. A changed value counts twice.
Document and array order matter. These measurements describe observed changes; the compiler's equivalence contract governs pruning.
Distances assume deterministic rendering with fixed chart dependencies, release, namespace and Kubernetes version.

![Sensitivity, interaction and sequence measurements](sensitivity.png)

Measured 48 single mutations and 1128 pairs. The plots include every comparable measurement.
Tables show up to 20 of the largest effects. Mutation IDs follow the order in mutations.json.

| ID | Mutation | Values path | Replacement | Output distance | Status |
| ---: | --- | --- | --- | ---: | --- |
| 19 | &quot;sharedTopologySignal15&quot; | [&quot;sharedTopologySignal15&quot;] | false | 416 | rendered |
| 35 | &quot;sharedTopologySignal31&quot; | [&quot;sharedTopologySignal31&quot;] | false | 398 | rendered |
| 30 | &quot;sharedTopologySignal26&quot; | [&quot;sharedTopologySignal26&quot;] | true | 390 | rendered |
| 22 | &quot;sharedTopologySignal18&quot; | [&quot;sharedTopologySignal18&quot;] | true | 384 | rendered |
| 23 | &quot;sharedTopologySignal19&quot; | [&quot;sharedTopologySignal19&quot;] | false | 362 | rendered |
| 11 | &quot;sharedTopologySignal07&quot; | [&quot;sharedTopologySignal07&quot;] | false | 348 | rendered |
| 34 | &quot;sharedTopologySignal30&quot; | [&quot;sharedTopologySignal30&quot;] | true | 348 | rendered |
| 28 | &quot;sharedTopologySignal24&quot; | [&quot;sharedTopologySignal24&quot;] | true | 332 | rendered |
| 33 | &quot;sharedTopologySignal29&quot; | [&quot;sharedTopologySignal29&quot;] | false | 326 | rendered |
| 5 | &quot;sharedTopologySignal01&quot; | [&quot;sharedTopologySignal01&quot;] | false | 316 | rendered |
| 14 | &quot;sharedTopologySignal10&quot; | [&quot;sharedTopologySignal10&quot;] | true | 294 | rendered |
| 39 | &quot;sharedTopologySignal35&quot; | [&quot;sharedTopologySignal35&quot;] | false | 292 | rendered |
| 16 | &quot;sharedTopologySignal12&quot; | [&quot;sharedTopologySignal12&quot;] | true | 288 | rendered |
| 46 | &quot;sharedTopologySignal42&quot; | [&quot;sharedTopologySignal42&quot;] | true | 282 | rendered |
| 8 | &quot;sharedTopologySignal04&quot; | [&quot;sharedTopologySignal04&quot;] | true | 280 | rendered |
| 27 | &quot;sharedTopologySignal23&quot; | [&quot;sharedTopologySignal23&quot;] | false | 266 | rendered |
| 48 | &quot;sharedTopologySignal44&quot; | [&quot;sharedTopologySignal44&quot;] | true | 264 | rendered |
| 40 | &quot;sharedTopologySignal36&quot; | [&quot;sharedTopologySignal36&quot;] | true | 212 | rendered |
| 21 | &quot;sharedTopologySignal17&quot; | [&quot;sharedTopologySignal17&quot;] | false | 204 | rendered |
| 47 | &quot;sharedTopologySignal43&quot; | [&quot;sharedTopologySignal43&quot;] | false | 204 | rendered |

## Parameter interactions

A nonzero mixed difference means the selected output features respond non-additively.
Pairs with order-dependent inputs are excluded from this measure. Render failures have no assigned distance.

| Mutations | Mixed difference | Status |
| --- | ---: | --- |
| [&quot;sharedTopologySignal18&quot;, &quot;sharedTopologySignal26&quot;] | 768 | rendered |
| [&quot;sharedTopologySignal26&quot;, &quot;sharedTopologySignal31&quot;] | 756 | rendered |
| [&quot;sharedTopologySignal18&quot;, &quot;sharedTopologySignal31&quot;] | 744 | rendered |
| [&quot;sharedTopologySignal15&quot;, &quot;sharedTopologySignal31&quot;] | 742 | rendered |
| [&quot;sharedTopologySignal15&quot;, &quot;sharedTopologySignal26&quot;] | 734 | rendered |
| [&quot;sharedTopologySignal15&quot;, &quot;sharedTopologySignal18&quot;] | 722 | rendered |
| [&quot;sharedTopologySignal19&quot;, &quot;sharedTopologySignal26&quot;] | 674 | rendered |
| [&quot;sharedTopologySignal18&quot;, &quot;sharedTopologySignal19&quot;] | 668 | rendered |
| [&quot;sharedTopologySignal15&quot;, &quot;sharedTopologySignal19&quot;] | 666 | rendered |
| [&quot;sharedTopologySignal19&quot;, &quot;sharedTopologySignal24&quot;] | 664 | rendered |
| [&quot;sharedTopologySignal24&quot;, &quot;sharedTopologySignal30&quot;] | 664 | rendered |
| [&quot;sharedTopologySignal19&quot;, &quot;sharedTopologySignal31&quot;] | 656 | rendered |
| [&quot;sharedTopologySignal18&quot;, &quot;sharedTopologySignal29&quot;] | 652 | rendered |
| [&quot;sharedTopologySignal26&quot;, &quot;sharedTopologySignal29&quot;] | 652 | rendered |
| [&quot;sharedTopologySignal07&quot;, &quot;sharedTopologySignal15&quot;] | 648 | rendered |
| [&quot;sharedTopologySignal07&quot;, &quot;sharedTopologySignal18&quot;] | 634 | rendered |
| [&quot;sharedTopologySignal07&quot;, &quot;sharedTopologySignal26&quot;] | 634 | rendered |
| [&quot;sharedTopologySignal18&quot;, &quot;sharedTopologySignal30&quot;] | 634 | rendered |
| [&quot;sharedTopologySignal26&quot;, &quot;sharedTopologySignal30&quot;] | 634 | rendered |
| [&quot;sharedTopologySignal01&quot;, &quot;sharedTopologySignal19&quot;] | 632 | rendered |

The ordered sequence in results.json records both cumulative path length and displacement from the baseline.
They differ when later mutations reverse earlier changes. The sequence stops at its first invalid or failed step.

Full measurements and render errors (local run data)

## Reproduce this study

Shared benchmark chart: 48 Boolean inputs, 64 structural components, seed 2026. The baseline alternates true and false; each mutation flips one distinct path. This measures one baseline, not the entire configuration space.

Exact chart sources are retained in chart-inputs.json (local run data).

This command updates the published study automatically after a successful run. Use --output to keep results separate; incomplete runs do not replace the published study.

```bash
bash scripts/project-run.sh hypothesis-helm-benchmark sensitivity --inputs 48 --components 64 --seed 2026 --time-limit 540.0
```

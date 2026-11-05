# Benchmark studies

<!-- toc:start -->
**Table of contents**

- [Shared studies](#shared-studies)
- [Backend comparisons](#backend-comparisons)
<!-- toc:end -->

[Benchmarking guide](../docs/benchmarking/README.md) | [CPU studies](cpu/README.md) | [GPU studies](gpu/README.md)

The inventory follows the executed code paths. Backend-dependent studies have separate CPU and GPU destinations. Shared studies do not invoke finite predicate planning. Existing figures retain their recorded measurements; an unmeasured GPU guide is not evidence of a GPU run.

Run `hypothesis-helm-benchmark inventory` for the machine-readable inventory and classification reasons.

## Shared studies

| Study | Scope |
| --- | --- |
| [chart-topologies](chart-topologies/README.md) | Template graph export and baseline Helm renders, without finite predicate planning. |
| [flamegraphs](flamegraphs/README.md) | Profiles the shared rendering/scaling workload, which does not call finite planning. |
| [performance](performance/README.md) | Explicit input-prefix rendering and exact-output pruning; no finite predicate planning. |
| [resource-sizing](resource-sizing/README.md) | Chart inventories and historical process observations. |
| [sampling](sampling/README.md) | Independent complete-population oracle and seeded sampling of observed defects. |
| [sensitivity](sensitivity/README.md) | Explicit mutation renders and output distances, without finite predicate planning. |
| [sparsity](sparsity/README.md) | Nested samples of an explicit workload and observed output distributions. |
| [structure-mixtures](structure-mixtures/README.md) | Seeded fixture definitions and generation instructions. |
| [structure-sparsity](structure-sparsity/README.md) | Nested samples of an explicit structural workload. |

## Backend comparisons

| Study | CPU | GPU | Scope |
| --- | --- | --- | --- |
| bug-density | [Results](cpu/bug-density/README.md) | [Study](gpu/bug-density/README.md) | Finite interaction planning and defect recall at increasing strengths. |
| calibration-variation | [Results](cpu/calibration-variation/README.md) | [Study](gpu/calibration-variation/README.md) | Finite population planning before calibration and selection. |
| discovery | [Results](cpu/discovery/README.md) | [Study](gpu/discovery/README.md) | Finite interaction planning and defect recall at increasing strengths. |
| error-surface | [Results](cpu/error-surface/README.md) | [Study](gpu/error-surface/README.md) | Fresh finite planning for every filtering strategy and error placement. |
| error-surface-quartic | [Results](cpu/error-surface-quartic/README.md) | [Study](gpu/error-surface-quartic/README.md) | Fits retained error-surface observations from the selected backend. |
| expansion | [Results](cpu/expansion/README.md) | [Study](gpu/expansion/README.md) | Finite population planning before paired failure-region expansion. |
| filtering | [Results](cpu/filtering/README.md) | [Study](gpu/filtering/README.md) | Production chart testing, including finite planning and filtering phase timings. |
| matrix | [Results](cpu/matrix/README.md) | [Study](gpu/matrix/README.md) | Fresh finite planning for each structural case and strategy. |
| nesting | [Results](cpu/nesting/README.md) | [Study](gpu/nesting/README.md) | Finite population and interaction planning across chart nesting profiles. |
| pca | [Results](cpu/pca/README.md) | [Study](gpu/pca/README.md) | Finite population planning before output projection and filtering comparisons. |
| sensitivity-ordering | [Results](cpu/sensitivity-ordering/README.md) | [Study](gpu/sensitivity-ordering/README.md) | Finite interaction planning before order and discovery comparisons. |
| stress | [Results](cpu/stress/README.md) | [Study](gpu/stress/README.md) | Fresh finite planning across the structural stress progression. |
| structural-sparsity | [Results](cpu/structural-sparsity/README.md) | [Study](gpu/structural-sparsity/README.md) | Finite planning and filtering with distant relevant inputs. |
| structure-depth | [Results](cpu/structure-depth/README.md) | [Study](gpu/structure-depth/README.md) | Finite population planning before topology filter-depth comparisons. |

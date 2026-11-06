# bug-density: GPU study

<!-- toc:start -->
**Table of contents**

- [bug-density: GPU study](#bug-density-gpu-study)
<!-- toc:end -->

**Status: not measured on a GPU.**

Finite interaction planning and defect recall at increasing strengths.

[CPU study](../../cpu/bug-density/README.md) | [Backend contract](../../../docs/benchmarking/backends.md)

Use Linux with a physical NVIDIA CUDA device, its driver, Helm 4 and the locked GPU/benchmarking dependencies. From the repository root:

```sh
hypothesis-helm-benchmark --execution-backend gpu discovery --input-complexity 8 --max-strength 6 --bug-percent 5 --seed 2026 --time-limit 9m --output .cache/benchmarks/gpu/bug-density
```

Use the matching CPU parameters and seeds for a paired comparison. A successful run retains backend receipts with the actual engine, native work, host fallbacks and measurement hashes. Publishing requires those receipts; CPU measurements cannot populate this directory as GPU observations.

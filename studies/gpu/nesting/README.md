# nesting: GPU study

<!-- toc:start -->
**Table of contents**

- [nesting: GPU study](#nesting-gpu-study)
<!-- toc:end -->

**Status: not measured on a GPU.**

Finite population and interaction planning across chart nesting profiles.

[CPU study](../../cpu/nesting/README.md) | [Backend contract](../../../docs/benchmarking/backends.md)

Use Linux with a physical NVIDIA CUDA device, its driver, Helm 4 and the locked GPU/benchmarking dependencies. From the repository root:

```sh
hypothesis-helm-benchmark --execution-backend gpu nesting --output .cache/benchmarks/gpu/nesting
```

Use the matching CPU parameters and seeds for a paired comparison. A successful run retains backend receipts with the actual engine, native work, host fallbacks and measurement hashes. Publishing requires those receipts; CPU measurements cannot populate this directory as GPU observations.

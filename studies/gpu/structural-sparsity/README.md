# structural-sparsity: GPU study

<!-- toc:start -->
**Table of contents**

- [structural-sparsity: GPU study](#structural-sparsity-gpu-study)
<!-- toc:end -->

**Status: not measured on a GPU.**

Finite planning and filtering with distant relevant inputs.

[CPU study](../../cpu/structural-sparsity/README.md) | [Backend contract](../../../docs/benchmarking/backends.md)

Use Linux with a physical NVIDIA CUDA device, its driver, Helm 4 and the locked GPU/benchmarking dependencies. From the repository root:

```sh
hypothesis-helm-benchmark --execution-backend gpu structural-sparsity --output .cache/benchmarks/gpu/structural-sparsity
```

Use the matching CPU parameters and seeds for a paired comparison. A successful run retains backend receipts with the actual engine, native work, host fallbacks and measurement hashes. Publishing requires those receipts; CPU measurements cannot populate this directory as GPU observations.

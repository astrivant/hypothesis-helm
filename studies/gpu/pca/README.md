# pca: GPU study

<!-- toc:start -->
**Table of contents**

- [pca: GPU study](#pca-gpu-study)
<!-- toc:end -->

**Status: not measured on a GPU.**

Finite population planning before output projection and filtering comparisons.

[CPU study](../../cpu/pca/README.md) | [Backend contract](../../../docs/benchmarking/backends.md)

Use Linux with a physical NVIDIA CUDA device, its driver, Helm 4 and the locked GPU/benchmarking dependencies. From the repository root:

```sh
hypothesis-helm-benchmark --execution-backend gpu pca --output .cache/benchmarks/gpu/pca
```

Use the matching CPU parameters and seeds for a paired comparison. A successful run retains backend receipts with the actual engine, native work, host fallbacks and measurement hashes. Publishing requires those receipts; CPU measurements cannot populate this directory as GPU observations.

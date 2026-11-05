# error-surface: GPU study

<!-- toc:start -->
**Table of contents**

- [error-surface: GPU study](#error-surface-gpu-study)
<!-- toc:end -->

**Status: not measured on a GPU.**

Fresh finite planning for every filtering strategy and error placement.

[CPU study](../../cpu/error-surface/README.md) | [Backend contract](../../../docs/benchmarking/backends.md)

Use Linux with a physical NVIDIA CUDA device, its driver, Helm 4 and the locked GPU/benchmarking dependencies. From the repository root:

```sh
hypothesis-helm-benchmark --execution-backend gpu error-surface --output .cache/benchmarks/gpu/error-surface
```

Use the matching CPU parameters and seeds for a paired comparison. A successful run retains backend receipts with the actual engine, native work, host fallbacks and measurement hashes. Publishing requires those receipts; CPU measurements cannot populate this directory as GPU observations.

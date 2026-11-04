# error-surface-quartic: GPU study

<!-- toc:start -->
**Table of contents**

- [error-surface-quartic: GPU study](#error-surface-quartic-gpu-study)
<!-- toc:end -->

**Status: not measured on a GPU.**

Fits retained error-surface observations from the selected backend.

[CPU study](../../cpu/error-surface-quartic/README.md) | [Backend contract](../../../docs/benchmarking/backends.md)

Use Linux with a physical NVIDIA CUDA device, its driver, Helm 4 and the locked GPU/benchmarking dependencies. From the repository root:

```sh
hypothesis-helm-benchmark --execution-backend gpu polynomial-surface --input .cache/benchmarks/gpu/error-surface/results.json --output .cache/benchmarks/gpu/error-surface-quartic
```

Use the matching CPU parameters and seeds for a paired comparison. A successful run retains backend receipts with the actual engine, native work, host fallbacks and measurement hashes. Publishing requires those receipts; CPU measurements cannot populate this directory as GPU observations.

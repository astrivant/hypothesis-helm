# discovery: GPU study

<!-- toc:start -->
**Table of contents**

- [discovery: GPU study](#discovery-gpu-study)
<!-- toc:end -->

**Status: not measured on a GPU.**

Finite interaction planning and defect recall at increasing strengths.

[CPU study](../../cpu/discovery/README.md) | [Backend contract](../../../docs/benchmarking/backends.md)

Use Linux with a physical NVIDIA CUDA device, its driver, Helm 4 and the locked GPU/benchmarking dependencies. From the repository root:

```sh
hypothesis-helm-benchmark --execution-backend gpu discovery --output .cache/benchmarks/gpu/discovery
```

Use the matching CPU parameters and seeds for a paired comparison. A successful run retains backend receipts with the actual engine, native work, host fallbacks and measurement hashes. Publishing requires those receipts; CPU measurements cannot populate this directory as GPU observations.

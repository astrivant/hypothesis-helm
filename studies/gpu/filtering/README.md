# filtering: GPU study

<!-- toc:start -->
**Table of contents**

- [filtering: GPU study](#filtering-gpu-study)
<!-- toc:end -->

**Status: not measured on a GPU.**

Production chart testing, including finite planning and filtering phase timings.

[CPU study](../../cpu/filtering/README.md) | [Backend contract](../../../docs/benchmarking/backends.md)

Use Linux with a physical NVIDIA CUDA device, its driver, Helm 4 and the locked GPU/benchmarking dependencies. From the repository root:

```sh
hypothesis-helm-benchmark --execution-backend gpu filtering --output .cache/benchmarks/gpu/filtering
```

Use the matching CPU parameters and seeds for a paired comparison. A successful run retains backend receipts with the actual engine, native work, host fallbacks and measurement hashes. Publishing requires those receipts; CPU measurements cannot populate this directory as GPU observations.

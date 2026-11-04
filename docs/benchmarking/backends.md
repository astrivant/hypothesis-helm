# CPU and GPU study execution

<!-- toc:start -->
**Table of contents**

- [Run a paired study](#run-a-paired-study)
- [Where flag-controlled work runs](#where-flag-controlled-work-runs)
- [Receipts, replay and publication](#receipts-replay-and-publication)
- [Maintain the inventory](#maintain-the-inventory)
<!-- toc:end -->

Backend-dependent studies publish under `studies/cpu/<study>/` and
`studies/gpu/<study>/`. Studies without finite predicate planning stay directly
under `studies/`. The [complete inventory](../../studies/README.md) records the
reason for every classification.

Historical CPU pages retain their original reference measurements. GPU pages
begin as unmeasured study definitions. Moving a report or duplicating a study
definition does not create a new observation, establish a speedup, or demonstrate
physical GPU execution.

## Run a paired study

Use Python 3.13, Poetry, and Helm 4. From the repository root, install the locked
benchmarking and compiled CPU dependencies:

```sh
poetry install --extras benchmarking --extras cpu --with dev
poetry run hypothesis-helm-benchmark --execution-backend cpu-vector --backend-verify \
    discovery --input-complexity 4 --max-strength 2 --time-limit 30s \
    --output .cache/benchmarks/cpu/discovery-paired
```

On Linux with a physical NVIDIA CUDA device and compatible driver, or macOS with
an available Apple Metal device, use the same inputs, seeds and limits:

```sh
poetry install --extras benchmarking --extras gpu --with dev
poetry run hypothesis-helm-benchmark --execution-backend gpu --backend-verify \
    discovery --input-complexity 4 --max-strength 2 --time-limit 30s \
    --output .cache/benchmarks/gpu/discovery-paired
```

Place execution controls before the study command. The same options apply to
`hypothesis-helm test` and `scan` after their subcommand. `reference` retains the
Python oracle; `cpu-vector` and `gpu` execute the same integer predicate program.
Compiled backends fail if unavailable unless `--backend-fallback reference` was
explicitly requested. Fallback observations cannot be published as GPU results.
The GPU extra uses PyTorch 2.15 for Python 3.13 through 3.15. It selects CUDA
when available, then Apple Metal. Linux CUDA requires a compatible NVIDIA driver
for PyTorch's CUDA 13.2 wheel; PyTorch 2.15 requires macOS 15 or later for Metal.
The Linux extra pins the native cuBLAS and NVRTC packages to the versions in the
[CUDA 13.2.2 toolkit](https://pypi.org/project/cuda-toolkit/13.2.2/). GPU execution
rejects Metal's optional CPU fallback. The CPU compiler
retains its own NumPy compatibility constraints when the CPU extra is installed.
The GPU backend evaluates the integer predicate graph with tensor operations;
device choice and workload size affect launch and transfer costs, so measure the
complete run before assuming a speedup. Receipts record `cuda` or `mps`, and a
published study must contain completed work from one device type without fallback.
The configured memory budget admits plan buffers, batch scratch and estimated
tensor temporaries; PyTorch's allocator cache and other device users are outside
that estimate. PyTorch out-of-memory errors during evaluation use the existing
bounded batch-splitting path.

`--backend-verify` compares every definitive compiled predicate with the host
validator. Keep that check for correctness comparisons; its extra validation is
part of the observed runtime. Paired speed measurements must use the same
verification setting and describe compilation, transfer, planning and execution
costs separately. No speedup is assumed before measurement.

## Where flag-controlled work runs

The finite planner consolidates full-strength permutations, automatic exhaustive
promotion, and interaction-group completion through one bounded schema-predicate
engine. Exhaustive plans submit consecutive batches rather than a device launch
per assignment. Explicit `--exhaustive` uses the same concrete-case encoder and
predicate kernel while retaining the existing enumeration order and limits.

| Controls | Compiled CPU/GPU work | Host responsibility |
| --- | --- | --- |
| `--permutations`, `--exhaustive-threshold` | Finite schema predicates for ordered candidates; one batched pass for full enumeration | Factor extraction, coverage targets, logical budgets, accepted-case ordering |
| `--exhaustive` | Predicate checks for encodable concrete candidates | Domain construction, unsupported shapes, exact original order and bounds |
| `--exhaustive-group`, inferred groups | Candidate constraint checks use the same compiled planner | Group discovery, required coverage and source diagnostics |
| `--filter`, `--filter-adaptive`, random/topology filter controls | Their upstream finite candidate planning uses the selected backend | Template specialization, exact region identities, seeded sampling, calibrated floors and protected cases |
| `--expand-failures`, rejection filtering | Their initial finite plan uses the selected backend | Observed failures, effectful callbacks and ordered expansion |
| Traversal and sensitivity ordering | Their input plan uses the selected backend | Deterministic ranking, mutation rendering and side effects |
| Exact-equivalence pruning and render caches | No device execution of template strings or hashes | Source-bound witnesses, rendered outputs and cache ownership |

Schema `allOf`, `anyOf`, `oneOf`, `not`, `if/then/else`, requiredness and finite
scalar constraints compose inside the same predicate graph. Unsupported fragments
remain unknown and require authoritative host validation. A predicate result
never counts as a Helm render or a successful property test.

The suitable device boundary is repeated, pure, bounded integer work. Template
interpretation, irregular string structures, Python callbacks, filesystem and
Helm execution retain their host contracts. Moving those operations would require
separate semantic support and measurement; batching alone cannot establish that
it would improve them.

## Receipts, replay and publication

Each backend-dependent command retains `backend.json` beside its measurements
and a readable `BACKEND.md`. The receipt records the requested controls, every
completed planner's actual engine and counters, and hashes of the measurement
files. Physical candidate evaluations include speculative work. Logical and
committed counts remain separate, and committed selections are not completed
chart tests.

Plot-only runs retain the original receipt. Shard merging checks that input
receipts match the requested backend and controls before combining measurements.
Derived polynomial fits inherit the receipt of their source error surface.
Publication rejects mismatched lanes, missing native evidence and GPU fallbacks.
Legacy unlabelled data remains eligible only for the reference CPU lane.

The local refresh accepts the same backend controls and retains them in each
dependent study's resumable operation record:

```sh
poetry run hypothesis-helm-refresh --execution-backend cpu-vector --dry-run
poetry run hypothesis-helm-refresh --execution-backend gpu --dry-run
```

These commands inspect the plan without running studies. Shared studies retain
their host execution and shared destination. A full refresh includes its existing
preparation, publication and repository-scan work; remove `--dry-run` only when
that full operation is intended. GPU execution requires an already provisioned
and authorized device; these commands do not create infrastructure.

## Maintain the inventory

The inventory is declared once in the benchmarking package and exposed through
the existing command:

```sh
poetry run hypothesis-helm-benchmark inventory --scope backend --backend gpu
poetry run hypothesis-helm-benchmark inventory --check-layout
poetry run hypothesis-helm-benchmark inventory --write-layout
```

`--write-layout` moves legacy backend-dependent results to the CPU lane, repairs
local Markdown links, refreshes indexes, and creates missing unmeasured GPU
guides. It refuses a collision with an existing CPU directory and preserves
existing GPU publications. `--check-layout` performs no writes. Update the
classification when an implemented execution path changes, then regenerate and
review the layout.

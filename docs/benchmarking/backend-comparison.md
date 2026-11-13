# Matched CPU and GPU benchmarks

<!-- toc:start -->
**Table of contents**

- [Start the comparison](#start-the-comparison)
- [Execution and ownership](#execution-and-ownership)
- [Interpret the measurements](#interpret-the-measurements)
- [Reproduce locally](#reproduce-locally)
<!-- toc:end -->

A GPU refresh includes a bounded, matched finite-planner comparison. It runs
`reference`, `cpu-vector` and `gpu` against the same frozen program, candidate
order, seed, batch sizes and repetition count. This compares the production worker
boundary; the existing chart studies retain their own backend selection.

## Start the comparison

From any directory, with GitHub CLI authenticated and access to the configured
GPU runner, dispatch the current review branch:

```sh
gh workflow run ci.yml \
    --repo astrivant/hypothesis-helm \
    --ref revert-16-revert-15-feat/compiled-backends \
    -f refresh=true \
    -f benchmark-backend=gpu \
    -f pull-request=17
```

After merge, use `--ref main` and omit `-f pull-request=17`. This starts the full
refresh as well as the matched comparison. GPU runner time is billed; the
comparison has one additional GPU job with a 20-minute timeout. It is not started
by ordinary PR, main or tag checks. Those checks run a small real-device acceptance
case through the existing differential-test jobs instead.

## Execution and ownership

1. Freeze a workload manifest bound to the immutable source, run and attempt.
2. Run three independent lanes with identical inputs. Reference and compiled CPU
   use standard Linux x64 runners (4 vCPU, 16 GiB RAM). GPU uses the configured
   Linux x64 T4 runner (4 vCPU, 28 GiB RAM, 16 GiB GPU memory).
3. Verify each ordered result against an independent host oracle. GPU fallback
   to CPU is rejected. Record actual hardware, exact Python/NumPy/compiler
   versions, plan and output hashes, setup, first-pass and repeated timings.
4. Require all lanes and matching source, settings and common runtime before
   rendering the comparison. Preserve slower results; speedup is a measurement,
   not an assertion that must pass.
5. Join the comparison with the existing study refresh at its single publisher.
   Commit the compact JSON measurements, manifest, README and PNG/SVG plots to
   the requested branch. A changed source or conflicting publication retains
   results as CI artifacts instead. Comparison artifacts also remain available
   if another study fails before publication.

Job names identify the backend and hardware, including shared studies that remain
on CPU during a GPU refresh. They do not imply those CPU studies ran on a GPU.

## Interpret the measurements

The first full candidate pass follows worker setup and includes lazy compilation.
Subsequent passes use that warmed worker. Each batch-size case gets a new worker.
Plots show median steady-pass latency, setup plus cold-pass time, and steady
speedup relative to the reference median. Error bars show the sample standard
deviation across repetitions, not a confidence interval.

Wall latency includes worker IPC, packing, device transfers, synchronization and
output decoding. Engine-reported transfer-inclusive time and separate host
verification time are retained in JSON. These measurements do not isolate GPU
kernel time and do not establish an end-to-end Helm rendering speedup. Hardware
and compiler differences are recorded alongside the results.

## Reproduce locally

From the repository root, install the locked benchmarking and desired native
extras. NVIDIA execution requires a CUDA driver and device; macOS can explicitly
select MPS. Prepare one manifest and reuse it for every lane:

```sh
poetry install --extras benchmarking --extras cpu --extras gpu --with dev
poetry run hypothesis-helm-benchmark backend-comparison prepare \
    --source "$(git rev-parse HEAD)" --run local \
    --output .cache/backend-comparison/workload.json
poetry run hypothesis-helm-benchmark backend-comparison measure \
    --input .cache/backend-comparison/workload.json --backend reference \
    --require-device reference --output .cache/backend-comparison/reference.json
poetry run hypothesis-helm-benchmark backend-comparison measure \
    --input .cache/backend-comparison/workload.json --backend cpu-vector \
    --require-device cpu --output .cache/backend-comparison/cpu-vector.json
poetry run hypothesis-helm-benchmark backend-comparison measure \
    --input .cache/backend-comparison/workload.json --backend gpu \
    --require-device cuda --output .cache/backend-comparison/gpu.json
poetry run hypothesis-helm-benchmark backend-comparison report \
    --input .cache/backend-comparison/workload.json \
    --lanes .cache/backend-comparison/reference.json \
    .cache/backend-comparison/cpu-vector.json .cache/backend-comparison/gpu.json \
    --output .cache/backend-comparison/report
```

Use `--require-device mps` for an explicitly selected MPS experiment. INFO audit
messages go to stderr by default; add the parent command's `--debug` before
`backend-comparison` for debug logging. The manifest's `prepare --help` documents
bounded workload and repetition controls.

After CI publishes results, redraw without running any benchmark:

```sh
poetry run hypothesis-helm-benchmark backend-comparison report \
    --input studies/backend-comparison/workload.json \
    --lanes studies/backend-comparison/measurements.json \
    --output .cache/backend-comparison/replot
```

The [reusable stage](../../.github/workflows/stage-backend-comparison.yml) implements
same-run artifact handoffs using GitHub's
[reusable workflows](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows)
and [workflow artifacts](https://docs.github.com/en/actions/tutorials/store-and-share-data).

# Phase resource measurements

<!-- toc:start -->
**Table of contents**

- [Capture and read](#capture-and-read)
- [Phases and ownership](#phases-and-ownership)
- [Metrics and ranking](#metrics-and-ranking)
- [Measurement references](#measurement-references)
<!-- toc:end -->

Use independent resource rankings to locate expensive phases before choosing an
optimization. A wall-time improvement does not establish lower CPU, RAM or GPU use.
Instrumentation is opt-in and remains separate from uninstrumented timing studies.

## Capture and read

With the benchmark package and Helm installed, run from a project checkout:

```sh
hypothesis-helm-benchmark --profile .cache/benchmarks/profiles filtering \
    --inputs 6 --depths 1 --repeats 1 --time-limit 30s \
    --output .cache/benchmarks/profiled-filtering
```

The command prints its unique `profile-*` directory. Its `flamegraphs/resources/`
contains independent ranked tables and PNG/SVG panels in `README.md`, and exact
recorded amounts with observation coverage in `rankings.json`. CPU comparisons
remain in the ordinary study output. Selecting `--execution-backend gpu` before
the study requires the optional GPU dependencies and a physical device; it does
not automatically obtain or provision a GPU runner.

Use the existing redraw command with a saved capture directory to regenerate the
tables and figures without repeating the workload:

```sh
hypothesis-helm-benchmark flamegraph .cache/benchmarks/profiles/profile-EXAMPLE \
    --output .cache/benchmarks/redrawn-profiles
```

Replace `profile-EXAMPLE` with the directory printed by the capture. Repository
refreshes also collect small, separate scaling and finite-filtering profiles.
Their resource reports are published beside the flame graphs. The finite profile
uses the refresh's selected backend, including its isolated native worker.

## Phases and ownership

Classification follows known source boundaries: candidate generation, schema
validation, exact-equivalence analysis, topology filtering, backend preparation
and IPC, predicate evaluation, Helm rendering, YAML parsing and serialization,
manifest validation, property checks, and reporting. A descendant inherits its
nearest classified caller unless it enters another known boundary. Remaining
work stays in **Other and orchestration**. This is a measurement classification,
not a claim of complete semantic intent coverage.

Raw captures retain the actual calling contexts. The coordinator, renderer
workers and native backend processes own separate captures and rankings. Sampling
threads are stopped and joined before writing completed files. Ordinary execution
does not import benchmark instrumentation into the native worker.

## Metrics and ranking

| Resource | Measurement | Aggregation and limits |
| --- | --- | --- |
| Wall time | Monotonic seconds between exclusive phase transitions | Sum within each process role; overlapping process wall times are not pipeline duration. |
| CPU | User plus system CPU seconds across the process's threads | Sum exclusive deltas. Includes profiler and sampler overhead; excludes child CPU. |
| Child CPU | CPU of terminated, waited-for descendants | Separate counter attributed when reaped. May overlap independently captured worker CPU; never add it to those workers' CPU. |
| RAM | Linux process RSS at transitions and at 25 ms intervals | Largest observation, with sample counts. A lower bound on peak RSS; retained memory can appear in several phases. Not allocation growth or concurrent process-tree RAM. |
| GPU time | CUDA events bracketing a native predicate evaluation on its current stream | Sum synchronized stream intervals. Includes possible host-launch idle gaps; does not measure kernel-active time, SM utilization or all streams. |
| GPU memory | PyTorch CUDA allocator high-water mark during each isolated evaluation | Maximum across observations, including retained input buffers. Excludes driver/external allocations and setup-only peaks. Reset only in the exclusively owned instrumented backend worker. |
| Disk reads | Linux `/proc/self/io` `read_bytes` deltas | Storage-layer bytes for this process and waited-for children; never sum parent and worker counters. Cached reads need not increase this counter. |
| Disk writes | Linux `/proc/self/io` `write_bytes` deltas | Process and waited-for child bytes dirtied, which may later be cancelled or never flushed. Not final artifact size or disk footprint. |

Each metric has its own descending ranking, with alphabetical tie ordering.
Complete additive measurements receive a share of that resource's recorded total.
Peaks are never summed and have no percentage share. A partially observed phase
retains its observed subtotal but receives no rank. Unknown or interrupted capture
coverage suppresses percentage claims. An observed zero remains different from an
unsupported or unobserved value.

Linux procfs measurements are unavailable on other platforms or when procfs access
is denied. Metal device time and memory, GPU setup peaks, unprofiled subprocess
RAM, unreaped child I/O, network traffic, and disk footprint are currently unavailable. CPU
and wall time remain usable on supported Unix hosts. These omissions are shown
explicitly; the report does not infer resource costs from wall time.

Resource collection runs only under `--profile`. Normal studies retain their
original timing behavior. A failed workload still writes completed captures in
`finally`; lost hooks are marked partial. Forced process termination can prevent
a final capture and is not evidence of zero work.

## Measurement references

- Python [`getrusage`](https://docs.python.org/3/library/resource.html#resource.getrusage)
  defines process CPU and terminated-child accounting; block operations are not bytes.
- Linux [`/proc` I/O accounting](https://docs.kernel.org/filesystems/proc.html)
  distinguishes storage bytes, ordinary read/write calls and cancelled writes.
  The [process I/O contract](https://man7.org/linux/man-pages/man5/proc_pid_io.5.html)
  includes waited-for children, so parent and worker counters can overlap.
- PyTorch [CUDA events](https://docs.pytorch.org/docs/stable/generated/torch.cuda.Event.html)
  report elapsed milliseconds between completed events.
- PyTorch [allocator peaks](https://docs.pytorch.org/docs/stable/generated/torch.cuda.memory.max_memory_allocated.html)
  describe allocator-owned memory, rather than total device residency.

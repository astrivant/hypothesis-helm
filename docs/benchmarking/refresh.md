# Repository refresh helpers

<!-- toc:start -->
**Table of contents**

- [Recovering an interrupted refresh](#recovering-an-interrupted-refresh)
- [Parallel refresh on GitHub Actions](#parallel-refresh-on-github-actions)
<!-- toc:end -->

[Full refresh command](README.md#reproduce-the-full-project-run) · [Benchmark results](<../../studies/README.md>)

These scripts prepare charts, run measurements, generate plots and publish reports.
The operation inventory lives in `pkg/hypothesis_helm_benchmarking/refresh/plan.py`.

Fresh runs first rebuild and verify the pinned compiler inventory and Kubernetes input catalog, run the Go extractor tests,
build the optional renderer, and regenerate reference documentation. Project checks then exercise those prepared dependencies
before initialization freezes the measured source. See [dependency preparation](../dependencies.md#repository-refresh-integration)
for the individual operations, pins and caches. Go is required for a full refresh; upstream version upgrades remain explicit.

Refresh workspaces and internal records live under `.cache/refresh/refresh-<epoch>/`.
That includes logs, timestamps, process journals, verification results, source snapshots and checksum inventories.
They are generated when needed and are not required in a fresh checkout.

The terminal shows each operation's stdout and stderr as it runs, prefixed with its name, such as `[checks]` or `[performance]`.
The complete, unprefixed output is also saved in `logs/<operation>.log`. Repository scans forward chart diagnostics while keeping
their JSON results in separate files. CI uses the same live output without progress bars.

Final chart scan reports are published under `docs/reports/`; benchmark studies and plots live in top-level `studies/`.
Raw measurements, generated charts, logs, profiles and verification records stay inside the refresh workspace under `.cache/refresh/`.
Repository workers also use that workspace, under `repositories/`; they never write into the published report directory.
Reusable chart definitions remain in the benchmarking package's `assets/fixture/`.
Every fresh refresh runs Bitnami, then Prometheus, after the synthetic studies and diagrams finish.
Both scans use `--filter --disable-codes HH2006 --jobs 6 --chart-timeout 5m --max-examples 10 --seed 0 --no-cache --shard none`.
Charts run sequentially, with six path workers per chart; CI shard variables do not partition these scans.
Successful report verification updates both Markdown/PDF reports and the root README's counts and links.
`HH2006` suppression hides opaque-object warnings while leaving their inputs testable and all other findings enabled.
Saved runs retain their recorded policy when resumed.
Each study validates its measurements and required plots before the next study starts. A final verification checks the
complete set before publication, so an invalid study cannot silently contribute to the published results.

## Recovering an interrupted refresh

Refresh keeps completed measurements in its workspace after a failure. Keep that directory, including its
`operations.json`, logs, frozen source and checksum records. To continue the latest attempt:

```sh
bash scripts/project-run.sh hypothesis-helm-refresh --resume --dry-run
bash scripts/project-run.sh hypothesis-helm-refresh --resume
```

You can also select a particular journal:

```sh
hypothesis-helm-refresh --resume .cache/refresh/refresh-<epoch>/operations.json --dry-run
hypothesis-helm-refresh --resume .cache/refresh/refresh-<epoch>/operations.json
```

Completed operations are preserved. Failed and unstarted operations run again in dependency order, under the refresh lock.
Each continuation writes a new `resumed-<timestamp>/operations.json` and logs. Bare `--resume` selects the latest continuation;
when supplying a path explicitly, use **that continuation's** journal on the next attempt.
Recovery verifies the frozen source hashes; it does not resume inside an individual benchmark. An unfinished study or profiling
stage starts again with a fresh output directory. Its previous output is retained under the continuation's `prior-attempts/`;
completed studies are not rerun or moved. Topology inventory rebuilding avoids duplicate chart jobs.
Fix the cause of the failure before resuming. Starting a fresh refresh still refuses an unfinished workspace.

If checks fail before initialization, resume uses the current checkout so your fixes take effect. Continuation journals live
under `logs/resumed-<timestamp>/` until initialization creates the measured source snapshot. Once initialization has started,
recovery requires that snapshot and verifies its hashes before continuing.

The refresh workspace owns all files needed for recovery, including repository scans under `repositories/`.
Published reports are replaceable outputs; keep the workspace if you want to resume or redraw a run.
During the repository cleanup, historical raw data was moved into `.cache/benchmarks/` and `.cache/repository-scans/`.
The local `.cache/publication-relocations.json` records its former and current locations. Historical recipes retain their
original paths; use the latest completed journal when inspecting those archived runs.

## Parallel refresh on GitHub Actions

Open the [CI pipeline](https://github.com/astrivant/hypothesis-helm/actions/workflows/ci.yml), select **Run workflow**,
and enable **refresh**. Once code checks, chart validation, packaging and smoke tests pass, preparation rebuilds the pinned
dependencies, checks the generated project and snapshots its inputs once.
GitHub runs each declared study on a separate runner, using the same source snapshot and parameters.
The matrix comes from the Python study inventory, so adding a study also adds its CI job.
There is no `max-parallel` setting: GitHub schedules as many jobs as the account's capacity and runner availability permit.
See [GitHub's matrix concurrency documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idstrategymax-parallel).

Each study owns its output directory, status file and process journal. A failed study retains diagnostics without cancelling
other studies. The final job requires every study to succeed, verifies the merged measurements, and publishes pages and plots
under `studies/`, then runs Bitnami followed by Prometheus. Reports, studies, and the separate `refresh-resume-data` artifact
are retained for 30 days.
Jobs default to `ubuntu-latest`. Set `HH_CI_RUNNER` to the label of an available larger Ubuntu x64 runner to use more cores.

After pushing the workflow changes, launch it with:

```sh
gh workflow run ci.yml -f refresh=true
```

Local `bash scripts/project-run.sh hypothesis-helm-refresh` still runs timing studies sequentially on one machine to avoid CPU contention affecting
measurements. Its `--workers` option controls independent operations within that machine; the GitHub matrix supplies separate
machines for concurrent studies. Each GitHub study job has a six-hour execution limit.

Sensitivity measures 48 input changes and all 1,128 pairs on the shared benchmark chart, with 64 structural components and a nine-minute budget.
It retains the chart sources and mutation inputs, before publication and repository scans.
Publication updates `studies/sensitivity/`; raw sensitivity runs remain under `.cache/benchmarks/sensitivity/`.
The standalone `hypothesis-helm-benchmark sensitivity` command also updates that study automatically after a successful run.
Supplying `--output` keeps its results separate; refresh uses this option and publishes after verification.

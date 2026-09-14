# Refresh provenance

The [aggressive-filter matrix refresh](aggressive-matrices.json) supersedes the matrix, PCA, expansion and nesting artifacts below.
It adds `--filter` and `--filter-aggressive`, including calibration fallback evidence. PCA uses the fresh expansion reference renders.
The structural timing matrix ran sequentially; expansion and nesting compare coverage and ran concurrently.
The remaining records on this page describe the earlier full-suite refresh.

## Earlier full-suite refresh

Fresh Helm 4 measurements; each independent run has a nine-minute execution ceiling. The studies ran sequentially, followed by chart graph exports. No earlier timing results were resumed.

The sequential synthetic suite took 60.5 minutes overall.

[Environment and source fingerprints](provenance.json) · [Study exit codes](status.tsv) · [Artifact checksums](sha256.json)

The chart fixtures, seeds, raw results, and command logs describe this run. Paths under
`.cache/benchmark-refresh-1789311940` identify its staging directory; published fixtures
and measurements are under `benchmarks/`. The helper scripts are maintained for
future refreshes with the current CLI. Use the [full refresh command](../README.md#reproduce-the-full-project-run)
to run the complete sequence from a checkout.

At the time of that full-suite refresh, all studies and graph exports used the same [recorded application sources](measured-source-hashes.json).

The repository tests continue with a [preserved source snapshot](measured-source.tar.gz)
while the working CLI changes. This snapshot uses the earlier `scan LOCAL_PATH`
spelling; the current CLI uses `test LOCAL_PATH`. The measured implementation and
test budgets stay unchanged. [Continuation details](snapshot-transition.json).

This refresh excludes generated C0/C1 controls except LF and CR. Other Unicode text remains eligible. The finite Boolean benchmark domains are unchanged; the text policy primarily affects repository path sampling. Filtering precedes seeded random traversal.

Timing is from one host and one repetition. Deadline-censored trajectories are reported as incomplete work, not extrapolated completed checks. Graph baselines are observations, not Kubernetes API schema validation.

## Study directory layout

Published outputs now live under [`benchmarks/studies/`](../studies/README.md), including the performance results formerly at the root.
The [relocation record](studies-relocation.json) maps original paths to current paths and records hashes before and after the move.
Measurement JSON, CSV, plots and fixtures are unchanged; Markdown links were rebased.
Older provenance records retain their original paths. The current [artifact checksums](sha256.json) use the new layout;
the prior ledger is retained as [sha256-before-studies.json](sha256-before-studies.json).

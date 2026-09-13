# Refresh provenance

Fresh Helm 4 measurements; each independent run has a nine-minute execution ceiling. The studies ran sequentially, followed by chart graph exports. No earlier timing results were resumed.

The sequential synthetic suite took 58.8 minutes overall.

[Environment and source fingerprints](provenance.json) · [Study exit codes](status.tsv) · [Artifact checksums](sha256.json)

The retained shell commands, chart fixtures, seeds, raw results, and logs describe this run. Paths under `.cache/benchmark-refresh-1789265418` identify its staging directory; the published fixtures and measurements are now under `docs/benchmarks/`.

The graph renderer received explicit sorted parent traversal after timing finished. The [source patch](plotting-order.patch) and [measured source hashes](measured-source-hashes.json) record that plotting-only difference.

Timing is from one host and one repetition. Deadline-censored trajectories are reported as incomplete work, not extrapolated completed checks. Graph baselines are observations, not Kubernetes API schema validation.

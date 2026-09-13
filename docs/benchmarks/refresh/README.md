# Refresh provenance

Fresh Helm 4 measurements; each independent run has a nine-minute execution ceiling. The studies ran sequentially, followed by chart graph exports. No earlier timing results were resumed.

The sequential synthetic suite took 60.5 minutes overall.

[Environment and source fingerprints](provenance.json) · [Study exit codes](status.tsv) · [Artifact checksums](sha256.json)

The retained shell commands, chart fixtures, seeds, raw results, and logs describe this run. Paths under `.cache/benchmark-refresh-1789311940` identify its staging directory; the published fixtures and measurements are now under `docs/benchmarks/`.

All studies and graph exports use the same [recorded application sources](measured-source-hashes.json).

This refresh excludes generated C0/C1 controls except LF and CR. Other Unicode text remains eligible. The finite Boolean benchmark domains are unchanged; the text policy primarily affects repository path sampling. Filtering precedes seeded random traversal.

Timing is from one host and one repetition. Deadline-censored trajectories are reported as incomplete work, not extrapolated completed checks. Graph baselines are observations, not Kubernetes API schema validation.

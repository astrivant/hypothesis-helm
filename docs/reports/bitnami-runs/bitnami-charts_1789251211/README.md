# Retained Bitnami charts scan

This is the complete five-minute-per-chart production run used by
[the combined report](../../bitnami.md) and [PDF](../../bitnami.pdf).
Earlier runs elsewhere in `docs/reports/` are superseded and are not included.

- `scan.json`: combined results with portable artifact paths.
- `inventory.json`: discovered chart names and pinned versions, in job order.
- `charts.txt`: NUL-delimited input paths used by GNU Parallel.
- `joblog.tsv`: per-job command, timing, exit code, and signal.
- `jobs/N`: original scan JSON for inventory entry N (one-based), possibly including recursively discovered child charts.
- `supplemental-recursive-results.json`: additional nested-chart results, excluded from primary totals to avoid counting a chart twice.
- `jobs/N.err`: original standard error; `jobs/N.seq`: job sequence.
- `runs/`: dependency/lint logs, phase statistics, and saved failing values.
- `run-metadata.json`: source revision, settings, package versions, and implementation hashes.
- `finding-categories.json`: diagnostic groupings with the original errors.
- `transport-triage.json`: representative transport failure investigation.
- `follow-up-policy.json`: records withdrawal of the proposed budget escalation.
- `sha256.json`: checksums of retained files, excluding itself.

Each worker owns its artifact directory. The parent aggregates after every job
exits, so workers do not compete to write the final report. Process-local render
hashes are not shared across workers. Nonzero worker exits are retained findings
or incomplete/N/A results; consult each chart's status and phases.

The per-chart JSON retains the original results, with artifact paths updated to
the renamed run directory. Diagnostics can still contain absolute or temporary paths. Use the portable artifact links in the combined
report to find saved reproductions. Reported attempts include shrinking and may
repeat an input or rendered output.

The production run used the implementation hashes in `run-metadata.json`.
After it finished, Unicode serialization was corrected to avoid inflating long
map keys. `transport-triage.json` records the isolated before/after checks for
all four saved values-transport failures. These checks do not replace any
production chart result or claim that the affected chart passes all tests.

Final verification: 354 tests passed, one skipped; linting, formatting, typing,
docstrings, and generated CLI documentation checks passed. See `verification.log`
and `verification.json`. Both report formats include all 115 primary chart records.

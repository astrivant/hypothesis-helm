# Retained prometheus chart tests

This run supplies the [combined report](../../prometheus.md) and [PDF](../../prometheus.pdf).
It uses the pinned source checkout recorded in `run-metadata.json`.

- `scan.json.gz`: combined primary results with artifact links relative to `docs/reports/`.
- `inventory.json`: chart discovery records in job order.
- `charts.txt`: NUL-delimited paths consumed by GNU Parallel.
- `run.sh`: exact scan invocation; run from the project root with this directory as its argument.
- `finalize.py`: aggregation recipe; run with this directory and `prometheus` as arguments after all workers finish.
- `joblog.tsv`: timings, commands, exit codes, and process signals.
- `jobs/`: original per-worker JSON and stderr; JSON larger than 1 MB is losslessly gzip-compressed.
- `runs/`: per-chart diagnostics, phase statistics, and reproducing values.
- `supplemental-recursive-results.json`: nested results excluded from the primary totals.
- `verification.json`: inventory, ownership, settings, and completion checks.
- `run-metadata.json`: source revision and implementation hashes.
- `sha256.json`: retained-file checksums, excluding itself and disposable dependency caches.

Workers write separate artifact directories and use separate Helm cache directories.
A single finalizer verifies every primary chart and writes one Markdown/PDF report.
Large JSON files under `runs/` are also losslessly gzip-compressed. Use `gzip -dc FILE.json.gz` to read them.
Cache directories under `helm/cache-*` are disposable and excluded from provenance.
A completed repository traversal does not establish exhaustive input coverage.

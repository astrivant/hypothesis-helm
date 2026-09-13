#!/usr/bin/env bash
set -euo pipefail
root="${1:?refresh directory}"
while [[ ! -f "$root/all-finished-epoch.txt" ]]; do
  sleep 45
done
.venv/bin/python "$root/update-documentation.py" "$root" >"$root/logs/update-documentation.log" 2>&1
.venv/bin/python "$root/verify-publication.py" "$root" >"$root/logs/verify-publication.log" 2>&1
.venv/bin/ruff check . >"$root/logs/final-ruff.log" 2>&1
.venv/bin/ruff format --check . >>"$root/logs/final-ruff.log" 2>&1
cp "$root/update-documentation.py" "$root/verify-publication.py" "$root/complete-publication.sh" benchmarks/refresh/
cp "$root/publication-verification.json" benchmarks/refresh/
date +%s >"$root/publication-finished-epoch.txt"

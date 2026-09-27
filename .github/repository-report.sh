#!/usr/bin/env bash
set -euo pipefail
repository="${1:?repository name}"
case "$repository" in
    bitnami)
        title=Bitnami
        shards=40
        ;;
    prometheus)
        title=Prometheus
        shards=40
        ;;
    *)
        echo '::error::Unknown scan repository.'
        exit 2
        ;;
esac
if [[ "${GITHUB_EVENT_NAME:-}" != workflow_dispatch || "${GITHUB_REF:-}" != refs/heads/* ]]; then
    echo "::error::${title} publication is only allowed for manual branch runs."
    exit 2
fi

# Aggregate validates common settings, source identities and exclusive shard ownership.
status=0
poetry run hypothesis-helm aggregate ".cache/${repository}-shards"/*/report.json \
    --shards "$shards" --run-id "${SCAN_RUN_ID:?scan identity}" --output-dir ".cache/${repository}-final" || status=$?
if ((status != 0 && status != 1)); then
    echo "::error::${title} aggregation failed; reports will not be committed."
    exit "$status"
fi

# Publish a self-contained final report directory; raw shard data stays in Actions artifacts.
poetry run python - "$repository" <<'PY'
import json
import sys
from pathlib import Path
from hypothesis_helm.reporting.reports.repository import write_reports

repository = sys.argv[1]
report = json.loads(Path(f'.cache/{repository}-final/report.json').read_text())
write_reports(report, Path(f'docs/reports/{repository}/report'))
for name in ('README.md', 'docs/README.md'):
    path = Path(name)
    text = path.read_text()
    text = text.replace(f'reports/{repository}.md', f'reports/{repository}/report.md')
    text = text.replace(f'reports/{repository}.pdf', f'reports/{repository}/report.pdf')
    path.write_text(text)
PY

# PR branches retain verified reports as Actions artifacts without updating main.
if [[ "$GITHUB_REF" != refs/heads/main ]]; then
    echo "${title} reports are ready for download; report commits are restricted to main."
    exit 0
fi

# Only final human-readable reports are staged. No raw observations or unrelated edits.
mapfile -d '' -t reports < <(find "docs/reports/${repository}" -type f \( -name '*.md' -o -name '*.pdf' -o -name '*.png' -o -name '*.svg' \) -print0)
git add -- README.md docs/README.md "${reports[@]}"
if git diff --cached --quiet; then
    echo "${title} reports are unchanged."
    exit 0
fi
git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
git -c core.hooksPath=/dev/null commit -m "Update ${title} scan reports ($SCAN_RUN_ID)"
# Never force-push over changes that arrived while the report was being prepared.
git push origin HEAD:main

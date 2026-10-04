#!/usr/bin/env bash
set -euo pipefail
repository="${1:?repository name}"
case "$repository" in
    bitnami)
        title=Bitnami
        shards=80
        ;;
    prometheus)
        title=Prometheus
        shards=80
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
git diff --cached --quiet || {
    echo '::error::Unexpected staged changes before scan publication.'
    exit 2
}

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
import os
import sys
from pathlib import Path
from hypothesis_helm.reporting.documentation.summaries import replace_summary, repository_summary
from hypothesis_helm.reporting.reports.repository import write_reports
from hypothesis_helm.schemas.contracts import mapping, sequence

repository = sys.argv[1]
report = mapping(json.loads(Path(f'.cache/{repository}-final/report.json').read_text()))
expected = os.environ.get('SCAN_SOURCE_SHA')
records = [report, *sequence(report.get('shards', []))]
if expected and any(mapping(mapping(record).get('source', {})).get('revision') != expected for record in records):
    raise ValueError('Aggregated scan source does not match the requested commit')
stem = Path(f'docs/reports/{repository}/report')
title = 'Bitnami' if repository == 'bitnami' else 'Prometheus Community'
readme = Path('README.md')
summary = replace_summary(readme.read_text(), repository, repository_summary(report, title, stem))
write_reports(report, stem)
readme.write_text(summary)
for name in ('README.md', 'docs/README.md'):
    path = Path(name)
    text = path.read_text()
    text = text.replace(f'reports/{repository}.md', f'reports/{repository}/report.md')
    text = text.replace(f'reports/{repository}.pdf', f'reports/{repository}/report.pdf')
    path.write_text(text)
PY

# Include the compact audit attachments linked by the final reports; raw observations stay in artifacts.
mapfile -d '' -t reports < <(find "docs/reports/${repository}" -type f \
    \( -name '*.md' -o -name '*.pdf' -o -name '*.png' -o -name '*.svg' \
    -o -path "docs/reports/${repository}/report-data/*.audit.json.gz" \) -print0)
git add -- README.md docs/README.md "${reports[@]}"
if git diff --cached --quiet; then
    echo "${title} reports are unchanged."
    exit 0
fi
git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
git -c core.hooksPath=/dev/null commit -m "Update ${title} scan reports ($SCAN_RUN_ID)"
# Never force-push over changes that arrived while the report was being prepared.
git push origin "HEAD:$GITHUB_REF"
if [[ "$GITHUB_REF" != "refs/heads/${DEFAULT_BRANCH:?default branch}" ]]; then
    # Branch publication uses GITHUB_TOKEN, so start checks explicitly as refresh does.
    gh workflow run ci.yml --repo "$GITHUB_REPOSITORY" --ref "${GITHUB_REF#refs/heads/}"
fi

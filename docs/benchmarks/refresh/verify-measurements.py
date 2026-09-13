"""
Validate completed study ledgers before publication.
"""

import json
import sys
from collections import Counter
from pathlib import Path

root = Path(sys.argv[1])
expected = json.loads((root / "provenance.json").read_text())["code_sha256"]
summary = {}
for study in [
    "performance",
    "discovery",
    "bug-density",
    "sparsity",
    "topology-sparsity",
    "matrix",
    "pca",
    "expansion",
    "topology-depth",
    "nesting",
]:
    directory = root / "outputs" / study
    result = json.loads((directory / "results.json").read_text())
    metadata = result["metadata"]
    if "code_sha256" in metadata:
        assert metadata["code_sha256"] == expected, study
    assert "v4." in metadata.get("helm", metadata.get("helm_version", "")), (study, list(metadata))
    rows = result.get("points", result.get("rows", result.get("runs", [])))
    assert rows, study
    statuses = Counter(row.get("status", "unreported") for row in rows)
    assert set(statuses) <= ({"passed", "time-limit"} if study == "performance" else {"passed", "complete"}), (study, statuses)
    references = result.get("references", [])
    assert all(row["status"] == "complete" for row in references), study
    figures = list(directory.glob("*.png"))
    assert figures, study
    for figure in figures:
        assert figure.stat().st_size > 1000
    vectors = list(directory.glob("*.svg"))
    assert vectors and all(figure.stat().st_size > 1000 for figure in vectors), study
    summary[study] = {
        "rows": len(rows),
        "statuses": dict(statuses),
        "references": len(references),
        "figures": len(figures),
        "vector_figures": len(vectors),
    }
(root / "measurement-verification.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))

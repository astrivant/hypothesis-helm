"""
Regenerate the fixed-count discovery fixture from its original seed and fault orders.
"""

import json
import sys
from pathlib import Path

from attrs import asdict
from hypothesis_helm.benchmarking.benchmark_discovery import faults, fixture

root = Path(sys.argv[1])
defects = faults(8, 6, 12, 2026)
chart = root / "outputs/discovery/chart"
fixture(chart, 8, defects)
metadata_path = chart / "benchmark.json"
metadata = json.loads(metadata_path.read_text())
metadata["bugs"] = {
    "definition": "legacy fixed fault count per interaction order",
    "seed": 2026,
    "total_faults": len(defects),
    "faults": [asdict(defect) for defect in defects],
}
metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
original = json.loads(Path("docs/benchmarks/discovery/chart/benchmark.json").read_text())
assert metadata["bugs"] == original["bugs"]
print(f"Regenerated {len(defects)} fixed discovery faults", flush=True)

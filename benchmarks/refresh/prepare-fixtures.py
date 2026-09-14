"""
Retain named parameter presets for the single benchmark chart definition.
"""

import sys
from pathlib import Path

from attrs import asdict
from hypothesis_helm.benchmarking.charts.parameters import Parameters
from hypothesis_helm.benchmarking.studies.discovery import faults
from hypothesis_helm.charts import yamlio

root = Path(sys.argv[1]) / "parameters"
root.mkdir(parents=True, exist_ok=True)
for name, settings in {
    "standard": Parameters(input_complexity=100, output_bins=256),
    "topology": Parameters(input_complexity=10, output_bins=4, topology=True),
    "discovery": Parameters(input_complexity=8),
}.items():
    document = {"parameters": asdict(settings)}
    if name == "discovery":
        document["operations"] = {"faults": {"faults": [asdict(defect) for defect in faults(8, 6, 12, 2026)]}}
    (root / f"{name}.yaml").write_text(yamlio.dump(document))

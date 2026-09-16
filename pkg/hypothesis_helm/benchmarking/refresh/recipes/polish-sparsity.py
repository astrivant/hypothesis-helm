"""
Redraw measured sparsity figures with sample labels that do not collide.
"""

import json
import sys
from pathlib import Path

from hypothesis_helm.benchmarking.studies.sparsity import plot
from matplotlib import pyplot as plt

root = Path(sys.argv[1])
with plt.rc_context({"xtick.labelsize": 8}):
    for study in ["sparsity", "structure-sparsity"]:
        directory = root / "outputs" / study
        result = json.loads((directory / "results.json").read_text())
        plot(directory, result["runs"], result["metadata"]["reference"])

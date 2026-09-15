"""
Publish fresh profiling captures separately from uninstrumented timing measurements.
"""

import hashlib
import json
import shutil
import sys
import tarfile
from pathlib import Path

root = Path(sys.argv[1])
profiles = list((root / "profiles").glob("profile-*"))
if len(profiles) != 1:
    raise ValueError("A refresh requires exactly one fresh profiling invocation")
source = profiles[0]
index = json.loads((source / "flamegraphs/index.json").read_text())
if index["incomplete_captures"] or not index["worker_processes"]:
    raise ValueError("Flame graphs require complete coordinator and worker captures")
if not any(figure["name"].startswith("coordinator-") for figure in index["figures"]):
    raise ValueError("Flame graphs require a coordinator capture")
target = root / "outputs/flamegraphs"
shutil.copytree(source / "flamegraphs", target, dirs_exist_ok=False)
with tarfile.open(target / "captures.tar.gz", "w:gz") as archive:
    for path in sorted(source.glob("*.json")):
        archive.add(path, arcname=path.name)
lines = [
    "# Flame graphs",
    "",
    "[Benchmarking](../../benchmarks/README.md#flame-graphs-across-worker-cores)",
    "",
    "Fresh captures from a separate scaling run with four cases and one or two workers.",
    "Profiling adds overhead, so these captures do not contribute to the uninstrumented timing studies.",
    "",
    "Wider boxes mean more time in a function and its children; stacked boxes show who called whom.",
    "Combined workers sum overlapping process time. Helm waits appear under Python callers; Helm internals are not profiled.",
    "",
    f"Captured {index['captures']} profiles across {index['worker_processes']} worker processes.",
    "Recording limits and incomplete captures are reported in the [capture index](index.json).",
    "[Raw captures](captures.tar.gz) retain the measured stacks for redrawing.",
    "",
]
for figure in index["figures"]:
    for extension in ("png", "svg"):
        if not (target / figure[extension]).is_file():
            raise ValueError(f"Missing flame graph: {figure[extension]}")
    lines.extend(
        [
            f"## {figure['name']}",
            "",
            f"![{figure['name']}]({figure['png']})",
            "",
            f"[Open zoomable SVG]({figure['svg']})",
            "",
        ]
    )
(target / "README.md").write_text("\n".join(lines))
checksums = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in target.iterdir() if path.is_file()}
(target / "sha256.json").write_text(json.dumps(checksums, indent=2) + "\n")
print(f"Published {len(index['figures'])} fresh flame graphs with raw captures")

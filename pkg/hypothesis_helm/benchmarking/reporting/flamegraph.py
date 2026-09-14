"""
Render observed Python calling-context trees as Matplotlib flame graphs.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

from hypothesis_helm.benchmarking.charts.fixture import FixtureWorkspace
from hypothesis_helm.benchmarking.execution.profiling import Frame
from hypothesis_helm.benchmarking.reporting.descriptions import describe
from hypothesis_helm.schemas.contracts import mapping, sequence


def merge(profiles: list[dict[str, object]]) -> list[Frame]:
    """
    Sum exclusive durations only when their complete caller paths match.

    Args:
        profiles (list[dict[str, object]]): Completed captures with parent-before-child frame arrays.

    Returns:
        list[Frame]: Combined tree preserving recursion and distinct caller contexts.
    """
    frames = [Frame("profiled entry", -1)]
    children: dict[tuple[int, str], int] = {}
    for profile in profiles:
        if profile.get("format") != "hypothesis-helm-profile-v1":
            raise ValueError("Unsupported profile format; expected captured Python call stacks")
        originals = sequence(profile["frames"])
        if not originals:
            raise ValueError("A profile must contain a root frame")
        remap = {0: 0}
        for index, entry in enumerate(originals):
            item = mapping(entry)
            parent = int(str(item["parent"]))
            seconds = float(str(item["self_seconds"]))
            calls = int(str(item["calls"]))
            if not math.isfinite(seconds) or seconds < 0 or calls < 0:
                raise ValueError("Profile durations and counts must be finite and nonnegative")
            if (index == 0 and parent != -1) or (index > 0 and not 0 <= parent < index):
                raise ValueError("Profile frames must follow their parents")
            if index:
                key = (remap[parent], str(item["label"]))
                child = children.get(key)
                if child is None:
                    child = len(frames)
                    frames.append(Frame(key[1], key[0]))
                    children[key] = child
                remap[index] = child
            destination = frames[remap[index]]
            destination.self_seconds += seconds
            destination.calls += calls
    return frames


def layout(frames: list[Frame]) -> list[tuple[int, float, float, int]]:
    """
    Allocate each frame its inclusive width while retaining self-time gaps.

    Args:
        frames (list[Frame]): Parent-before-child calling-context tree.

    Returns:
        list[tuple[int, float, float, int]]: Frame index, horizontal origin, width in seconds, and depth.
    """
    totals = [frame.self_seconds for frame in frames]
    children: dict[int, list[int]] = {}
    for index in range(len(frames) - 1, 0, -1):
        parent = frames[index].parent
        totals[parent] += totals[index]
        children.setdefault(parent, []).append(index)
    result = []
    pending = [(0, 0.0, 0)]
    while pending:
        index, left, depth = pending.pop()
        result.append((index, left, totals[index], depth))
        offset = left
        for child in sorted(children.get(index, []), key=lambda child: frames[child].label):
            pending.append((child, offset, depth + 1))
            offset += totals[child]
    return result


def plot(frames: list[Frame], output: Path, title: str, max_depth: int = 30, min_percent: float = 0.1) -> float:
    """
    Save matching PNG and SVG figures without changing the retained raw profiles.

    Args:
        frames (list[Frame]): Captured or merged calling contexts.
        output (Path): Figure basename.
        title (str): Process or worker-group description.
        max_depth (int): Maximum displayed stack depth.
        min_percent (float): Minimum displayed width as a percentage of captured time.

    Returns:
        float: Total captured seconds represented by the root frame.
    """
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt
    from matplotlib.patches import Rectangle
    from matplotlib.ticker import MaxNLocator

    positions = layout(frames)
    total = positions[0][2]
    visible = [row for row in positions if row[3] <= max_depth and row[2] > 0 and row[2] >= total * min_percent / 100]
    depth = max((row[3] for row in visible), default=0)
    figure, axis = plt.subplots(figsize=(16, max(3.5, 1.8 + (depth + 1) * 0.28)))
    try:
        for index, left, width, level in visible:
            frame = frames[index]
            shade = int.from_bytes(hashlib.sha256(frame.label.encode()).digest()[:2]) / 65535
            rectangle = Rectangle((left, level), width, 0.9, facecolor=plt.get_cmap("YlOrRd")(0.25 + shade * 0.5), linewidth=0.4)
            axis.add_patch(rectangle)
            if total and width / total >= 0.018:
                label = frame.label.rsplit("/", 1)[-1]
                text = axis.text(left + total * 0.001, level + 0.45, label, va="center", fontsize=7, clip_on=True)
                text.set_clip_path(rectangle)
        if not total:
            axis.text(0.5, 0.5, "No elapsed time captured", transform=axis.transAxes, ha="center")
        axis.set(
            xlim=(0, total or 1),
            ylim=(-0.15, depth + 1.15),
            xlabel="Captured wall seconds (summed for workers); grouped call stacks, not a timeline",
            ylabel="Python call depth",
        )
        axis.yaxis.set_major_locator(MaxNLocator(integer=True))
        figure.text(
            0.5,
            0.01,
            f"Instrumented execution; native work is charged to its Python caller. "
            f"Frames below {min_percent:g}% or deeper than {max_depth} are hidden; retained stacks are in JSON.",
            ha="center",
            fontsize=8,
        )
        figure.suptitle(title)
        figure.tight_layout(rect=(0, 0.05, 1, describe(figure, "flamegraph")))
        figure.savefig(output.with_suffix(".png"), dpi=160)
        figure.savefig(output.with_suffix(".svg"))
    finally:
        plt.close(figure)
    return total


def render_profiles(source: Path, output: Path, *, max_depth: int = 30, min_percent: float = 0.1) -> dict[str, object]:
    """
    Plot each process and a combined worker view, excluding coordinator waits from that sum.

    Args:
        source (Path): Directory of atomically completed capture files.
        output (Path): Directory receiving figures and their index.
        max_depth (int): Maximum displayed stack depth.
        min_percent (float): Smallest displayed frame as a percentage of root time.

    Returns:
        dict[str, object]: Process coverage, capture limits, and generated figures.
    """
    if max_depth < 1 or not math.isfinite(min_percent) or not 0 <= min_percent < 100:
        raise ValueError("Depth must be positive and minimum percentage must be in [0, 100)")
    groups: dict[str, list[dict[str, object]]] = {}
    workers = []
    files = sorted([*source.glob("coordinator-*.json"), *source.glob("worker-*.json")])
    truncated = 0
    incomplete = 0
    worker_identities = set()
    for path in files:
        document = mapping(json.loads(path.read_text()))
        role = document["role"]
        if role not in {"coordinator", "worker"}:
            raise ValueError(f"Unknown profile role in {path}")
        pid = int(str(document["pid"]))
        identity = str(document.get("process_id", path.stem))
        suffix = hashlib.sha256(identity.encode()).hexdigest()[:32]
        groups.setdefault(f"{role}-{pid}-{suffix}", []).append(document)
        truncated += int(str(document["truncated_events"]))
        incomplete += int(document.get("capture_complete") is not True)
        if role == "worker":
            workers.append(document)
            worker_identities.add(identity)
    if not groups:
        raise ValueError(f"No completed profile captures in {source}")
    if workers:
        groups["workers-combined"] = workers
    output.mkdir(parents=True, exist_ok=True)
    figures = []
    for name, profiles in groups.items():
        title = "All benchmark workers (coordinator excluded)" if name == "workers-combined" else "-".join(name.split("-")[:2])
        if any(profile.get("capture_complete") is not True for profile in profiles):
            title += " (includes partial capture)"
        if any(int(str(profile["truncated_events"])) for profile in profiles):
            title += " (stack capture limit reached)"
        seconds = plot(merge(profiles), output / name, title, max_depth, min_percent)
        figures.append({"name": name, "captured_seconds": seconds, "png": f"{name}.png", "svg": f"{name}.svg"})
    summary: dict[str, object] = {
        "source": str(source.resolve()),
        "captures": len(files),
        "worker_processes": len(worker_identities),
        "truncated_events": truncated,
        "incomplete_captures": incomplete,
        "scope": "Completed captures only; worker time is summed across overlapping processes, not elapsed runtime",
        "figures": figures,
    }
    (output / "index.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main(argv: list[str] | None = None, *, workspace: FixtureWorkspace | None = None) -> int:
    """
    Redraw saved call stacks without rerunning benchmark workloads.

    Args:
        argv (list[str] | None): Explicit command arguments or the process command line.
        workspace (FixtureWorkspace | None): Explicit owner of the invocation's reusable chart.

    Returns:
        int: Zero after saving figures and their index.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="directory containing coordinator and worker profile JSON")
    parser.add_argument("--output", type=Path, help="figure directory; defaults to SOURCE/flamegraphs")
    parser.add_argument("--max-depth", type=int, default=30)
    parser.add_argument("--min-percent", type=float, default=0.1)
    args = parser.parse_args(argv)
    result = render_profiles(
        args.source, args.output or args.source / "flamegraphs", max_depth=args.max_depth, min_percent=args.min_percent
    )
    print(json.dumps(result, indent=2))
    return 0

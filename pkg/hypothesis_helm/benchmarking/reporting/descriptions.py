"""
Give every figure a plain-language question immediately below its title.
"""

from textwrap import fill

from matplotlib.figure import Figure

INTRODUCTIONS = {
    "progressive": (
        "Permutation testing under a time ceiling",
        "How much work can each method finish before the time limit? Compare elapsed time and completed checks as more "
        "inputs are requested.",
    ),
    "strong-scaling": (
        "Strong scaling",
        "Does adding workers finish the same number of checks sooner? Compare runtime and speedup while total work stays fixed.",
    ),
    "weak-scaling": (
        "Weak scaling",
        "Can runtime stay steady as both workers and total work increase? Each worker receives the same number of inputs.",
    ),
    "replicas": (
        "Parallel worker throughput",
        "How does worker count affect completed checks and skipped renders? All worker counts receive the same total workload.",
    ),
    "output-distribution": (
        "Expected and observed output frequencies",
        "Does the chart produce the expected distribution, and which repeated outputs avoid another render? Compare the "
        "bars with the reference.",
    ),
    "bug-discovery": (
        "Defect discovery by interaction strength",
        "Does testing higher-order input interactions find more injected bugs? Compare distinct bugs found with the "
        "number of checks required.",
    ),
    "bug-order": (
        "Defect discovery by fault interaction order",
        "Which bugs require testing several fields together? Each curve groups bugs by the number of values needed to trigger them.",
    ),
    "sparsity-quality": (
        "Outcome coverage as the sample shrinks",
        "What coverage do we lose when testing fewer inputs? Compare distinct outputs reached and distribution error "
        "across shrinking samples.",
    ),
    "sparsity-distributions": (
        "Output distributions as the sample shrinks",
        "Which parts of the output distribution disappear from smaller samples? Each panel compares a received "
        "distribution with the full reference.",
    ),
    "sampling-recall": (
        "Sample size and defect discovery",
        "How many sampled inputs are needed to find the known defects? Compare distinct bugs found with the fraction of "
        "erroneous inputs tested.",
    ),
    "complexity-sweep": (
        "Measured sampling floors across chart breadth and depth",
        "Does a wider or deeper manifest need more test cases when the inputs and defect triggers stay the same? "
        "Compare paired chart shapes.",
    ),
    "calibration": (
        "Chart complexity and measured sampling floors",
        "How much sampling was needed for these generated charts? Compare chart complexity, retained checks and observed bug discovery.",
    ),
    "matching-matrix": (
        "Sampling policy comparison",
        "Do nearby calibration profiles save checks while retaining known-bug discovery? Compare cases kept and bugs "
        "found for each policy.",
    ),
    "profile-variation": (
        "Sampling variation between chart structures",
        "Do charts with similar sizes need similar numbers of checks? Vary nested conditions and compare results across defect placements.",
    ),
    "filtering-runtime": (
        "Filtering runtime as the input space grows",
        "Which filtering method finishes sooner as the problem grows? Each panel fixes the number of nested template conditions.",
    ),
    "filtering-planning": (
        "Filtering preparation cost",
        "How much time does each method spend deciding what to test? Compare planning time as input counts and nested conditions increase.",
    ),
    "filtering-completed": (
        "Checks completed by each filtering method",
        "How much testing does each method actually perform? Compare completed configurations at the same input-space "
        "size and condition depth.",
    ),
    "filtering-phases": (
        "Where filtering spends its time",
        "Is time spent analysing the chart, choosing inputs or running checks? Bar segments show phase costs; whiskers "
        "show variation in total time.",
    ),
    "clustering-observed": (
        "Measured failure clustering",
        "Are failing configurations surrounded by other failures? The vertical axis counts neighbours that also fail "
        "after changing one Boolean value.",
    ),
    "topology-stress": (
        "Filtering as structural difficulty decreases",
        "Which chart structures make filtering useful? Starting from the stress case, reduce one control per step and "
        "compare checks with bugs found.",
    ),
    "strategy-matrix": (
        "Filtering methods across chart structures",
        "Which method saves work for each chart structure, and what coverage does it lose? Compare output coverage, "
        "runtime, renders and distribution error.",
    ),
    "failure-expansion": (
        "Testing more inputs after a failure",
        "Does expanding around a discovered failure recover errors missed by trimming? Compare added checks and "
        "detected errors from matched starting samples.",
    ),
    "structure-depth": (
        "Sensitivity to topology trim depth",
        "How far can topology trimming reduce checks before errors are missed? Vary trim depth while holding the chart "
        "and other settings fixed.",
    ),
    "output-pca": (
        "Output space before and after filtering",
        "Which output regions disappear after filtering? Compare the same two-dimensional projection before and after "
        "selection; orange rings mark missed errors.",
    ),
    "nesting-matrix": (
        "Nested conditions and filtering coverage",
        "Does deeper template nesting hide errors from a filtering method? Compare erroneous inputs reached and checks "
        "performed, with and without expansion.",
    ),
    "nesting-pca": (
        "Output space across nesting depths",
        "How do nested conditions change the output regions that filtering reaches? Compare shared projection axes "
        "across depths and selection methods.",
    ),
    "topology": (
        "Helm chart dependency graph",
        "Which values connect to template decisions and rendered fields? Follow the directed links; they record "
        "potential references and observed output.",
    ),
    "graph-invariants": (
        "Dependency graph structure across charts",
        "How do real charts differ in dependency graph size and interconnectedness? Compare vertices, edges and "
        "independent cycles across charts.",
    ),
    "flamegraph": (
        "Benchmark call stacks",
        "Which Python call paths account for captured time? Wider blocks contain more time; stacked blocks show callers "
        "and their children, not execution order.",
    ),
}

for _axis, _factor in (("depth", "nested conditions"), ("redundancy", "unused fields"), ("clustering", "failure concentration")):
    for _metric, _question in (
        (
            "total-seconds",
            "How do error frequency and {factor} affect runtime? Each panel shows one method at the same parameter settings.",
        ),
        (
            "render-invocations",
            "How do error frequency and {factor} affect the number of Helm renders? Compare work performed across methods.",
        ),
        (
            "error-recall",
            "How do error frequency and {factor} affect error detection? Cells show erroneous inputs found as a percentage "
            "of all erroneous inputs.",
        ),
        ("additional-executed", "When do failures cause extra testing? Compare added checks as error frequency and {factor} change."),
    ):
        INTRODUCTIONS[f"{_axis}-{_metric}"] = (f"Error frequency and {_factor}", _question.format(factor=_factor))


def describe(figure: Figure, name: str, *, question: str | None = None) -> float:
    """
    Place a specific question beneath a figure title and reserve space above its panels.

    Args:
        figure (Figure): Matplotlib figure, optionally with an existing descriptive title.
        name (str): Registered plot purpose, shared by variants of the same study.
        question (str | None): Explicit description for a new or custom plot.

    Returns:
        float: Upper subplot boundary in figure coordinates for tight_layout.
    """
    if question is None:
        title, question = INTRODUCTIONS[name]
    else:
        title = name.replace("-", " ").capitalize()
    title = figure.get_suptitle() or title
    width, height = figure.get_figwidth(), figure.get_figheight()
    title = fill(title, width=max(35, int(width * 8)))
    question = fill(question, width=max(40, int(width * 13)))
    title_height = len(title.splitlines()) * 0.25
    title_artist = figure.suptitle(title, x=0.5, y=1 - 0.10 / height, va="top", fontsize=16)
    title_artist.set_in_layout(False)
    explanation = figure.text(
        0.5,
        1 - (0.16 + title_height) / height,
        question,
        ha="center",
        va="top",
        fontsize=10,
        color="#475569",
    )
    explanation.set_gid("plot-question")
    explanation.set_in_layout(False)
    return 1 - (0.36 + title_height + len(question.splitlines()) * 0.18) / height

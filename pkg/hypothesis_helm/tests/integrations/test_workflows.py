"""
Verify the unified CI graph, setup contexts and release artifact handoff.
"""

from graphlib import TopologicalSorter

from ruamel.yaml import YAML

from hypothesis_helm.schemas.contracts import mapping, sequence
from hypothesis_helm.tests import PROJECT_ROOT

ROOT = PROJECT_ROOT


def workflows() -> dict[str, dict[str, object]]:
    """
    Read the maintained workflow definitions without interpreting YAML booleans as keys.

    Returns:
        dict[str, dict[str, object]]: Workflow filenames mapped to their definitions.
    """
    return {path.name: mapping(YAML(typ="safe").load(path.read_text())) for path in (ROOT / ".github/workflows").glob("*.yml")}


def test_workflow_references_and_dependencies() -> None:
    """
    Keep one workflow entry point with valid local actions and acyclic job dependencies.

    Returns:
        None: All jobs appear in one run and their prerequisites resolve.
    """
    documents = workflows()
    assert set(documents) == {"ci.yml"}
    for filename, document in documents.items():
        jobs = mapping(document["jobs"])
        dependencies: dict[str, set[str]] = {}
        for job_id, raw in jobs.items():
            job = mapping(raw)
            assert job.get("name"), (filename, job_id)
            needs = job.get("needs", [])
            dependencies[job_id] = {needs} if isinstance(needs, str) else {str(item) for item in sequence(needs)}
            assert dependencies[job_id] <= jobs.keys(), (filename, job_id, dependencies[job_id])
            assert "uses" not in job  # Jobs stay visible in this graph, rather than separate workflow runs.
            for raw_step in sequence(job.get("steps", [])):
                action = str(mapping(raw_step).get("uses", ""))
                if action.startswith("./"):
                    assert (ROOT / action / "action.yml").is_file(), action
        assert set(TopologicalSorter(dependencies).static_order()) == jobs.keys()


def test_release_requires_all_verification_and_matching_artifacts() -> None:
    """
    Keep tag-only publishing behind every verification job and its exact built distributions.

    Returns:
        None: Release gates cannot be bypassed and the builder's artifact matches the publisher's download.
    """
    documents = workflows()
    release = documents["ci.yml"]
    triggers = mapping(release["on"])
    assert triggers["push"] == {"branches": ["main"], "tags": ["v[0-9]*"]}
    assert "pull_request" in triggers
    jobs = {name: mapping(job) for name, job in mapping(release["jobs"]).items()}
    publish = jobs["publish"]
    assert set(sequence(publish["needs"])) == {"go", "checks", "python-tests", "sharded-chart", "aggregate", "build", "smoke"}
    # No status override: GitHub's implicit success() still rejects failed or skipped prerequisites.
    assert publish["if"] == "${{ github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v') }}"
    assert publish["environment"] == "pypi"
    build = jobs["build"]
    build_steps = [mapping(step) for step in sequence(build["steps"])]
    publish_steps = [mapping(step) for step in sequence(publish["steps"])]
    upload = next(step for step in build_steps if str(step.get("uses", "")).startswith("actions/upload-artifact@"))
    download = next(step for step in publish_steps if str(step.get("uses", "")).startswith("actions/download-artifact@"))
    assert mapping(upload["with"])["name"] == mapping(download["with"])["name"]
    assert "package-version.outputs.version" in str(mapping(upload["with"])["name"])
    for steps in (build_steps, publish_steps):
        version = next(step for step in steps if step.get("id") == "package-version")
        assert "--tag" in str(version["run"])
        stamp = next(step for step in steps if step.get("run") == 'poetry version "$PACKAGE_VERSION"')
        assert mapping(stamp["env"])["PACKAGE_VERSION"] == "${{ steps.package-version.outputs.version }}"
        distribution = next(
            step for step in steps if str(step.get("run", "")).startswith("poetry build") or "poetry publish" in str(step.get("run", ""))
        )
        assert steps.index(version) < steps.index(stamp) < steps.index(distribution)
    catalog = next(step for step in build_steps if "hypothesis-helm-catalog --check" in str(step.get("run", "")))
    assert catalog["if"] == "startsWith(github.ref, 'refs/tags/')"


def test_refresh_is_optional_and_retains_matrix_barriers() -> None:
    """
    Reserve full measurements for manual requests without skipping release verification.

    Returns:
        None: Ordinary CI remains parallel; refresh waits for verification and every study before publication.
    """
    document = workflows()["ci.yml"]
    inputs = mapping(mapping(mapping(document["on"])["workflow_dispatch"])["inputs"])
    assert inputs["refresh"] == {
        "description": "Run the full benchmark and report refresh after verification",
        "type": "boolean",
        "default": False,
    }
    jobs = {name: mapping(job) for name, job in mapping(document["jobs"]).items()}
    for name in ("go", "checks", "python-tests", "sharded-chart", "build", "smoke"):
        assert "needs" not in jobs[name] and "if" not in jobs[name]
    prepare = jobs["refresh-prepare"]
    assert prepare["if"] == "${{ github.event_name == 'workflow_dispatch' && inputs.refresh }}"
    assert set(sequence(prepare["needs"])) == {"go", "checks", "python-tests", "sharded-chart", "aggregate", "build", "smoke"}
    study = jobs["refresh-study"]
    assert study["needs"] == "refresh-prepare"
    assert mapping(study["strategy"])["fail-fast"] is False
    assert "max-parallel" not in mapping(study["strategy"])
    assert set(sequence(jobs["refresh-finish"]["needs"])) == {"refresh-prepare", "refresh-study"}
    # Optional jobs cannot block the tag-only publisher.
    assert not set(sequence(jobs["publish"]["needs"])) & {"refresh-prepare", "refresh-study", "refresh-finish"}
    assert mapping(document["concurrency"])["cancel-in-progress"] == "${{ github.event_name == 'pull_request' }}"


def test_setup_receives_workflow_resolved_cache_policy() -> None:
    """
    Resolve repository variables before entering the composite action's restricted context.

    Returns:
        None: Every setup call honors manual and repository cache switches without invalid vars expressions.
    """
    document = workflows()["ci.yml"]
    assert mapping(document["env"])["HH_BINARY_CACHE"] == (
        "${{ vars.HH_BINARY_CACHE != 'false' && (github.event_name != 'workflow_dispatch' || inputs.binary-cache) }}"
    )
    setup_text = (ROOT / ".github/actions/setup-project/action.yml").read_text()
    assert "vars." not in setup_text
    assert "inputs.binary-cache == 'true'" in setup_text
    for raw_job in mapping(document["jobs"]).values():
        job = mapping(raw_job)
        assert "ubuntu-latest-8-cores" not in str(job["runs-on"])
        for raw_step in sequence(job["steps"]):
            step = mapping(raw_step)
            if step.get("uses") in {"./.github/actions/setup-project", "./"}:
                assert mapping(step["with"])["binary-cache"] == "${{ env.HH_BINARY_CACHE }}"


def test_go_jobs_test_every_module_without_python_setup() -> None:
    """
    Start native tests independently of Python dependency resolution and use each module's Go version.

    Returns:
        None: Every Go module has an isolated test job with its own dependency cache.
    """
    job = mapping(mapping(workflows()["ci.yml"]["jobs"])["go"])
    matrix = mapping(mapping(job["strategy"])["matrix"])
    modules = {str(mapping(item)["module"]) for item in sequence(matrix["include"])}
    assert modules == {str(path.parent.relative_to(ROOT)) for path in ROOT.glob("pkg/**/go.mod")}
    steps = [mapping(step) for step in sequence(job["steps"])]
    assert {str(step["uses"]).split("@")[0] for step in steps if "uses" in step} == {"actions/checkout", "actions/setup-go"}
    setup = next(step for step in steps if str(step.get("uses", "")).startswith("actions/setup-go@"))
    assert mapping(setup["with"])["go-version-file"] == "${{ matrix.module }}/go.mod"
    assert mapping(setup["with"])["cache-dependency-path"] == "${{ matrix.module }}/go.sum"
    test = next(step for step in steps if "run" in step)
    assert mapping(test["env"])["GO_MODULE"] == "${{ matrix.module }}"
    assert test["run"] == 'go -C "$GO_MODULE" test -v -timeout 10m ./...'


def test_python_setup_reuses_locked_environment_without_resolving() -> None:
    """
    Cache the exact Python environment while always installing the current checkout's editable packages.

    Returns:
        None: Setup bounds installation, shows progress and invalidates caches when either package changes.
    """
    action = mapping(YAML(typ="safe").load((ROOT / ".github/actions/setup-project/action.yml").read_text()))
    steps = [mapping(step) for step in sequence(mapping(action["runs"])["steps"])]
    restore = next(step for step in steps if step.get("id") == "python-cache")
    cache = mapping(restore["with"])
    for coordinate in ("runner.os", "runner.arch", "steps.python.outputs.python-version", "poetry-2.1.3"):
        assert coordinate in str(cache["key"])
    for path in ("poetry.lock", "pyproject.toml", "pkg/hypothesis_helm_benchmarking/pyproject.toml"):
        assert f"'{path}'" in str(cache["key"])
    install = next(step for step in steps if "poetry install" in str(step.get("run", "")))
    assert "if" not in install  # A cache hit must still refresh the editable project installs.
    environment = mapping(install["env"])
    assert environment["POETRY_KEYRING_ENABLED"] == environment["POETRY_INSTALLER_RE_RESOLVE"] == "false"
    command = str(install["run"])
    assert "poetry check --lock" in command
    assert "timeout --signal=TERM --kill-after=30s 10m poetry install" in command
    assert "--extras benchmarking --with dev --no-interaction --no-ansi -v" in command
    save = next(step for step in steps if "python-cache.outputs.cache-hit" in str(step.get("if", "")))
    assert mapping(save["with"])["path"] == cache["path"]
    assert mapping(save["with"])["key"] == "${{ steps.python-cache.outputs.cache-primary-key }}"
    assert steps.index(restore) < steps.index(install) < steps.index(save)
    setup_go = next(step for step in steps if str(step.get("uses", "")).startswith("actions/setup-go@"))
    assert mapping(setup_go["with"])["go-version-file"] == "pkg/hypothesis_helm/compiler/assets/renderer/go.mod"


def test_python_matrix_partitions_tests_and_artifacts() -> None:
    """
    Keep lint independent while every Python shard uses its runner's available CPUs.

    Returns:
        None: All shards run, retain distinct reports and participate in the release gate.
    """
    jobs = mapping(workflows()["ci.yml"]["jobs"])
    job = mapping(jobs["python-tests"])
    strategy = mapping(job["strategy"])
    assert strategy["fail-fast"] is False
    assert mapping(strategy["matrix"])["shard"] == [1, 2, 3, 4]
    steps = [mapping(step) for step in sequence(job["steps"])]
    test = next(step for step in steps if "--suite-shard" in str(step.get("run", "")))
    assert mapping(test["env"])["SUITE_SHARD"] == "${{ matrix.shard }}/4"
    assert "-p hypothesis_helm.tests.sharding" in str(test["run"])
    assert "-n auto --dist worksteal" in str(test["run"])
    upload = next(step for step in steps if str(step.get("uses", "")).startswith("actions/upload-artifact@"))
    assert "matrix.shard" in str(mapping(upload["with"])["name"])
    assert "always()" in str(upload["if"])
    assert all("pre-commit" not in str(step.get("run", "")) for step in steps)


def test_chart_workflow_restores_shard_caches_and_comparison_history() -> None:
    """
    Keep incremental CI, fresh security validation and tag release coverage wired together.

    Returns:
        None: Independent caches persist complete evidence and tags force new property tests.
    """
    job = mapping(mapping(workflows()["ci.yml"]["jobs"])["sharded-chart"])
    steps = [mapping(step) for step in sequence(job["steps"])]
    checkout = next(step for step in steps if str(step.get("uses", "")).startswith("actions/checkout@"))
    assert mapping(checkout["with"])["fetch-depth"] == 0
    restore = next(step for step in steps if step.get("id") == "outcomes")
    settings = mapping(restore["with"])
    for coordinate in ("matrix.kubernetes", "matrix.shard", "runner.os", "runner.arch"):
        assert coordinate in str(settings["key"])
        assert coordinate in str(settings["restore-keys"])
    test = next(step for step in steps if step.get("id") == "hypothesis")
    options = mapping(test["with"])
    assert options["incremental"] == options["kubesec"] == "true"
    assert options["cache-dir"] == settings["path"]
    assert "refs/tags/" in str(options["rerun"]) and "'all'" in str(options["rerun"])
    save = next(step for step in steps if str(step.get("uses", "")).startswith("actions/cache/save@"))
    assert "always()" in str(save["if"])
    assert mapping(save["with"])["path"] == settings["path"]

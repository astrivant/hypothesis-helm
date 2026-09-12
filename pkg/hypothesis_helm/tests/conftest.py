"""
Keep embedded CLI tests independent of their parent CI runner's shard identity.
"""

import pytest


@pytest.fixture(autouse=True)
def isolated_ci_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Clear external node coordinates; CI detection tests explicitly supply their own.

    Args:
        monkeypatch (pytest.MonkeyPatch): Fixture restoring caller environment variables.

    Returns:
        None: Tests cannot accidentally inherit the surrounding pipeline's partition.
    """
    for key in (
        "CIRCLE_NODE_INDEX",
        "CIRCLE_NODE_TOTAL",
        "CI_NODE_INDEX",
        "CI_NODE_TOTAL",
        "HYPOTHESIS_HELM_JOB_INDEX",
        "HYPOTHESIS_HELM_JOB_TOTAL",
        "HH_CHART",
        "HH_SHARD",
        "HH_ARTIFACT_DIR",
        "HH_MATCH",
        "HH_KUBECONFORM",
        "HH_KUBESEC",
        "HH_KUBESEC_JOBS",
        "HH_KUBESEC_BINARY",
        "HH_SCHEMA_VERSION",
        "HH_SCHEMA_CACHE_DIR",
        "HH_SCHEMA_OFFLINE",
        "HH_KUBECONFORM_BINARY",
        "HYPOTHESIS_HELM_CONFORMITY",
        "HH_CACHE",
        "HH_CACHE_DIR",
        "HH_RERUN",
        "CI",
        "GITHUB_ACTIONS",
        "GITLAB_CI",
        "CIRCLECI",
    ):
        monkeypatch.delenv(key, raising=False)

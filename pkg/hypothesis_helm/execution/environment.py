"""
Interpret process environment markers consistently across execution and reporting.
"""

import os
from collections.abc import Mapping

CI_PROVIDERS = ("GITHUB_ACTIONS", "GITLAB_CI", "CIRCLECI", "TF_BUILD", "JENKINS_URL", "BUILD_BUILDID", "BUILDKITE")
DISABLED = frozenset({"", "0", "false", "no", "off"})


def in_ci(environment: Mapping[str, str] | None = None, *, honor_override: bool = True) -> bool:
    """
    Detect CI providers, optionally allowing an explicit CI value to override them.

    Cache defaults honor CI=false so users can request local retry behavior.
    Progress displays ignore that override to keep bars out of CI logs.

    Args:
        environment (Mapping[str, str] | None): Environment to inspect; defaults to the current process.
        honor_override (bool): Let an explicit CI value take precedence over provider markers.

    Returns:
        bool: Whether CI is enabled under the requested policy.
    """
    environment = os.environ if environment is None else environment
    if honor_override and "CI" in environment:
        return environment["CI"].strip().lower() not in DISABLED
    return any(environment.get(name, "").strip().lower() not in DISABLED for name in ("CI", *CI_PROVIDERS))

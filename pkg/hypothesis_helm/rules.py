"""
Stable built-in check identifiers and an inherited, explicit ignore policy.
"""

import json
import logging
import os
from pathlib import Path

from hypothesis_helm.charts import yamlio
from hypothesis_helm.findings.catalog import CATALOG
from hypothesis_helm.findings.generator import Finding, FindingGenerator

ENVIRONMENT = "HYPOTHESIS_HELM_IGNORED_RULES"
LOGGER = logging.getLogger(__name__)
RULES = {code: rule.title for code, rule in CATALOG.items()}
AUDIT_RULES = {
    "undocumented": "HH2001",
    "untyped": "HH2002",
    "missing-description": "HH2003",
    "no-default": "HH2004",
}


def load_ignored(config: Path | None, codes: list[str]) -> list[str]:
    """
    Combine an explicit or working-directory YAML policy with command-line codes.

    Args:
        config (Path | None): Explicit file, or discover .hypothesis-helm.yaml in the working directory.
        codes (list[str]): Additional stable identifiers, checked for spelling mistakes.

    Returns:
        list[str]: Sorted unique identifiers; invalid policies raise ValueError.
    """
    path = config or Path(".hypothesis-helm.yaml")
    configured: object = []
    if config is not None or path.is_file():
        document = yamlio.load(path.read_text())
        if not isinstance(document, dict) or set(document) - {"ignored"}:
            raise ValueError(f"{path}: expected a mapping containing only 'ignored'")
        configured = document.get("ignored", [])
        if configured is None:
            configured = []
    if not isinstance(configured, list) or any(not isinstance(code, str) for code in configured):
        raise ValueError(f"{path}: 'ignored' must be a list of rule codes")
    result = sorted(set([*configured, *codes]))
    unknown = [code for code in result if code not in RULES]
    if unknown:
        raise ValueError(f"Unknown rule codes: {', '.join(unknown)}; run 'helm hypothesis rules'")
    return result


def ignored_codes() -> list[str]:
    """
    Read the CLI-resolved policy inherited unchanged by subprocess workers.

    Returns:
        list[str]: Active ignored rule identifiers.
    """
    return load_codes(os.environ.get(ENVIRONMENT, "[]"))


def load_codes(value: str) -> list[str]:
    """
    Validate serialized policy before it can disable a check.

    Args:
        value (str): JSON-encoded identifiers supplied by the coordinator.

    Returns:
        list[str]: Valid identifiers, or a ValueError for malformed policy.
    """
    codes = json.loads(value)
    if not isinstance(codes, list) or any(not isinstance(code, str) or code not in RULES for code in codes):
        raise ValueError("Invalid inherited ignored-rule policy")
    return sorted(set(codes))


def ignored(code: str) -> bool:
    """
    Check whether an explicitly identified built-in rule is disabled.

    Args:
        code (str): Stable built-in rule identifier.

    Returns:
        bool: Whether the current policy disables this check.
    """
    return code in ignored_codes()


def record_ignored(code: str, message: str) -> None:
    """
    Expose skipped checks in diagnostics without emitting manifest output.

    Args:
        code (str): Disabled rule identifier.
        message (str): Reason the check could not pass.

    Returns:
        None: Emit an informational diagnostic.
    """
    LOGGER.info("[%s] Ignored: %s", code, message)


class RenderFailure(AssertionError):
    """
    Attach a stable check identifier to a reproducible render failure.

    Attributes:
        code (str): Stable identifier, independent of report grouping order.
        finding (Finding): Structured observation carried by this exception.
        resources (list[object] | None): Parsed output available before validation failed.
    """

    code: str
    finding: Finding
    resources: list[object] | None = None

    def __init__(self, message: str, code: str = "HH1001") -> None:
        """
        Retain the diagnostic and its explicit rule identity.

        Args:
            message (str): Original renderer or validator diagnostic.
            code (str): Explicit detected condition, or an unclassified template failure.
        """
        self.finding = FindingGenerator.create(code, message)
        self.code = self.finding.rule.code
        super().__init__(f"[{self.code}] {message}")


def check(condition: bool, code: str, message: str) -> None:
    """
    Enforce one independent check without skipping subsequent enabled checks.

    Args:
        condition (bool): Whether the checked requirement holds.
        code (str): Stable identifier.
        message (str): Failure diagnostic.

    Returns:
        None: Continue on success or explicit opt-out; otherwise raise RenderFailure.
    """
    if condition:
        return
    if ignored(code):
        record_ignored(code, message)
        return
    raise RenderFailure(message, code)

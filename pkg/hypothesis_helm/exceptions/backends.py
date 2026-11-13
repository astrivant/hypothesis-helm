"""
Describe bounded plan failures separately from chart defects.
"""

from __future__ import annotations

__all__ = ("BackendError", "BackendUnavailable", "InvalidPlan")


class BackendError(RuntimeError):
    """
    A compute attempt failed without validating any chart output.
    """


class BackendUnavailable(BackendError):
    """
    The requested optional runtime or device is unavailable.
    """


class InvalidPlan(ValueError):
    """
    A plan violates the versioned, bounded data contract.
    """

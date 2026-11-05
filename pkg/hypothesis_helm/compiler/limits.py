"""
Resolve bounded compiler analysis independently of Helm's rendering limits.
"""

import json
from functools import lru_cache
from pathlib import Path

__all__ = ("DEFAULT_LIMITS", "LIMITS", "active_limits", "call_depth", "compiler_limits", "policy_limits")


# Resource budgets only. Language semantics, numeric precision and proof requirements
# are not configurable: changing those would change what the analysis can establish.
LIMITS: dict[str, tuple[int, str]] = {
    "max_call_depth": (16, "Nested helper/tpl calls."),
    "max_files": (10000, "Members inspected per chart archive, including directories."),
    "max_context_bytes": (64 * 1024 * 1024, "Packed/unpacked bytes per archive; retained native certificate records per prepared chart."),
    "max_template_bytes": (1024 * 1024, "UTF-8 bytes in each dynamically analyzed tpl source."),
    "max_steps": (10000, "Statements/iterations per root analysis; effect calls per render and retained crypto records per chart."),
    "max_discovery_nodes": (10000, "Actions per discovery traversal or nodes per helper projection."),
    "max_tpl_depth": (32, "Nested tpl expansions during value-path discovery."),
    "max_range_items": (4096, "Elements in a collection evaluated by a range."),
    "max_dependency_depth": (16, "Dependency nesting inspected from the root chart."),
    "max_dependencies": (512, "Dependency instances inspected per chart."),
    "max_version_chars": (4096, "Combined characters in a semantic-version constraint and version."),
    "max_string_chars": (16384, "Characters in a transformation operand or replacement result."),
    "max_regex_pattern_chars": (256, "Characters in an analyzed Go regex pattern."),
    "max_regex_subject_chars": (4096, "Characters in an analyzed Go regex subject."),
    "max_symbolic_variants": (64, "Alternatives at one destination-projection branch join."),
    "max_indent_width": (128, "Spaces in a projected indent/nindent operation."),
    "max_fragment_depth": (4, "Nested input containers checked for literal serialized YAML fragment constraints."),
    "max_proof_bytes": (16 * 1024 * 1024, "Chart bytes retained for an exact-pruning proof snapshot."),
    "max_output_nodes": (100000, "Manifest nodes inspected per complexity measurement."),
    "max_complexity_cases": (4096, "Template assignments and witnesses in a complexity search."),
    "max_complexity_seconds": (5, "Whole seconds allowed for a complexity search."),
    "max_lua_memory_bytes": (64 * 1024 * 1024, "Lua allocations per complexity analysis; exhaustion uses Python bounds."),
    "max_sampling_domain_values": (4096, "Values per factor when computing a sampling profile."),
    "max_fallbacks": (128, "Distinct incomplete-analysis diagnostics retained per chart."),
    "max_preimage_steps": (128, "Search steps when proposing inputs for a transformed allowlist."),
    "max_preimage_choices": (16, "Targets and proposals per transformed-allowlist search step."),
    "max_rejections": (64, "Distinct rejection contracts used to guide generation."),
    "max_repair_attempts": (48, "Candidate changes tried for a rejected configuration."),
    "max_repair_branch_attempts": (16, "Candidate changes tried at one repair search node."),
    "max_repair_depth": (3, "Successive changes considered along a repair search branch."),
    "max_repair_length": (16, "Largest proposed list length during rejection repair."),
}
DEFAULT_LIMITS = {name: default for name, (default, _) in LIMITS.items()}


def compiler_limits(raw: object) -> dict[str, int]:
    """
    Validate configured compiler settings and fill in default budgets.

    Args:
        raw (object): Partial compiler configuration mapping.

    Returns:
        dict[str, int]: Complete compiler limits suitable for worker serialization.
    """
    if not isinstance(raw, dict):
        raise ValueError("compiler must be a mapping of analysis budgets")
    unknown = set(raw) - DEFAULT_LIMITS.keys()
    if unknown:
        raise ValueError("Unknown compiler setting(s): " + ", ".join(sorted(str(key) for key in unknown)))
    resolved = dict(DEFAULT_LIMITS)
    for name, value in raw.items():
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"compiler.{name} must be a positive integer")
        resolved[name] = value
    return resolved


@lru_cache(maxsize=128)
def policy_limits(serialized: str, name: str | None = None, source: str | None = None) -> tuple[tuple[str, int], ...]:
    """
    Cache validated limits by the complete inherited policy, never by chart or process alone.

    Args:
        serialized (str): Coordinator policy serialized for worker inheritance.
        name (str | None): Root chart name, or global defaults when omitted.
        source (str | None): Original chart source for matrix selectors.

    Returns:
        tuple[tuple[str, int], ...]: Immutable entries safe to reuse across analysis calls.
    """
    from hypothesis_helm.schemas.configuration.selectors import select_rules
    from hypothesis_helm.schemas.contracts import mapping, sequence

    policy = mapping(json.loads(serialized))
    resolved = compiler_limits(policy.get("compiler", {}))
    overrides: dict[str, int] = {}
    if name is not None and source is not None:
        for rule in select_rules(sequence(policy.get("input_constraints", [])), name, source):
            if "compiler" not in rule:
                continue
            if rule.get("path") != "$":
                raise ValueError("Chart compiler overrides require path: $; compiler budgets cannot vary by values branch")
            configured = mapping(rule["compiler"])
            validated = compiler_limits(configured)
            for key in configured:
                value = validated[key]
                if key in overrides and overrides[key] != value:
                    raise ValueError(f"Conflicting compiler.{key} overrides for chart {name!r} from {source!r}")
                overrides[key] = value
    return tuple({**resolved, **overrides}.items())


def active_limits(chart: Path | None = None) -> dict[str, int]:
    """
    Snapshot the coordinator's compiler budgets when building an analysis.

    Args:
        chart (Path | None): Root chart for scoped overrides; omit for global defaults.

    Returns:
        dict[str, int]: Detached validated settings, also available in spawned workers.
    """
    from hypothesis_helm.schemas.configuration.policy import inherited_policy
    from hypothesis_helm.schemas.configuration.selectors import chart_identity, source_identity

    # Resolve both policy transports before caching; a file pointer must not mean default budgets.
    serialized = json.dumps(inherited_policy(), sort_keys=True)
    return dict(
        policy_limits(serialized, chart_identity(chart), source_identity(chart)) if chart is not None else policy_limits(serialized)
    )


def call_depth() -> int:
    """
    Read the coordinator's nested-call budget when building a chart analysis.

    Returns:
        int: Maximum nested helper calls, shared by rejection and destination analysis.
    """
    return active_limits()["max_call_depth"]

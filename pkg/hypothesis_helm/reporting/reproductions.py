"""
Present recorded failing inputs without inferring missing values or independent causes.
"""

import json
import re
from collections.abc import Iterator

from deepdiff import DeepDiff


def changed_values(values: dict[str, object], defaults: dict[str, object]) -> dict[str, object]:
    """
    Record supplied overrides that differ from chart defaults, including explicit nulls.

    Args:
        values (dict[str, object]): Recorded Helm overrides.
        defaults (dict[str, object]): Defaults loaded for this exact chart run.

    Returns:
        dict[str, object]: Changed paths and their values; omitted keys still inherit defaults.
    """
    if not values:
        return {}
    changes = {}
    for path, value in leaves(values, [], arrays=False):
        current: object = defaults
        for key in path:
            if isinstance(current, dict) and key in current:
                current = current[key]
            elif isinstance(current, list) and isinstance(key, int) and 0 <= key < len(current):
                current = current[key]
            else:
                changes[value_path(path)] = value
                break
        else:
            if isinstance(value, dict) and not value and isinstance(current, dict):
                continue
            if value is None or DeepDiff(json.loads(json.dumps(current)), json.loads(json.dumps(value)), zip_ordered_iterables=True):
                changes[value_path(path)] = value
    return changes


def value_path(path: list[str | int]) -> str:
    """
    Format exact keys and array indices without interpreting literal wildcard keys.

    Args:
        path (list[str | int]): Concrete path in a recorded values document.

    Returns:
        str: Dollar-rooted path with unusual keys escaped in bracket notation.
    """
    result = "$"
    for key in path:
        result += f"[{key}]" if isinstance(key, int) else f".{key}" if key.isidentifier() else f"[{json.dumps(key, ensure_ascii=True)}]"
    return result


def leaves(value: object, path: list[str | int], *, arrays: bool = True) -> Iterator[tuple[list[str | int], object]]:
    """
    Enumerate supplied leaf values, retaining empty mappings, lists, and nulls.

    Args:
        value (object): Recorded input subtree.
        path (list[str | int]): Prefix identifying that subtree.
        arrays (bool): Expand array indices; disable to preserve whole-list replacement semantics.

    Yields:
        tuple[list[str | int], object]: Exact path and recorded value.
    """
    if isinstance(value, dict) and value:
        for key, child in value.items():
            yield from leaves(child, [*path, str(key)], arrays=arrays)
    elif arrays and isinstance(value, list) and value:
        for index, child in enumerate(value):
            yield from leaves(child, [*path, index], arrays=arrays)
    else:
        yield path, value


def failing_input(source: dict[str, object]) -> dict[str, object]:
    """
    Present selected paths first and retain the complete recorded configuration.

    Args:
        source (dict[str, object]): Phase or chart record containing reproducing values.

    Returns:
        dict[str, object]: Explicit evidence availability, scope, path values, and absent paths.
    """
    values = source.get("values")
    if not isinstance(values, dict):
        return {"recorded": False}
    selected: list[list[str | int]] = []
    candidates = source.get("paths", [source["path"]] if "path" in source else [])
    if isinstance(candidates, list):
        for candidate in candidates:
            if isinstance(candidate, list) and all(type(key) in (str, int) for key in candidate):
                selected.append(candidate)
    inputs = {}
    absent = []
    if selected:
        for path in selected:
            current: object = values
            for key in path:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                elif isinstance(current, list) and isinstance(key, int) and 0 <= key < len(current):
                    current = current[key]
                else:
                    absent.append(value_path(path))
                    break
            else:
                inputs[value_path(path)] = current
    for path, value in leaves(values, []):
        if not any(path[: len(prefix)] == prefix for prefix in selected):
            inputs[value_path(path)] = value
    return {
        "recorded": True,
        "scope": "recorded configuration",
        "selected_paths": [value_path(path) for path in selected],
        "paths": inputs,
        "absent_paths": absent,
        "changes": source.get("input_changes"),
        "comparisons": source.get("comparisons"),
    }


def input_summary(evidence: dict[str, object]) -> list[str]:
    """
    Bound human-facing input previews while retaining full evidence in JSON and artifacts.

    Args:
        evidence (dict[str, object]): Structured failing-input evidence.

    Returns:
        list[str]: At most six path-value previews and an explicit omission notice.
    """
    if not evidence.get("recorded"):
        return ["No triggering values were recorded for this diagnostic."]
    paths = evidence.get("paths", {})
    assert isinstance(paths, dict)
    selected = evidence.get("selected_paths", [])
    changes = evidence.get("changes")
    if isinstance(changes, dict):
        paths, label = changes, "Changed overrides (used together)"
    elif isinstance(selected, list) and selected:
        paths = {path: paths[path] for path in selected if path in paths}
        label = "Selected fields (full context in artifacts)"
    else:
        label = "Recorded input (used together)"
    lines = [label + ":"]
    comparisons = evidence.get("comparisons")
    values_record = comparisons.get("values", {}) if isinstance(comparisons, dict) else {}
    value_changes = values_record.get("changes", []) if isinstance(values_record, dict) else []
    previous = {change["path"]: change["before"] for change in value_changes if change.get("old_present")} if value_changes else {}
    for path, value in list(paths.items())[:6]:
        encoded = json.dumps(value, ensure_ascii=True)
        truncated = len(encoded) > 120
        preview = encoded[:120] + "... [value shortened]" if truncated else encoded
        content = f"{path} = {preview}"
        if path in previous:
            old = json.dumps(previous[path], ensure_ascii=True)
            content += " (was " + (old[:120] + "... [value shortened]" if len(old) > 120 else old) + ")"
        fence = "`" * (max((len(part) for part in re.findall(r"`+", content)), default=0) + 1)
        lines.append(f"- {fence}{content}{fence}")
    if len(paths) > 6:
        lines.append(f"- {len(paths) - 6} more paths; see full input.")
    if not paths:
        lines.append("- No changed overrides." if isinstance(changes, dict) else "- No supplied value at the selected paths.")
    absent = evidence.get("absent_paths", [])
    if isinstance(absent, list) and absent:
        lines.append("Absent from overrides: " + ", ".join(str(path) for path in absent[:6]) + ". Defaults may still apply.")
    manifests = comparisons.get("manifests", {}) if isinstance(comparisons, dict) else {}
    if isinstance(manifests, dict) and manifests.get("changes"):
        changes = manifests["changes"]
        assert isinstance(changes, list)
        lines.extend(["", "Manifest changes from rendered defaults (document and list order preserved):"])
        for change in changes[:6]:
            parts = []
            for key in ("before", "after"):
                encoded = json.dumps(change[key], ensure_ascii=True) if key in change else "<absent>"
                parts.append(encoded[:120] + "... [value shortened]" if len(encoded) > 120 else encoded)
            content = str(change["path"]) + ": " + " -> ".join(parts)
            fence = "`" * (max((len(part) for part in re.findall(r"`+", content)), default=0) + 1)
            lines.append(f"- {fence}{content}{fence}")
        if len(changes) > 6:
            lines.append(f"- {len(changes) - 6} more changes; see JSON artifacts.")
    return lines

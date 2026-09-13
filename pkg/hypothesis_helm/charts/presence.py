"""
Check whether configurable paths are explicitly represented in source values.
"""


def has_path(value: object, path: tuple[str | int, ...]) -> bool:
    """
    Require named fields in every existing collection entry, without applying defaults.

    Args:
        value (object): Original parsed values document or nested value.
        path (tuple[str | int, ...]): Schema or template path, including item wildcards.

    Returns:
        bool: The path is explicit, including null-valued leaves. Empty collections
            satisfy item-value wildcards but cannot demonstrate nested named fields.
    """
    if not path:
        return True
    segment, *remaining = path
    tail = tuple(remaining)
    if segment == "*":
        if isinstance(value, dict):
            entries = list(value.values())
        elif isinstance(value, list):
            entries = value
        else:
            return False
        return (bool(entries) or not tail) and all(has_path(entry, tail) for entry in entries)
    if isinstance(segment, int):
        return isinstance(value, list) and 0 <= segment < len(value) and has_path(value[segment], tail)
    return isinstance(value, dict) and segment in value and has_path(value[segment], tail)

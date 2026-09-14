"""
Update historical benchmark method labels for display without rewriting measurement files.
"""


def current_labels(value: object) -> object:
    """
    Copy JSON containers with the current preset label while preserving other values.

    Args:
        value (object): Loaded benchmark metadata, rows or nested strategy mappings.

    Returns:
        object: Display copy using the current name; the original ledger remains unchanged.
    """
    if isinstance(value, str):
        return "filter-adaptive" if value == "filter-aggressive" else value
    if isinstance(value, dict):
        return {"filter-adaptive" if key == "filter-aggressive" else key: current_labels(item) for key, item in value.items()}
    if isinstance(value, list):
        return [current_labels(item) for item in value]
    return value

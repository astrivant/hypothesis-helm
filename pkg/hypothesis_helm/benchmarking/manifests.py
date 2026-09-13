"""
Construct shared benchmark oracle resource envelopes without generator dependencies.
"""


def configmap(name: str, data: dict[str, object]) -> dict[str, object]:
    """
    Construct an oracle ConfigMap without inspecting the template.

    Args:
        name (str): Fixed resource name.
        data (dict[str, object]): Expected scalar fields.

    Returns:
        dict[str, object]: Complete expected resource.
    """
    return {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": name}, "data": data}

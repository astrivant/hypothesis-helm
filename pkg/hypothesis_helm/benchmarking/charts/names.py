"""
Give generated input fields stable names describing their downstream roles.
"""

import json
from pathlib import Path

from hypothesis_helm.charts import yamlio
from hypothesis_helm.schemas.contracts import mapping


def name_inputs(chart: Path, spec: dict[str, object], names: list[str] | None = None) -> dict[str, object]:
    """
    Rename fields consistently in templates, values, schema, and oracle metadata.

    Args:
        chart (Path): Completed generated chart before applying readable input names.
        spec (dict[str, object]): Independent distribution and structural metadata.
        names (list[str] | None): Explicit fixed names for the combined stress fixture.

    Returns:
        dict[str, object]: Metadata whose input names and structural selectors match Helm.
    """
    count, active = int(str(spec["input_complexity"])), int(str(spec["active_inputs"]))
    if names is None:
        names = [
            f"distributionBit{index + 1:02d}"
            if index < active
            else f"sharedTopologySignal{index - active + 1:02d}"
            if spec.get("structure") or spec.get("topology")
            else f"equivalentChoice{index - active + 1:03d}"
            for index in range(count)
        ]
    if len(names) != count or len(set(names)) != count:
        raise ValueError("input names must match the number of distinct input fields")
    previous = spec.get("input_names", [f"input{index:03d}" for index in range(count)])
    if not isinstance(previous, list) or len(previous) != count:
        raise ValueError("existing input names must match the field count")
    replacements = {str(old): name for old, name in zip(previous, names, strict=True)}

    def renamed(document: object) -> object:
        """
        Replace exact field selectors while retaining all data types.

        Args:
            document (object): JSON-compatible schema, values, or oracle document.

        Returns:
            object: Equivalent document with readable selectors.
        """
        encoded = json.dumps(document)
        for old, new in replacements.items():
            encoded = encoded.replace(json.dumps(old), json.dumps(new))
        return json.loads(encoded)

    values_file, schema_file = chart / "values.yaml", chart / "values.schema.json"
    values_file.write_text(yamlio.dump(renamed(yamlio.load(values_file.read_text()))))
    schema_file.write_text(json.dumps(renamed(json.loads(schema_file.read_text())), indent=2) + "\n")
    for template in (chart / "templates").glob("*.yaml"):
        text = template.read_text()
        for old in sorted(replacements, key=len, reverse=True):
            text = text.replace(".Values." + old, ".Values." + replacements[old])
        template.write_text(text)
    result = mapping(renamed(spec))
    result["input_names"] = names
    return result

"""
Compare manifest float resolution with native Helm without changing values-file readers.
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path
from textwrap import dedent

import pytest
from hypothesis_helm.charts.values import parsers, yamlio
from hypothesis_helm.execution.state.render_hashes import render_digest
from hypothesis_helm.schemas.contracts import mapping
from ruamel.yaml import YAML

RUAMEL_BACKENDS = ("ruamel", "ruamel-safe")


@pytest.mark.parametrize("backend", RUAMEL_BACKENDS)
@pytest.mark.parametrize("literal", ["1E400", "-1e400", "+1.0e+400", "1_0e400", "9" * 320 + ".0"])
def test_implicit_overflow_retains_string(backend: str, literal: str) -> None:
    """
    Preserve overflowing numeric-looking strings instead of introducing non-JSON infinity.

    Args:
        backend (str): Manifest reader under test.
        literal (str): Plain scalar outside the finite binary64 domain.

    Returns:
        None: The scalar keeps its original text and remains canonically hashable.
    """
    documents = parsers.load_all(f"value: {literal}\n", backend=backend)
    assert documents == [{"value": literal}]
    assert render_digest(documents) == render_digest([{"value": literal}])


@pytest.mark.parametrize("backend", RUAMEL_BACKENDS)
@pytest.mark.parametrize("literal", ["1e-05", "1e-06", "-2E+10", "1.7976931348623157e308", "1e-400", "0.25"])
def test_finite_scientific_values_remain_numbers(backend: str, literal: str) -> None:
    """
    Retain finite numeric types, including small scientific defaults and underflow to zero.

    Args:
        backend (str): Manifest reader under test.
        literal (str): Numeric text accepted as a finite binary64 value.

    Returns:
        None: Implicit numbers remain numbers and explicit strings stay strings.
    """
    document = mapping(parsers.load_all(f'value: {literal}\nquoted: "{literal}"\n', backend=backend)[0])
    assert isinstance(document["value"], float)
    assert document["value"] == float(literal)
    assert document["quoted"] == literal


@pytest.mark.parametrize("backend", RUAMEL_BACKENDS)
def test_explicit_nonfinite_scalars_and_other_readers_are_unchanged(backend: str) -> None:
    """
    Limit compatibility handling to implicit overflow in the selected manifest reader.

    Args:
        backend (str): Manifest reader under test.

    Returns:
        None: Explicit tags and independent values-file readers retain their documented behavior.
    """
    document = mapping(parsers.load_all("overflow: !!float 1E400\ninf: .inf\nnan: .nan\n", backend=backend)[0])
    overflow, infinity, nan = document["overflow"], document["inf"], document["nan"]
    assert isinstance(overflow, float) and math.isinf(overflow)
    assert isinstance(infinity, float) and math.isinf(infinity)
    assert isinstance(nan, float) and math.isnan(nan)
    assert math.isinf(YAML(typ="rt").load("value: 1E400")["value"])
    values_overflow = mapping(yamlio.load("value: 1E400"))["value"]
    assert isinstance(values_overflow, float) and math.isinf(values_overflow)


@pytest.mark.integration
@pytest.mark.skipif(shutil.which("helm") is None, reason="requires Helm")
@pytest.mark.parametrize("backend", RUAMEL_BACKENDS)
def test_scalar_types_agree_with_native_helm(tmp_path: Path, backend: str) -> None:
    """
    Compare parsed manifest values with Helm's own YAML-to-JSON conversion.

    Args:
        tmp_path (Path): Synthetic chart and values files.
        backend (str): Manifest reader under test.

    Returns:
        None: Overflow strings and finite numbers match the independently rendered JSON oracle.
    """
    (tmp_path / "templates").mkdir()
    (tmp_path / "Chart.yaml").write_text("apiVersion: v2\nname: scalar-oracle\nversion: 0.1.0\n")
    source = "small: 1e-05\ntiny: 1e-06\nlarge: 1e308\noverflow: 1E400\nnegative: -1.0e400\nquantity: 2Gi\n"
    values = tmp_path / "values.json"
    values.write_text(json.dumps({"source": source}))
    (tmp_path / "templates/resource.yaml").write_text(
        dedent("""
        apiVersion: example.test/v1
        kind: ScalarFixture
        metadata:
          name: scalar-oracle
          annotations:
            native: {{ fromYaml .Values.source | toJson | quote }}
        spec:
          {{- .Values.source | nindent 2 }}
        """)
    )
    result = subprocess.run(
        ["helm", "template", "scalar-oracle", str(tmp_path), "--values", str(values)],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    documents = parsers.load_all(result.stdout, backend=backend)
    document = mapping(documents[0])
    annotations = mapping(mapping(document["metadata"])["annotations"])
    assert document["spec"] == json.loads(str(annotations["native"]))
    assert len(render_digest(documents)) == 32

"""
Verify generated chart value paths against their inferred contracts.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from hypothesis.strategies import DataObject
from hypothesis_helm import Chart
from hypothesis_helm.charts.generated import RenderOptions, check_path, prepared_chart
from hypothesis_helm.schemas.contracts import schema_strategy as from_schema
from hypothesis_helm.schemas.contracts import supported_generated_text

HERE = Path(__file__).resolve().parent
OPTIONS = RenderOptions(
    **{"timeout": 30, "helm": "helm", "release": "hypothesis", "namespace": "default", "kube_version": None, "allow_empty": False}
)


@pytest.fixture(scope="module")
def chart() -> Iterator[Chart]:
    """
    Prepare a temporary chart with the generated values contract.

    Yields:
        Chart: Isolated chart shared by this generated module.
    """
    with prepared_chart(HERE / "../workload", HERE) as chart:
        yield chart


# Path: ('replicas',); contract: schema
@pytest.mark.hypothesis_helm_path(("replicas",))
@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(value=(st.integers(min_value=0, max_value=5)).filter(supported_generated_text), data=st.data())
def test_replicas_fc55c2d623(chart: Chart, value: object, data: DataObject) -> None:
    """
    Verify that this value path renders valid resource envelopes.

    Args:
        chart (Chart): Temporary chart containing the coalesced values.
        value (object): Candidate drawn from the path strategy.
        data (DataObject): Draw context for schema-dependent siblings.

    Returns:
        None: Rendered resources satisfy the configured contract.
    """
    check_path(chart, ("replicas",), value, data, options=OPTIONS)


# Path: ('image',); contract: schema
@pytest.mark.hypothesis_helm_path(("image",))
@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    value=(
        from_schema(
            {
                "type": "object",
                "description": "Container image",
                "additionalProperties": False,
                "required": ["repository", "tag"],
                "properties": {
                    "repository": {"type": "string", "enum": ["nginx", "busybox"], "description": "Image repository"},
                    "tag": {"type": "string", "enum": ["stable", "latest"], "description": "Image tag"},
                },
            }
        )
    ).filter(supported_generated_text),
    data=st.data(),
)
def test_image_45e0390eb7(chart: Chart, value: object, data: DataObject) -> None:
    """
    Verify that this value path renders valid resource envelopes.

    Args:
        chart (Chart): Temporary chart containing the coalesced values.
        value (object): Candidate drawn from the path strategy.
        data (DataObject): Draw context for schema-dependent siblings.

    Returns:
        None: Rendered resources satisfy the configured contract.
    """
    check_path(chart, ("image",), value, data, options=OPTIONS)


# Path: ('image', 'repository'); contract: schema
@pytest.mark.hypothesis_helm_path(("image", "repository"))
@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(value=(st.sampled_from(["nginx", "busybox"])).filter(supported_generated_text), data=st.data())
def test_image_repository_7df0ac81c4(chart: Chart, value: object, data: DataObject) -> None:
    """
    Verify that this value path renders valid resource envelopes.

    Args:
        chart (Chart): Temporary chart containing the coalesced values.
        value (object): Candidate drawn from the path strategy.
        data (DataObject): Draw context for schema-dependent siblings.

    Returns:
        None: Rendered resources satisfy the configured contract.
    """
    check_path(chart, ("image", "repository"), value, data, options=OPTIONS)


# Path: ('image', 'tag'); contract: schema
@pytest.mark.hypothesis_helm_path(("image", "tag"))
@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(value=(st.sampled_from(["stable", "latest"])).filter(supported_generated_text), data=st.data())
def test_image_tag_5c4ac61fdd(chart: Chart, value: object, data: DataObject) -> None:
    """
    Verify that this value path renders valid resource envelopes.

    Args:
        chart (Chart): Temporary chart containing the coalesced values.
        value (object): Candidate drawn from the path strategy.
        data (DataObject): Draw context for schema-dependent siblings.

    Returns:
        None: Rendered resources satisfy the configured contract.
    """
    check_path(chart, ("image", "tag"), value, data, options=OPTIONS)

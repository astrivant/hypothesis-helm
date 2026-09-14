"""
Verify that plot questions stay below titles and above the measured panels.
"""

import pytest
from matplotlib import pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg

from hypothesis_helm.benchmarking.reporting.descriptions import INTRODUCTIONS, describe


@pytest.mark.parametrize("size", [(6.4, 4.8), (13, 5), (24, 18)])
def test_description_layout(size: tuple[float, float]) -> None:
    """
    Reserve physical space for wrapped descriptions in small and large figures.

    Args:
        size (tuple[float, float]): Figure dimensions in inches.

    Returns:
        None: Title, description and panel title have separate readable bounds.
    """
    figure, axis = plt.subplots(figsize=size)
    figure.suptitle("A chart comparison with a title that needs wrapping on a small figure")
    axis.set_title("Measured error detection")
    top = describe(figure, "clustering-error-recall")
    figure.tight_layout(rect=(0, 0.08, 1, top))
    canvas = FigureCanvasAgg(figure)
    canvas.draw()  # type: ignore[no-untyped-call]
    renderer = canvas.get_renderer()  # type: ignore[no-untyped-call]
    title, question = figure.texts
    assert question.get_gid() == "plot-question"
    assert "erroneous inputs" in question.get_text()
    assert title.get_window_extent(renderer).y0 > question.get_window_extent(renderer).y1
    assert question.get_window_extent(renderer).y0 > axis.title.get_window_extent(renderer).y1
    plt.close(figure)


def test_each_registered_plot_has_a_specific_question() -> None:
    """
    Require explicit questions instead of generic labels or inferred scientific claims.

    Returns:
        None: Each registered purpose has a title, a question and a distinct explanation.
    """
    questions = []
    for title, question in INTRODUCTIONS.values():
        assert title.strip() and "?" in question and len(question) < 220
        questions.append(question)
    assert len(set(questions)) == len(questions)
    figure = plt.figure()
    with pytest.raises(KeyError):
        describe(figure, "unregistered-study")
    assert 0 < describe(figure, "custom-study", question="What does this custom measurement compare?") < 1
    plt.close(figure)

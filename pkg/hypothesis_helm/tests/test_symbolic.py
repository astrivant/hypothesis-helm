"""
Verify leakage-free surface partitions and scoring without requiring Julia.
"""

import itertools
from pathlib import Path

import pytest

from hypothesis_helm.benchmarking.analysis.symbolic import partition, surfaces
from hypothesis_helm.benchmarking.studies.symbolic_surface import score


def test_partitions() -> None:
    """
    Reserve entire cells and one repeat with reproducible, disjoint assignments.

    Returns:
        None: Assertions verify no training observation leaks into holdouts.
    """
    rows: list[dict[str, object]] = [
        {"x": x, "y": y, "repeat": r, "status": "passed", "response": r * 100 + x + y}
        for x, y, r in itertools.product(range(3), range(8), range(3))
    ]
    split = partition(rows, 3, 2026)
    assert split == partition(rows, 3, 2026)
    training = {(x, y) for x, y, _ in split["train"]}
    held = {(x, y) for x, y, _ in split["cells"]}
    assert not training & held
    assert len(training) == 18 and len(held) == 6
    assert {(x, y) for x, y, _ in split["seeds"]} == training
    assert {(x, y) for x, y, _ in split["joint"]} == held
    assert all(z < 100 for _, _, z in split["train"])
    assert all(z >= 200 for _, _, z in split["observed"])
    assert {(0, 0), (0, 7), (2, 0), (2, 7)} <= training
    rows[0]["status"] = "time-limit"
    with pytest.raises(ValueError, match="censored"):
        partition(rows, 3, 2026)


def test_scores_and_missing_seeds() -> None:
    """
    Keep impossible predictions visible and reject absent validation evidence.

    Returns:
        None: Assertions check exact errors and degenerate holdouts.
    """
    assert score([0, 0], [-2, -2]) == {"rmse": 2.0, "r_squared": None}
    with pytest.raises(ValueError):
        score([1], [float("nan")])
    with pytest.raises(ValueError, match="two paired"):
        partition([{"x": 0, "y": 0, "repeat": 0, "status": "passed", "response": 1}], 1, 0)
    with pytest.raises(ValueError, match="absent"):
        surfaces({"rows": [{"strategy": "filter"}]}, ["missing"])


def test_missing_optional_dependency(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Explain installation when a requested optional backend is unavailable.

    Args:
        tmp_path (Path): Temporary source data location.
        monkeypatch (pytest.MonkeyPatch): Replace only the PySR import.

    Returns:
        None: Command exits with a normal CLI error instead of importing Julia.
    """
    import json

    import hypothesis_helm.benchmarking.studies.symbolic_surface as study

    source = tmp_path / "results.json"
    source.write_text(json.dumps({"rows": [], "metadata": {}}))

    def missing(name: str) -> object:
        """
        Simulate an absent optional package.

        Args:
            name (str): Requested import.

        Returns:
            object: Always raises the import failure under test.
        """
        raise ModuleNotFoundError(name=name)

    monkeypatch.setattr("hypothesis_helm.benchmarking.studies.symbolic_surface.importlib.import_module", missing)
    with pytest.raises(SystemExit) as error:
        study.main(["--input", str(source)])
    assert error.value.code == 2


def test_source_cannot_be_overwritten(tmp_path: Path) -> None:
    """
    Refuse an output directory that would replace the source measurement ledger.

    Args:
        tmp_path (Path): Source and conflicting output location.

    Returns:
        None: The rejected command leaves the source bytes intact.
    """
    from hypothesis_helm.benchmarking.studies.symbolic_surface import main

    source = tmp_path / "results.json"
    original = '{"rows": [], "metadata": {}}'
    source.write_text(original)
    with pytest.raises(SystemExit) as error:
        main(["--input", str(source), "--output", str(tmp_path)])
    assert error.value.code == 2
    assert source.read_text() == original

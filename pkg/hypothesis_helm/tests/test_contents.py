"""
Keep documentation links correct when headings repeat or generated reports change.
"""

from pathlib import Path
from textwrap import dedent

from hypothesis_helm.reporting.contents import main, with_contents


def test_contents_skip_examples_and_comments() -> None:
    """
    Ignore example headings and hidden generator code, preserving document content.

    Returns:
        None: Generated contents match the visible sections and remain stable.
    """
    document = dedent(
        """
        # Guide

        Introduction.

        ## Install `--filter`

        ````markdown
        ## Not a section
        ```
        ### Still inside the fence
        ````

        <!--
        ## Generator comment
        -->

        ### [Next steps](next.md) & checks

        ## Install `--filter`

        ## Install --filter-1
        """
    ).lstrip()
    result = with_contents(document)
    assert "- [Install --filter](#install---filter)" in result
    assert "  - [Next steps &amp; checks](#next-steps--checks)" in result
    assert "- [Install --filter](#install---filter-1)" in result
    assert "- [Install --filter-1](#install---filter-1-1)" in result
    contents, body = result.split("<!-- toc:end -->", 1)
    assert "Not a section" not in contents
    assert "Still inside the fence" not in contents
    assert "Generator comment" not in contents
    assert body.lstrip() == document.split("\n\n", 1)[1]
    assert with_contents(result) == result


def test_contents_update_removed_and_new_sections() -> None:
    """
    Regenerate links without keeping stale entries or accumulating contents blocks.

    Returns:
        None: Generated contents match the visible sections and remain stable.
    """
    result = with_contents("# Report\n\n## Before\n\nText.\n")
    result = with_contents(result.replace("## Before", "## After") + "\n## Details\n")
    assert "#before" not in result
    assert "[After](#after)" in result
    assert "[Details](#details)" in result
    assert result.count("<!-- toc:start -->") == 1
    assert with_contents("# Single page\n\nText.\n").count("[Single page](#single-page)") == 1
    assert with_contents("Plain text without headings.\n") == "Plain text without headings.\n"


def test_contents_collapse_long_reports() -> None:
    """
    Keep chart-heavy reports navigable without pushing the summary far down the page.

    Returns:
        None: Generated contents match the visible sections and remain stable.
    """
    document = "# Charts\n\n" + "".join(f"## Chart {index}\n\n" for index in range(21))
    result = with_contents(document)
    assert "<summary>Table of contents</summary>" in result
    assert "- [Chart 20](#chart-20)" in result
    assert with_contents(result) == result


def test_contents_command_check_and_archive_exclusions(tmp_path: Path) -> None:
    """
    Check without writing, update ordinary docs, and leave checksummed snapshots intact.

    Args:
        tmp_path (Path): Temporary maintained document and retained run directory.

    Returns:
        None: Checks do not write and archived snapshots remain unchanged.
    """
    document = tmp_path / "README.md"
    document.write_text("# Guide\n\n## Run\n")
    original = document.read_text()
    archived = tmp_path / "runs" / "README.md"
    archived.parent.mkdir()
    archived.write_text(original)
    assert main(["--check", str(document)]) == 1
    assert document.read_text() == original
    assert main([str(document), str(archived)]) == 0
    assert main(["--check", str(document), str(archived)]) == 0
    assert archived.read_text() == original

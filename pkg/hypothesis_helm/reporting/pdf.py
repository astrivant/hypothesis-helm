"""
Render branded, paginated PDF reports while preserving links and input examples.
"""

import re
import textwrap
from html import escape
from importlib.resources import files
from io import BytesIO
from pathlib import Path

from reportlab.lib.styles import ParagraphStyle  # type: ignore[import-untyped]
from reportlab.lib.utils import ImageReader  # type: ignore[import-untyped]
from reportlab.pdfgen.canvas import Canvas  # type: ignore[import-untyped]
from reportlab.platypus import Paragraph  # type: ignore[import-untyped]

from hypothesis_helm.reporting.links import LINK, linked_prose


def write_pdf(content: str, pdf: Path, *, title: str = "Helm chart scan") -> None:
    """
    Render report Markdown with a reserved header and working PDF hyperlinks.

    Args:
        content (str): Report prose and fenced reproducing values.
        pdf (Path): Destination PDF file.
        title (str): Document metadata title.

    Returns:
        None: The PDF contains its logo without requiring an external image file.
    """
    canvas = Canvas(str(pdf), pagesize=(612, 792))
    logo = ImageReader(BytesIO(files("hypothesis_helm.reporting").joinpath("assets", "logo.png").read_bytes()))

    lines = content.splitlines()
    heading = next((index for index, line in enumerate(lines) if line.strip()), None)
    header_title = title
    if heading is not None and lines[heading].startswith("# "):
        header_title = lines.pop(heading)[2:].strip()

    def page_header() -> float:
        """
        Align the report title and compact logo within one shared header.

        Returns:
            float: Body baseline below the header divider, accounting for wrapped titles.
        """
        canvas.saveState()
        paragraph = Paragraph(escape(header_title), ParagraphStyle("header", fontName="Helvetica-Bold", fontSize=14, leading=18))
        _, height = paragraph.wrap(486, 708)
        paragraph.drawOn(canvas, 36, 766 - height)
        # The packaged square asset includes transparent padding around the mark.
        # Its visible right edge aligns with the body's 576-point right margin.
        canvas.drawImage(logo, 543, 734, width=44, height=44, mask="auto", preserveAspectRatio=True)
        divider = min(736.0, 756 - float(height))
        canvas.setStrokeColorRGB(0.82, 0.85, 0.88)
        canvas.setLineWidth(0.5)
        canvas.line(36, divider, 576, divider)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColorRGB(0.4, 0.44, 0.48)
        canvas.drawRightString(576, 24, str(canvas.getPageNumber()))
        canvas.restoreState()
        return divider - 20

    canvas.setTitle(title)
    y = page_header()
    canvas.setFont("Courier", 8)
    code_fence = ""
    for line in lines:
        if not line.strip():
            y -= 4
            continue
        marker = re.match(r"^(`{3,})(.*)$", line)
        if not code_fence and marker:
            code_fence = marker[1]
            continue
        if code_fence and re.fullmatch(re.escape(code_fence) + r"`*\s*", line):
            code_fence = ""
            continue
        if not code_fence and LINK.search(line):
            paragraph = Paragraph(linked_prose(line), ParagraphStyle("links", fontName="Courier", fontSize=8, leading=12))
            _, height = paragraph.wrap(540, 708)
            if y - height < 42:
                canvas.showPage()
                y = page_header()
            paragraph.drawOn(canvas, 36, y + 8 - height)
            y -= height
            continue
        if not code_fence:
            line = re.sub(r"\[([^\]]+)\]\(<\1>\)", r"\1", line)
            line = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", line)
            line = line.replace("**", "").replace("`", "")
        heading = not code_fence and line.startswith("#")
        if heading and y < 120:
            canvas.showPage()
            y = page_header()
        font = "Helvetica-Bold" if heading else "Courier"
        size = 14 if line.startswith("# ") else 11 if heading else 8
        content = line.lstrip("# ") if heading else line
        for wrapped in textwrap.wrap(content, width=85 if heading else 100) or [""]:
            if y < 42:
                canvas.showPage()
                y = page_header()
            canvas.setFont(font, size)
            canvas.drawString(36, y, wrapped.encode("latin-1", "backslashreplace").decode("latin-1"))
            y -= size + 4
    canvas.save()

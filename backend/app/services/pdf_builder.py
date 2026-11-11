from __future__ import annotations

from datetime import datetime, timezone
import io
from pathlib import Path
from typing import Sequence
import xml.sax.saxutils as saxutils

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
)

from app.schemas import QAItem

# Design token colors
COLOR_TITLE = colors.HexColor("#1E293B")  # Slate 800
COLOR_TEXT = colors.HexColor("#334155")  # Slate 700
COLOR_MUTED = colors.HexColor("#64748B")  # Slate 500
COLOR_BORDER = colors.HexColor("#E2E8F0")  # Slate 200
COLOR_PRIMARY = colors.HexColor("#3B6FD4")  # Academic Blue


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas that adds running headers and dynamic 'Page X of Y' footers."""

    def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict] = []  # type: ignore[type-arg]

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_header_footer(num_pages)
            super().showPage()
        super().save()

    def _draw_header_footer(self, total_pages: int) -> None:
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(COLOR_MUTED)

        # Draw running header on page 2 and later
        if self._pageNumber > 1:
            self.drawString(54, letter[1] - 36, "Study Guide")
            self.setStrokeColor(COLOR_BORDER)
            self.setLineWidth(0.5)
            self.line(54, letter[1] - 42, letter[0] - 54, letter[1] - 42)

        # Draw running footer on all pages
        footer_text = f"Page {self._pageNumber} of {total_pages}"
        self.drawRightString(letter[0] - 54, 36, footer_text)

        self.setStrokeColor(COLOR_BORDER)
        self.setLineWidth(0.5)
        self.line(54, 48, letter[0] - 54, 48)

        self.restoreState()


def _escape_text(raw_text: str) -> str:
    """Escape XML characters and convert newlines to <br/> tags for ReportLab."""
    escaped = saxutils.escape(raw_text)
    # Convert consecutive newlines to paragraph breaks, single newlines to br
    return escaped.replace("\r\n", "\n").replace("\n", "<br/>")


def _get_styles() -> dict[str, ParagraphStyle]:
    """Build typographic hierarchy styles for the study guide document."""
    base_styles = getSampleStyleSheet()

    return {
        "Title": ParagraphStyle(
            name="GuideTitle",
            parent=base_styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            textColor=COLOR_TITLE,
            spaceAfter=6,
        ),
        "Subtitle": ParagraphStyle(
            name="GuideSubtitle",
            parent=base_styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=COLOR_MUTED,
            spaceAfter=14,
        ),
        "Question": ParagraphStyle(
            name="GuideQuestion",
            parent=base_styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=15,
            textColor=COLOR_TITLE,
            spaceAfter=4,
            keepWithNext=True,  # Avoid orphan questions at the bottom of a page
        ),
        "Answer": ParagraphStyle(
            name="GuideAnswer",
            parent=base_styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=COLOR_TEXT,
            spaceAfter=8,
        ),
    }


def build_qa_pdf(title: str, qa_items: Sequence[QAItem]) -> bytes:
    """Build a formatted study guide PDF and return the raw PDF bytes.

    Args:
        title: Title of the study guide.
        qa_items: List of QAItem objects (question, answer, optional page ref).

    Returns:
        bytes: Complete generated PDF data.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=54,  # 0.75 in
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
        title=title,
        author="PDF Q&A Study Guide",
    )

    styles = _get_styles()
    story: list[object] = []

    # Document Header
    escaped_title = _escape_text(title)
    story.append(Paragraph(escaped_title, styles["Title"]))

    gen_date = datetime.now(timezone.utc).strftime("%B %d, %Y")
    subtitle_text = f"Study Guide · Generated on {gen_date} · {len(qa_items)} question{'s' if len(qa_items) != 1 else ''}"
    story.append(Paragraph(_escape_text(subtitle_text), styles["Subtitle"]))

    # Accent divider rule
    story.append(
        HRFlowable(
            width="100%",
            thickness=1.5,
            color=COLOR_PRIMARY,
            spaceAfter=16,
            spaceBefore=0,
        )
    )

    # Q&A Items
    for index, item in enumerate(qa_items, start=1):
        # Format Question header with optional page reference
        q_text = _escape_text(item.question)
        if item.page is not None:
            page_badge = f' <font color="#64748B" size="8.5">[p. {item.page}]</font>'
            question_html = f"<b>Q{index}.</b> {q_text}{page_badge}"
        else:
            question_html = f"<b>Q{index}.</b> {q_text}"

        story.append(Paragraph(question_html, styles["Question"]))

        # Format Answer body (handles wrapping across pages gracefully)
        a_text = _escape_text(item.answer)
        answer_html = f'<font color="#3B6FD4"><b>A:</b></font> {a_text}'
        story.append(Paragraph(answer_html, styles["Answer"]))

        # Separator line between Q&A items (except after the last item)
        if index < len(qa_items):
            story.append(
                HRFlowable(
                    width="100%",
                    thickness=0.5,
                    color=COLOR_BORDER,
                    spaceAfter=12,
                    spaceBefore=4,
                )
            )

    doc.build(story, canvasmaker=NumberedCanvas)
    return buffer.getvalue()


def build_qa_pdf_to_file(
    title: str, qa_items: Sequence[QAItem], output_path: Path | str
) -> Path:
    """Generate a study guide PDF and write it directly to a file path."""
    dest = Path(output_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    pdf_bytes = build_qa_pdf(title, qa_items)
    dest.write_bytes(pdf_bytes)
    return dest

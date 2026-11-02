"""Paragraph and table extraction using the SRS-mandated python-docx."""

from pathlib import Path

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.extraction.models import ExtractedPage


class DocxExtractionError(RuntimeError):
    """Raised when a DOCX cannot be extracted."""


def extract_docx(file_path: Path) -> list[ExtractedPage]:
    try:
        document = Document(file_path)
        blocks: list[str] = []
        for item in document.iter_inner_content():
            if isinstance(item, Paragraph):
                if item.text.strip():
                    blocks.append(item.text)
            elif isinstance(item, Table):
                for row in item.rows:
                    blocks.append("\t".join(cell.text for cell in row.cells))
        # OOXML does not expose stable physical pagination. SRS page-aware PDF
        # extraction remains physical; DOCX is represented as one logical page.
        return [ExtractedPage(pageNumber=1, text="\n".join(blocks))]
    except Exception as exc:
        raise DocxExtractionError("DOCX extraction failed") from exc


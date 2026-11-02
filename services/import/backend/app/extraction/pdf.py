"""Page-aware PDF extraction using the SRS-mandated PyMuPDF."""

from pathlib import Path

import fitz

from app.extraction.models import ExtractedPage


class PdfExtractionError(RuntimeError):
    """Raised when a PDF cannot be extracted."""


def extract_pdf(file_path: Path) -> list[ExtractedPage]:
    try:
        with fitz.open(file_path) as document:
            if document.needs_pass or document.page_count < 1:
                raise PdfExtractionError("PDF is encrypted, empty, or unreadable")
            return [
                ExtractedPage(
                    pageNumber=page_index + 1,
                    text=document.load_page(page_index).get_text("text"),
                )
                for page_index in range(document.page_count)
            ]
    except PdfExtractionError:
        raise
    except Exception as exc:
        raise PdfExtractionError("PDF extraction failed") from exc


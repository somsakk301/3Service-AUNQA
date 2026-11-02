from pathlib import Path

import fitz
from docx import Document as WordDocument

from app.extraction.docx import extract_docx
from app.extraction.pdf import extract_pdf


def make_pdf(file_path: Path) -> None:
    document = fitz.open()
    first_page = document.new_page()
    first_page.insert_text((72, 72), "First page")
    second_page = document.new_page()
    second_page.insert_text((72, 72), "Second page")
    document.save(file_path)
    document.close()


def test_pdf_extraction_preserves_page_numbers(tmp_path: Path) -> None:
    file_path = tmp_path / "two-pages.pdf"
    make_pdf(file_path)

    pages = extract_pdf(file_path)

    assert [page.pageNumber for page in pages] == [1, 2]
    assert "First page" in pages[0].text
    assert "Second page" in pages[1].text


def test_docx_extraction_reads_paragraphs_and_tables(tmp_path: Path) -> None:
    file_path = tmp_path / "content.docx"
    document = WordDocument()
    document.add_paragraph("Paragraph content")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Column A"
    table.cell(0, 1).text = "Column B"
    document.save(file_path)

    pages = extract_docx(file_path)

    assert len(pages) == 1
    assert pages[0].pageNumber == 1
    assert pages[0].text == "Paragraph content\nColumn A\tColumn B"


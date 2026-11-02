"""Create PDF entry files whose built-in OpenAction targets each referenced page."""

from pathlib import Path

import pymupdf


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DIR = ROOT / "services" / "monitor" / "frontend" / "public" / "references"
SOURCE = REFERENCE_DIR / "wuqa-template-2568.pdf"
TARGET_PAGES = (14, 15, 17, 18)


def main() -> None:
    for page_number in TARGET_PAGES:
        output = SOURCE.with_name(f"{SOURCE.stem}-page-{page_number}.pdf")
        document = pymupdf.open(SOURCE)
        page_reference = document[page_number - 1].xref
        document.xref_set_key(
            document.pdf_catalog(),
            "OpenAction",
            f"[{page_reference} 0 R /Fit]",
        )
        document.save(output)
        document.close()
        print(f"created {output.name}: opens PDF page {page_number}")


if __name__ == "__main__":
    main()

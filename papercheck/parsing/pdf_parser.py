"""PyMuPDF-based raw text extraction from PDF files."""

from __future__ import annotations

from pathlib import Path

import pymupdf


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract all text from a PDF file using PyMuPDF.

    Returns the concatenated text of all pages.
    Raises FileNotFoundError if pdf_path doesn't exist.
    """
    doc = pymupdf.open(str(pdf_path))
    pages = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()
    return "\n".join(pages)

"""GROBID TEI XML structured parsing — stub for Phase 1."""

from __future__ import annotations

from pathlib import Path

from papercheck.models import (
    EquationRef,
    FigureRef,
    Reference,
    Section,
    TableRef,
)


async def parse_pdf_with_grobid(
    pdf_path: Path, grobid_url: str = "http://localhost:8070"
) -> dict | None:
    """Send PDF to GROBID and parse TEI XML response.

    Returns None if GROBID is unavailable. Full implementation in Phase 2.
    """
    # Phase 1 stub — GROBID integration is Phase 2
    return None

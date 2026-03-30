"""Extract abstract, contributions, and conclusions from paper data."""

from __future__ import annotations

from papercheck.models import PaperData, Section


def get_abstract(paper: PaperData) -> str:
    """Return the paper's abstract text."""
    return paper.abstract


def get_introduction(paper: PaperData) -> str:
    """Return the introduction section text."""
    return _find_section_text(paper, ["introduction", "intro"])


def get_conclusion(paper: PaperData) -> str:
    """Return the conclusion section text."""
    return _find_section_text(
        paper, ["conclusion", "conclusions", "concluding remarks", "discussion and conclusion"]
    )


def get_methods(paper: PaperData) -> str:
    """Return the methodology section text."""
    return _find_section_text(
        paper, ["method", "methods", "methodology", "approach", "our approach", "model"]
    )


def get_results(paper: PaperData) -> str:
    """Return the results section text."""
    return _find_section_text(
        paper, ["results", "experiments", "experimental results", "evaluation"]
    )


def _find_section_text(paper: PaperData, candidates: list[str]) -> str:
    """Find a section by heading (case-insensitive partial match)."""
    for section in paper.sections:
        heading_lower = section.heading.lower().strip()
        for candidate in candidates:
            if candidate in heading_lower:
                return section.text
    return ""

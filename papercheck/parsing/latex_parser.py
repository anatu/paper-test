"""LaTeX source parsing — minimal implementation for Phase 1."""

from __future__ import annotations

import re
from pathlib import Path

from papercheck.models import EquationRef, Reference, Section


def parse_latex_source(tex_path: Path) -> dict:
    """Parse a .tex file and extract structure.

    Returns a dict with keys: sections, references, equations, labels, refs, cites, raw_text.
    """
    source = tex_path.read_text(errors="ignore")
    return parse_latex_string(source)


def parse_latex_string(source: str) -> dict:
    """Parse a LaTeX string and extract structure."""
    sections = _extract_sections(source)
    references = _extract_bibitem_references(source)
    equations = _extract_equations(source)
    labels = _extract_labels(source)
    refs = _extract_refs(source)
    cites = _extract_cites(source)

    return {
        "sections": sections,
        "references": references,
        "equations": equations,
        "labels": labels,
        "refs": refs,
        "cites": cites,
        "raw_text": source,
    }


def _extract_sections(source: str) -> list[Section]:
    """Extract section headings and their text content."""
    pattern = re.compile(
        r"\\(section|subsection|subsubsection)\*?\{([^}]*)\}", re.MULTILINE
    )
    matches = list(pattern.finditer(source))
    sections: list[Section] = []
    level_map = {"section": 1, "subsection": 2, "subsubsection": 3}

    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(source)
        text = source[start:end].strip()
        # Check for a \label right after the section command
        label_match = re.match(r"\s*\\label\{([^}]*)\}", text)
        label = label_match.group(1) if label_match else None
        sections.append(
            Section(
                heading=m.group(2).strip(),
                level=level_map.get(m.group(1), 1),
                text=text,
                label=label,
            )
        )
    return sections


def _extract_bibitem_references(source: str) -> list[Reference]:
    """Extract references from \\bibitem entries."""
    pattern = re.compile(r"\\bibitem\{([^}]*)\}\s*(.*?)(?=\\bibitem|\Z)", re.DOTALL)
    refs: list[Reference] = []
    for m in pattern.finditer(source):
        raw = m.group(2).strip()[:500]
        title, authors, year = _parse_bibitem_text(raw)
        refs.append(
            Reference(
                key=m.group(1).strip(),
                title=title,
                authors=authors,
                year=year,
                raw_text=raw,
            )
        )
    return refs


def _parse_bibitem_text(raw: str) -> tuple[str | None, list[str], int | None]:
    """Extract title, authors, and year from a raw bibitem text string.

    Common formats:
      Author, A. and Author, B. (2023). Title Here. Venue, pages.
      Author, A., Author, B., 2023. Title Here. Venue.
    """
    # Extract year
    year_match = re.search(r"\((\d{4})\)|,\s*(\d{4})\b", raw)
    year = int(year_match.group(1) or year_match.group(2)) if year_match else None

    # Try to extract title: text after "(YYYY)." or ", YYYY." up to next period
    title = None
    if year_match:
        after_year = raw[year_match.end():]
        # Strip leading punctuation/whitespace
        after_year = re.sub(r"^[\s.,)]+", "", after_year)
        # Title is typically the next sentence (up to period)
        title_match = re.match(r"(.+?)(?:\.|$)", after_year)
        if title_match:
            candidate = title_match.group(1).strip()
            if len(candidate) > 5:  # Skip very short fragments
                title = candidate

    # Extract authors: text before the year
    authors: list[str] = []
    if year_match:
        before_year = raw[:year_match.start()].strip().rstrip(",").rstrip(".")
        # Split on " and " or ", " (but not within names like "Smith, J.")
        author_parts = re.split(r"\s+and\s+", before_year)
        for part in author_parts:
            part = part.strip().rstrip(",")
            if part:
                authors.append(part)

    return title, authors, year


def _extract_equations(source: str) -> list[EquationRef]:
    """Extract labeled equations from equation/align environments."""
    envs = re.compile(
        r"\\begin\{(equation|align|gather)\*?\}(.*?)\\end\{\1\*?\}",
        re.DOTALL,
    )
    eqs: list[EquationRef] = []
    for m in envs.finditer(source):
        content = m.group(2).strip()
        label_match = re.search(r"\\label\{([^}]*)\}", content)
        eqs.append(
            EquationRef(
                label=label_match.group(1) if label_match else None,
                raw_latex=content,
            )
        )
    return eqs


def _extract_labels(source: str) -> set[str]:
    """Extract all \\label{...} keys."""
    return set(re.findall(r"\\label\{([^}]*)\}", source))


def _extract_refs(source: str) -> list[str]:
    """Extract all \\ref{...} and \\eqref{...} targets."""
    return re.findall(r"\\(?:eq)?ref\{([^}]*)\}", source)


def _extract_cites(source: str) -> list[str]:
    """Extract all \\cite{...} keys (handles comma-separated)."""
    raw = re.findall(r"\\cite[tp]?\{([^}]*)\}", source)
    keys: list[str] = []
    for group in raw:
        keys.extend(k.strip() for k in group.split(","))
    return keys

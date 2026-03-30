"""Unified paper loader — accepts ArXiv ID, PDF path, or .tex path."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from papercheck.config import PipelineConfig
from papercheck.models import PaperData, PaperMetadata, Section
from papercheck.parsing.pdf_parser import extract_text_from_pdf
from papercheck.parsing.latex_parser import parse_latex_source


class PaperLoadError(Exception):
    """Raised when a paper cannot be loaded."""


def _is_arxiv_id(source: str) -> bool:
    """Check if source looks like an ArXiv ID (e.g. 2301.00001 or hep-ph/0601001)."""
    return bool(re.match(r"^(\d{4}\.\d{4,5}|[a-z-]+/\d{7})$", source))


def _find_main_tex(paper_dir: Path) -> Path | None:
    """Find the main .tex file in a directory (has \\documentclass)."""
    tex_files = list(paper_dir.glob("*.tex"))
    if not tex_files:
        return None
    if len(tex_files) == 1:
        return tex_files[0]
    for f in tex_files:
        content = f.read_text(errors="ignore")
        if r"\documentclass" in content:
            return f
    return tex_files[0]


def _extract_title_from_latex(source: str) -> str:
    """Extract \\title{...} from LaTeX source."""
    m = re.search(r"\\title\{([^}]*)\}", source)
    return m.group(1).strip() if m else ""


def _extract_authors_from_latex(source: str) -> list[str]:
    """Extract \\author{...} from LaTeX source."""
    m = re.search(r"\\author\{([^}]*)\}", source, re.DOTALL)
    if not m:
        return []
    raw = m.group(1)
    # Split on \and or \\
    parts = re.split(r"\\and|\\\\", raw)
    return [re.sub(r"\\[a-zA-Z]+\{[^}]*\}|\\[a-zA-Z]+", "", p).strip() for p in parts if p.strip()]


def _extract_abstract_from_latex(source: str) -> str:
    """Extract abstract from \\begin{abstract}...\\end{abstract}."""
    m = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", source, re.DOTALL)
    return m.group(1).strip() if m else ""


def load_paper(source: str, config: PipelineConfig | None = None) -> PaperData:
    """Load a paper from an ArXiv ID, PDF path, or .tex path.

    For ArXiv IDs, uses the existing fetch_arxiv.py to download source into data/arxiv/.
    """
    if _is_arxiv_id(source):
        return _load_from_arxiv(source, config)

    path = Path(source)
    if not path.exists():
        raise PaperLoadError(f"File not found: {source}")

    if path.suffix == ".pdf":
        return _load_from_pdf(path)
    elif path.suffix == ".tex":
        return _load_from_latex(path)
    else:
        raise PaperLoadError(f"Unsupported file type: {path.suffix}")


def _load_from_arxiv(arxiv_id: str, config: PipelineConfig | None = None) -> PaperData:
    """Download and load a paper from ArXiv using the existing fetch_arxiv.py."""
    # Import fetch_arxiv from repo root
    repo_root = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(repo_root))
    try:
        import fetch_arxiv
    except ImportError as e:
        raise PaperLoadError(f"Cannot import fetch_arxiv.py from repo root: {e}") from e
    finally:
        sys.path.pop(0)

    out_dir = repo_root / "data" / "arxiv"
    out_dir.mkdir(parents=True, exist_ok=True)

    paper_dir = fetch_arxiv.download_source(arxiv_id, out_dir)
    if paper_dir is None:
        raise PaperLoadError(f"Failed to download ArXiv paper: {arxiv_id}")

    main_tex = _find_main_tex(paper_dir) or fetch_arxiv.find_main_tex(paper_dir)
    if main_tex is None:
        raise PaperLoadError(f"No .tex file found for ArXiv paper: {arxiv_id}")

    paper = _load_from_latex(main_tex)
    paper.source_type = "arxiv"
    paper.arxiv_id = arxiv_id
    return paper


def _load_from_pdf(pdf_path: Path) -> PaperData:
    """Load a paper from a PDF file using PyMuPDF text extraction."""
    raw_text = extract_text_from_pdf(pdf_path)

    # For Phase 1, we get raw text only. GROBID (Phase 2) will give us structure.
    return PaperData(
        source_type="pdf",
        title=pdf_path.stem,
        raw_text=raw_text,
    )


def _load_from_latex(tex_path: Path) -> PaperData:
    """Load a paper from a .tex file."""
    parsed = parse_latex_source(tex_path)
    source = parsed["raw_text"]

    title = _extract_title_from_latex(source)
    authors = _extract_authors_from_latex(source)
    abstract = _extract_abstract_from_latex(source)

    return PaperData(
        source_type="latex",
        title=title,
        authors=authors,
        abstract=abstract,
        sections=parsed["sections"],
        raw_text=source,
        references=parsed["references"],
        equations=parsed["equations"],
        latex_source=source,
    )

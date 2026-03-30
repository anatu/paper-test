"""Tests for paper parsing."""

from __future__ import annotations

from pathlib import Path

from papercheck.parsing.latex_parser import parse_latex_source
from papercheck.parsing.paper_loader import load_paper, PaperLoadError

import pytest


class TestLatexParser:
    def test_extracts_sections(self, sample_clean_tex: Path):
        result = parse_latex_source(sample_clean_tex)
        headings = [s.heading for s in result["sections"]]
        assert "Introduction" in headings
        assert "Methodology" in headings
        assert "Results" in headings
        assert "Conclusion" in headings

    def test_extracts_labels(self, sample_clean_tex: Path):
        result = parse_latex_source(sample_clean_tex)
        assert "sec:intro" in result["labels"]
        assert "sec:method" in result["labels"]
        assert "eq:main" in result["labels"]
        assert "tab:results" in result["labels"]

    def test_extracts_refs(self, sample_clean_tex: Path):
        result = parse_latex_source(sample_clean_tex)
        assert "sec:method" in result["refs"]
        assert "eq:main" in result["refs"]
        assert "tab:results" in result["refs"]

    def test_extracts_cites(self, sample_clean_tex: Path):
        result = parse_latex_source(sample_clean_tex)
        # No \cite commands in the clean sample, but bibitem keys are extracted
        assert len(result["references"]) == 2

    def test_extracts_equations(self, sample_clean_tex: Path):
        result = parse_latex_source(sample_clean_tex)
        assert len(result["equations"]) >= 1
        eq = result["equations"][0]
        assert eq.label == "eq:main"

    def test_extracts_bibitem_references(self, sample_clean_tex: Path):
        result = parse_latex_source(sample_clean_tex)
        keys = [r.key for r in result["references"]]
        assert "smith2023" in keys
        assert "jones2022" in keys

    def test_dangling_refs_detected(self, sample_dangling_ref_tex: Path):
        result = parse_latex_source(sample_dangling_ref_tex)
        labels = result["labels"]
        refs = result["refs"]
        dangling = [r for r in refs if r not in labels]
        assert len(dangling) >= 3  # fig:nonexistent, tab:missing, sec:phantom, etc.


class TestPaperLoader:
    def test_load_latex_file(self, sample_clean_tex: Path):
        paper = load_paper(str(sample_clean_tex))
        assert paper.source_type == "latex"
        assert paper.title == "A Sample Clean Paper for Testing"
        assert len(paper.authors) == 2
        assert "Alice Test" in paper.authors
        assert paper.abstract != ""
        assert len(paper.sections) >= 4
        assert len(paper.references) == 2

    def test_load_nonexistent_file_raises(self):
        with pytest.raises(PaperLoadError, match="File not found"):
            load_paper("/nonexistent/path.tex")

    def test_load_unsupported_format_raises(self, tmp_path: Path):
        bad = tmp_path / "paper.docx"
        bad.write_text("not a real docx")
        with pytest.raises(PaperLoadError, match="Unsupported file type"):
            load_paper(str(bad))

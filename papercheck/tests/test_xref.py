"""Tests for cross-reference integrity checker."""

from __future__ import annotations

from pathlib import Path

from papercheck.checkers.xref_integrity import check_xref_integrity
from papercheck.parsing.paper_loader import load_paper


class TestXrefIntegrity:
    def test_clean_paper_no_dangling(self, sample_clean_tex: Path):
        paper = load_paper(str(sample_clean_tex))
        findings = check_xref_integrity(paper)
        dangling = [f for f in findings if f.category == "dangling_reference"]
        assert len(dangling) == 0

    def test_dangling_refs_detected(self, sample_dangling_ref_tex: Path):
        paper = load_paper(str(sample_dangling_ref_tex))
        findings = check_xref_integrity(paper)
        dangling = [f for f in findings if f.category == "dangling_reference"]
        # fig:nonexistent, tab:missing, sec:phantom, eq:ghost, sec:results_gone
        assert len(dangling) >= 4

    def test_unreferenced_labels_flagged(self, sample_clean_tex: Path):
        paper = load_paper(str(sample_clean_tex))
        findings = check_xref_integrity(paper)
        unreferenced = [f for f in findings if f.category == "unreferenced_label"]
        # sec:conclusion is defined but never \ref'd in the clean sample
        labels_unrefd = [f.message for f in unreferenced]
        assert any("sec:conclusion" in m for m in labels_unrefd)

    def test_no_latex_source_skips(self):
        from papercheck.models import PaperData
        paper = PaperData(source_type="pdf", raw_text="Some text")
        findings = check_xref_integrity(paper)
        assert len(findings) == 1
        assert findings[0].category == "xref_skipped"

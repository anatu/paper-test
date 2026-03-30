"""Integration tests for Layer 2: Citation Verification."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from papercheck.config import PipelineConfig
from papercheck.external.semantic_scholar import S2Paper
from papercheck.layers.layer2_citations import CitationVerificationLayer
from papercheck.llm.schemas import CitationAlignmentResult
from papercheck.parsing.paper_loader import load_paper


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def layer():
    return CitationVerificationLayer()


@pytest.fixture
def config_no_llm():
    """Config without API key — LLM checks degrade gracefully."""
    return PipelineConfig(anthropic_api_key="")


@pytest.fixture
def sample_hallucinated_cite_tex() -> Path:
    return FIXTURES_DIR / "sample_hallucinated_cite.tex"


@pytest.fixture
def sample_misattribution_tex() -> Path:
    return FIXTURES_DIR / "sample_misattribution.tex"


@pytest.fixture
def sample_good_citations_tex() -> Path:
    return FIXTURES_DIR / "sample_good_citations.tex"


def _mock_s2_client(found_titles: dict[str, S2Paper | None] = None):
    """Create a mock S2 client that returns papers for specified titles."""
    found = found_titles or {}
    client = MagicMock()
    client.close = MagicMock()

    def search_by_title(title, authors=None, year=None):
        title_lower = title.lower().strip().rstrip(".")
        for key, paper in found.items():
            if key.lower().strip().rstrip(".") in title_lower or title_lower in key.lower():
                return paper
        return None

    client.get_paper_by_title = MagicMock(side_effect=search_by_title)
    client.get_recommendations = MagicMock(return_value=[])
    return client


def _mock_crossref_client(found_titles: dict[str, dict] = None):
    """Create a mock CrossRef client."""
    found = found_titles or {}
    client = MagicMock()
    client.close = MagicMock()

    def lookup(title, author=None):
        title_lower = title.lower().strip().rstrip(".")
        for key, data in found.items():
            if key.lower() in title_lower or title_lower in key.lower():
                return data
        return None

    client.lookup_by_title = MagicMock(side_effect=lookup)
    return client


def _mock_openalex_client():
    """Create a mock OpenAlex client that finds nothing."""
    client = MagicMock()
    client.close = MagicMock()
    client.search_by_title = MagicMock(return_value=None)
    return client


# ── Existence checks (no LLM needed) ───────────────────────────────────────


class TestCitationExistence:
    @pytest.mark.asyncio
    async def test_hallucinated_citation_detected(self, layer, config_no_llm, sample_hallucinated_cite_tex):
        """A fabricated citation should produce a citation_not_found finding."""
        paper = load_paper(str(sample_hallucinated_cite_tex))

        # Only the "real" citation is found; fake ones return None
        real_paper = S2Paper(
            paper_id="abc123",
            title="Transformer Models for Sentiment Analysis: A Survey",
            abstract="A survey of transformer models for sentiment analysis.",
            authors=["J. Smith", "A. Jones"],
            year=2023,
        )
        s2 = _mock_s2_client({
            "Transformer Models for Sentiment Analysis: A Survey": real_paper,
        })
        cr = _mock_crossref_client()
        oa = _mock_openalex_client()

        with patch("papercheck.layers.layer2_citations.SemanticScholarClient", return_value=s2), \
             patch("papercheck.layers.layer2_citations.CrossRefClient", return_value=cr), \
             patch("papercheck.layers.layer2_citations.OpenAlexClient", return_value=oa), \
             patch("papercheck.layers.layer2_citations._make_cache", return_value=None):
            result = await layer.verify(paper, config_no_llm)

        categories = [f.category for f in result.findings]
        assert "citation_not_found" in categories
        # At least one of the fake citations should be flagged
        not_found = [f for f in result.findings if f.category == "citation_not_found"]
        assert len(not_found) >= 1

    @pytest.mark.asyncio
    async def test_valid_citations_pass(self, layer, config_no_llm, sample_good_citations_tex):
        """All valid citations should be verified without errors."""
        paper = load_paper(str(sample_good_citations_tex))

        vaswani = S2Paper(
            paper_id="v123",
            title="Attention Is All You Need",
            abstract="We propose a new network architecture, the Transformer.",
            authors=["A. Vaswani"],
            year=2017,
        )
        bahdanau = S2Paper(
            paper_id="b456",
            title="Neural Machine Translation by Jointly Learning to Align and Translate",
            abstract="We conjecture that the use of a fixed-length vector is a bottleneck.",
            authors=["D. Bahdanau"],
            year=2015,
        )
        s2 = _mock_s2_client({
            "Attention Is All You Need": vaswani,
            "Neural Machine Translation by Jointly Learning to Align and Translate": bahdanau,
        })
        cr = _mock_crossref_client()
        oa = _mock_openalex_client()

        with patch("papercheck.layers.layer2_citations.SemanticScholarClient", return_value=s2), \
             patch("papercheck.layers.layer2_citations.CrossRefClient", return_value=cr), \
             patch("papercheck.layers.layer2_citations.OpenAlexClient", return_value=oa), \
             patch("papercheck.layers.layer2_citations._make_cache", return_value=None):
            result = await layer.verify(paper, config_no_llm)

        categories = [f.category for f in result.findings]
        assert "citation_not_found" not in categories

    @pytest.mark.asyncio
    async def test_crossref_fallback_works(self, layer, config_no_llm, sample_good_citations_tex):
        """If S2 fails, CrossRef should be used as fallback."""
        paper = load_paper(str(sample_good_citations_tex))

        # S2 finds nothing
        s2 = _mock_s2_client({})
        # CrossRef finds both papers
        cr = _mock_crossref_client({
            "Attention Is All You Need": {
                "title": "Attention Is All You Need",
                "authors": ["A. Vaswani"],
                "year": 2017,
                "doi": "10.5555/3295222.3295349",
            },
            "Neural Machine Translation by Jointly Learning to Align and Translate": {
                "title": "Neural Machine Translation by Jointly Learning to Align and Translate",
                "authors": ["D. Bahdanau"],
                "year": 2015,
                "doi": "10.48550/arXiv.1409.0473",
            },
        })
        oa = _mock_openalex_client()

        with patch("papercheck.layers.layer2_citations.SemanticScholarClient", return_value=s2), \
             patch("papercheck.layers.layer2_citations.CrossRefClient", return_value=cr), \
             patch("papercheck.layers.layer2_citations.OpenAlexClient", return_value=oa), \
             patch("papercheck.layers.layer2_citations._make_cache", return_value=None):
            result = await layer.verify(paper, config_no_llm)

        categories = [f.category for f in result.findings]
        assert "citation_not_found" not in categories

    @pytest.mark.asyncio
    async def test_hallucinated_citation_lowers_score(self, layer, config_no_llm, sample_hallucinated_cite_tex):
        """Hallucinated citations should lower the layer score."""
        paper = load_paper(str(sample_hallucinated_cite_tex))

        s2 = _mock_s2_client({})  # Nothing found
        cr = _mock_crossref_client()
        oa = _mock_openalex_client()

        with patch("papercheck.layers.layer2_citations.SemanticScholarClient", return_value=s2), \
             patch("papercheck.layers.layer2_citations.CrossRefClient", return_value=cr), \
             patch("papercheck.layers.layer2_citations.OpenAlexClient", return_value=oa), \
             patch("papercheck.layers.layer2_citations._make_cache", return_value=None):
            result = await layer.verify(paper, config_no_llm)

        assert result.score < 1.0


# ── Graceful degradation ───────────────────────────────────────────────────


class TestGracefulDegradation:
    @pytest.mark.asyncio
    async def test_no_llm_key_degrades_gracefully(self, layer, config_no_llm, sample_good_citations_tex):
        """Without an API key, LLM-based checks should be skipped with info findings."""
        paper = load_paper(str(sample_good_citations_tex))

        vaswani = S2Paper(
            paper_id="v123",
            title="Attention Is All You Need",
            abstract="We propose a new network architecture.",
            authors=["A. Vaswani"],
            year=2017,
        )
        s2 = _mock_s2_client({"Attention Is All You Need": vaswani})
        cr = _mock_crossref_client()
        oa = _mock_openalex_client()

        with patch("papercheck.layers.layer2_citations.SemanticScholarClient", return_value=s2), \
             patch("papercheck.layers.layer2_citations.CrossRefClient", return_value=cr), \
             patch("papercheck.layers.layer2_citations.OpenAlexClient", return_value=oa), \
             patch("papercheck.layers.layer2_citations._make_cache", return_value=None):
            result = await layer.verify(paper, config_no_llm)

        categories = [f.category for f in result.findings]
        assert "claim_alignment_skipped" in categories
        assert "coverage_check_skipped" in categories

    @pytest.mark.asyncio
    async def test_no_references_warns(self, layer, config_no_llm):
        """A paper with no references should produce a warning."""
        from papercheck.models import PaperData
        paper = PaperData(source_type="latex", raw_text="Hello world")

        with patch("papercheck.layers.layer2_citations._make_cache", return_value=None):
            result = await layer.verify(paper, config_no_llm)

        categories = [f.category for f in result.findings]
        assert "no_references" in categories


# ── Citation summary ───────────────────────────────────────────────────────


class TestCitationSummary:
    @pytest.mark.asyncio
    async def test_summary_finding_present(self, layer, config_no_llm, sample_good_citations_tex):
        """A summary info finding should always be present."""
        paper = load_paper(str(sample_good_citations_tex))

        vaswani = S2Paper(paper_id="v123", title="Attention Is All You Need", authors=["A. Vaswani"], year=2017)
        bahdanau = S2Paper(paper_id="b456", title="Neural Machine Translation by Jointly Learning to Align and Translate", authors=["D. Bahdanau"], year=2015)
        s2 = _mock_s2_client({
            "Attention Is All You Need": vaswani,
            "Neural Machine Translation by Jointly Learning to Align and Translate": bahdanau,
        })
        cr = _mock_crossref_client()
        oa = _mock_openalex_client()

        with patch("papercheck.layers.layer2_citations.SemanticScholarClient", return_value=s2), \
             patch("papercheck.layers.layer2_citations.CrossRefClient", return_value=cr), \
             patch("papercheck.layers.layer2_citations.OpenAlexClient", return_value=oa), \
             patch("papercheck.layers.layer2_citations._make_cache", return_value=None):
            result = await layer.verify(paper, config_no_llm)

        summary = [f for f in result.findings if f.category == "citation_summary"]
        assert len(summary) == 1
        assert "2/2" in summary[0].message


# ── Extractors ─────────────────────────────────────────────────────────────


class TestReferenceExtractor:
    def test_extracts_citation_contexts(self, sample_hallucinated_cite_tex):
        """Citation contexts should be extracted for each reference."""
        from papercheck.extractors.references import extract_citation_contexts

        paper = load_paper(str(sample_hallucinated_cite_tex))
        enriched = extract_citation_contexts(paper)

        assert len(enriched) >= 2
        # At least some references should have in-text contexts
        refs_with_contexts = [r for r in enriched if r.in_text_contexts]
        assert len(refs_with_contexts) >= 1

    def test_context_has_section_and_text(self, sample_good_citations_tex):
        """Each citation context should have section and surrounding text."""
        from papercheck.extractors.references import extract_citation_contexts

        paper = load_paper(str(sample_good_citations_tex))
        enriched = extract_citation_contexts(paper)

        for ref in enriched:
            for ctx in ref.in_text_contexts:
                assert ctx.section
                assert ctx.surrounding_text


# ── External client unit tests ─────────────────────────────────────────────


class TestSemanticScholarClient:
    def test_title_match_exact(self):
        from papercheck.external.semantic_scholar import _title_match
        assert _title_match("Attention Is All You Need", "attention is all you need")
        assert _title_match("Attention Is All You Need.", "attention is all you need")
        assert not _title_match("Something Else", "attention is all you need")

    def test_fuzzy_title_match(self):
        from papercheck.external.semantic_scholar import _fuzzy_title_match
        assert _fuzzy_title_match(
            "Attention Is All You Need",
            "attention is all you need"
        )
        assert not _fuzzy_title_match("Completely Different Title", "attention is all you need")

    def test_author_overlap(self):
        from papercheck.external.semantic_scholar import _author_overlap
        assert _author_overlap(["Ashish Vaswani", "Noam Shazeer"], ["Vaswani, A."])
        assert not _author_overlap(["John Smith"], ["Jane Doe"])


class TestCrossRefClient:
    def test_normalize_item(self):
        from papercheck.external.crossref import _normalize_item
        item = {
            "title": ["Test Paper"],
            "author": [{"given": "John", "family": "Doe"}],
            "published-print": {"date-parts": [[2023]]},
            "DOI": "10.1234/test",
            "container-title": ["Test Journal"],
            "type": "journal-article",
        }
        result = _normalize_item(item)
        assert result["title"] == "Test Paper"
        assert result["authors"] == ["John Doe"]
        assert result["year"] == 2023
        assert result["doi"] == "10.1234/test"

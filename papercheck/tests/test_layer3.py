"""Integration tests for Layer 3: Cross-Paper Consistency."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from papercheck.config import PipelineConfig
from papercheck.layers.layer3_corpus import CrossPaperConsistencyLayer
from papercheck.llm.schemas import ClaimExtractionResult, EmpiricalClaim
from papercheck.parsing.paper_loader import load_paper


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def layer():
    return CrossPaperConsistencyLayer()


@pytest.fixture
def config_no_llm():
    return PipelineConfig(anthropic_api_key="")


@pytest.fixture
def sample_clean_tex() -> Path:
    return FIXTURES_DIR / "sample_clean.tex"


# ── Claim extraction ───────────────────────────────────────────────────────


class TestClaimExtraction:
    @pytest.mark.asyncio
    async def test_no_api_key_skips_gracefully(self, layer, config_no_llm, sample_clean_tex):
        """Without API key, claim extraction should be skipped."""
        paper = load_paper(str(sample_clean_tex))
        result = await layer.verify(paper, config_no_llm)

        categories = [f.category for f in result.findings]
        assert "claim_extraction_skipped" in categories

    @pytest.mark.asyncio
    async def test_claims_extracted_with_mock_llm(self, layer, sample_clean_tex):
        """With a mocked LLM, claims should be extracted and reported."""
        paper = load_paper(str(sample_clean_tex))
        config = PipelineConfig(anthropic_api_key="test-key")

        mock_claims = ClaimExtractionResult(
            stated_contributions=["A clean paper structure for testing"],
            empirical_claims=[
                EmpiricalClaim(
                    claim_text="Our approach achieves consistent results",
                    claim_type="performance",
                    quantitative=False,
                ),
            ],
            framing_claims=["Verification is important"],
        )

        with patch("papercheck.layers.layer3_corpus.LLMClient") as MockLLM:
            mock_instance = MockLLM.return_value
            mock_instance.query = AsyncMock(return_value=mock_claims)

            with patch("papercheck.layers.layer3_corpus.extract_claims", new=AsyncMock(return_value=mock_claims)):
                result = await layer.verify(paper, config)

        categories = [f.category for f in result.findings]
        assert "claims_extracted" in categories
        # Should report 1 contribution and 1 empirical claim
        claims_finding = [f for f in result.findings if f.category == "claims_extracted"][0]
        assert "1 stated contributions" in claims_finding.message
        assert "1 empirical claims" in claims_finding.message

    @pytest.mark.asyncio
    async def test_corpus_search_skipped_without_deps(self, layer, sample_clean_tex):
        """Without chromadb/sentence-transformers, corpus search should be skipped."""
        paper = load_paper(str(sample_clean_tex))
        config = PipelineConfig(anthropic_api_key="test-key")

        mock_claims = ClaimExtractionResult(
            stated_contributions=["Test"],
            empirical_claims=[],
            framing_claims=[],
        )

        with patch("papercheck.layers.layer3_corpus.LLMClient"):
            with patch("papercheck.layers.layer3_corpus.extract_claims", new=AsyncMock(return_value=mock_claims)):
                with patch("papercheck.layers.layer3_corpus.HAS_CHROMADB", False):
                    result = await layer.verify(paper, config)

        categories = [f.category for f in result.findings]
        assert "corpus_search_skipped" in categories


# ── Internal consistency ───────────────────────────────────────────────────


class TestInternalConsistency:
    @pytest.mark.asyncio
    async def test_value_not_in_results_flagged(self, layer, sample_clean_tex):
        """If a claimed value doesn't appear in results, flag it."""
        paper = load_paper(str(sample_clean_tex))
        config = PipelineConfig(anthropic_api_key="test-key")

        mock_claims = ClaimExtractionResult(
            stated_contributions=["Test"],
            empirical_claims=[
                EmpiricalClaim(
                    claim_text="We achieve 99.9% accuracy",
                    claim_type="performance",
                    quantitative=True,
                    metric="accuracy",
                    value="99.9%",
                ),
            ],
            framing_claims=[],
        )

        with patch("papercheck.layers.layer3_corpus.LLMClient"):
            with patch("papercheck.layers.layer3_corpus.extract_claims", new=AsyncMock(return_value=mock_claims)):
                with patch("papercheck.layers.layer3_corpus.HAS_CHROMADB", False):
                    result = await layer.verify(paper, config)

        categories = [f.category for f in result.findings]
        assert "claim_value_not_in_results" in categories


# ── Score and signal ───────────────────────────────────────────────────────


class TestLayerOutput:
    @pytest.mark.asyncio
    async def test_layer_result_structure(self, layer, config_no_llm, sample_clean_tex):
        """Layer should return a valid LayerResult."""
        paper = load_paper(str(sample_clean_tex))
        result = await layer.verify(paper, config_no_llm)

        assert result.layer == 3
        assert result.layer_name == "Cross-Paper Consistency"
        assert 0.0 <= result.score <= 1.0
        assert result.signal in ("pass", "warn", "fail")
        assert result.execution_time_seconds > 0


# ── Claims extractor unit tests ────────────────────────────────────────────


class TestClaimsExtractor:
    @pytest.mark.asyncio
    async def test_no_abstract_returns_none(self):
        """extract_claims should return None if no abstract."""
        from papercheck.extractors.claims import extract_claims
        from papercheck.models import PaperData

        paper = PaperData(source_type="latex", raw_text="Hello")
        config = PipelineConfig(anthropic_api_key="test-key")

        with patch("papercheck.extractors.claims.LLMClient"):
            result = await extract_claims(paper, config)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_api_key_returns_none(self):
        """extract_claims should return None without API key."""
        from papercheck.extractors.claims import extract_claims
        from papercheck.models import PaperData

        paper = PaperData(source_type="latex", abstract="Test abstract", raw_text="Test")
        config = PipelineConfig(anthropic_api_key="")

        result = await extract_claims(paper, config)
        assert result is None

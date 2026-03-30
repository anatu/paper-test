"""Integration tests for Layer 1: Formal Consistency."""

from __future__ import annotations

from pathlib import Path

import pytest

from papercheck.config import PipelineConfig
from papercheck.layers.layer1_formal import FormalConsistencyLayer
from papercheck.parsing.paper_loader import load_paper


@pytest.fixture
def layer():
    return FormalConsistencyLayer()


@pytest.fixture
def config_no_llm():
    """Config without API key — LLM checks degrade gracefully."""
    return PipelineConfig(anthropic_api_key="")


class TestLayer1Integration:
    @pytest.mark.asyncio
    async def test_clean_paper_passes(self, layer, config_no_llm, sample_clean_tex: Path):
        paper = load_paper(str(sample_clean_tex))
        result = await layer.verify(paper, config_no_llm)
        assert result.score >= 0.7
        assert result.signal == "pass"

    @pytest.mark.asyncio
    async def test_statbug_paper_flagged(self, layer, config_no_llm, sample_statbug_tex: Path):
        paper = load_paper(str(sample_statbug_tex))
        result = await layer.verify(paper, config_no_llm)
        categories = [f.category for f in result.findings]
        # Should catch stat errors and/or impossible values
        assert "statistical_error" in categories or "impossible_value" in categories

    @pytest.mark.asyncio
    async def test_dangling_ref_flagged(self, layer, config_no_llm, sample_dangling_ref_tex: Path):
        paper = load_paper(str(sample_dangling_ref_tex))
        result = await layer.verify(paper, config_no_llm)
        categories = [f.category for f in result.findings]
        assert "dangling_reference" in categories

    @pytest.mark.asyncio
    async def test_dangling_ref_lowers_score(self, layer, config_no_llm, sample_dangling_ref_tex: Path):
        paper = load_paper(str(sample_dangling_ref_tex))
        result = await layer.verify(paper, config_no_llm)
        # Multiple dangling refs should lower the score
        assert result.score < 1.0

    @pytest.mark.asyncio
    async def test_no_llm_key_degrades_gracefully(self, layer, config_no_llm, sample_clean_tex: Path):
        paper = load_paper(str(sample_clean_tex))
        result = await layer.verify(paper, config_no_llm)
        # Should see a "skipped" info finding for claim alignment
        skipped = [f for f in result.findings if f.category == "claim_alignment_skipped"]
        assert len(skipped) == 1

"""Integration tests for Layer 5: Logical Structure."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from papercheck.config import PipelineConfig
from papercheck.layers.layer5_logic import LogicalStructureLayer
from papercheck.llm.schemas import (
    HypothesisExperimentResult,
    OverclaimFinding,
    ResultsConclusionResult,
)
from papercheck.parsing.paper_loader import load_paper


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def layer():
    return LogicalStructureLayer()


@pytest.fixture
def config_no_llm():
    return PipelineConfig(anthropic_api_key="")


@pytest.fixture
def config_with_llm():
    return PipelineConfig(anthropic_api_key="test-key")


@pytest.fixture
def sample_clean_tex() -> Path:
    return FIXTURES_DIR / "sample_clean.tex"


@pytest.fixture
def sample_weak_logic_tex() -> Path:
    return FIXTURES_DIR / "sample_weak_logic.tex"


# ── Graceful degradation ───────────────────────────────────────────────────


class TestGracefulDegradation:
    @pytest.mark.asyncio
    async def test_no_api_key_skips(self, layer, config_no_llm, sample_clean_tex):
        """Without API key, all checks should be skipped."""
        paper = load_paper(str(sample_clean_tex))
        result = await layer.verify(paper, config_no_llm)

        categories = [f.category for f in result.findings]
        assert "logic_check_skipped" in categories
        assert result.signal == "pass"


# ── Hypothesis-experiment alignment ────────────────────────────────────────


class TestHypothesisExperiment:
    @pytest.mark.asyncio
    async def test_strong_alignment_passes(self, layer, config_with_llm, sample_clean_tex):
        """Strong hypothesis-experiment alignment should produce info findings."""
        paper = load_paper(str(sample_clean_tex))

        mock_hyp_result = HypothesisExperimentResult(
            hypothesis="Testing framework achieves consistent results",
            experimental_elements=["composite scoring", "baseline comparison"],
            alignment="strong",
            gaps=[],
            explanation="Experiments directly test the stated hypothesis.",
        )
        mock_rc_result = ResultsConclusionResult(
            overclaimed=[],
            underdiscussed_negatives=[],
            overall="well_supported",
            explanation="Conclusions match the results.",
        )

        with patch("papercheck.layers.layer5_logic.LLMClient") as MockLLM:
            instance = MockLLM.return_value
            instance.query = AsyncMock(side_effect=[mock_hyp_result, mock_rc_result])
            result = await layer.verify(paper, config_with_llm)

        categories = [f.category for f in result.findings]
        assert "hypothesis_extracted" in categories
        assert "hypothesis_experiment_aligned" in categories
        assert "hypothesis_experiment_gap" not in categories

    @pytest.mark.asyncio
    async def test_weak_alignment_flagged(self, layer, config_with_llm, sample_weak_logic_tex):
        """Weak hypothesis-experiment alignment should produce warnings."""
        paper = load_paper(str(sample_weak_logic_tex))

        mock_hyp_result = HypothesisExperimentResult(
            hypothesis="RL can solve NP-hard problems in polynomial time",
            experimental_elements=["Q-learning", "sorting task"],
            alignment="misaligned",
            gaps=[
                "Sorting is not NP-hard",
                "Only tested on 10-element lists",
                "No comparison with classical algorithms",
            ],
            explanation="The experiment tests a trivial task, not NP-hard problems.",
        )
        mock_rc_result = ResultsConclusionResult(
            overclaimed=[
                OverclaimFinding(
                    conclusion_claim="RL can solve NP-hard problems",
                    strongest_supporting_result="100% accuracy on sorting 10 integers",
                    gap="Sorting is not NP-hard; no NP-hard problem was tested",
                ),
            ],
            underdiscussed_negatives=["Accuracy drops to 45% on lists of 100"],
            overall="significant_overclaiming",
            explanation="Conclusions far exceed what the results support.",
        )

        with patch("papercheck.layers.layer5_logic.LLMClient") as MockLLM:
            instance = MockLLM.return_value
            instance.query = AsyncMock(side_effect=[mock_hyp_result, mock_rc_result])
            result = await layer.verify(paper, config_with_llm)

        categories = [f.category for f in result.findings]
        assert "hypothesis_experiment_gap" in categories
        assert "experimental_gap" in categories
        assert "significant_overclaiming" in categories
        assert "overclaimed_conclusion" in categories
        assert "underdiscussed_negative" in categories
        # Should lower the score significantly
        assert result.score < 0.7

    @pytest.mark.asyncio
    async def test_missing_methods_skips_hypothesis_check(self, layer, config_with_llm):
        """If no methods section, hypothesis check should be skipped."""
        from papercheck.models import PaperData, Section
        paper = PaperData(
            source_type="latex",
            abstract="We propose a method.",
            sections=[
                Section(heading="Introduction", level=1, text="Some intro text"),
                Section(heading="Conclusion", level=1, text="We concluded things"),
            ],
            raw_text="We propose a method. We concluded things.",
        )

        mock_rc_result = ResultsConclusionResult(
            overclaimed=[],
            underdiscussed_negatives=[],
            overall="well_supported",
            explanation="OK",
        )

        with patch("papercheck.layers.layer5_logic.LLMClient") as MockLLM:
            instance = MockLLM.return_value
            instance.query = AsyncMock(return_value=mock_rc_result)
            result = await layer.verify(paper, config_with_llm)

        categories = [f.category for f in result.findings]
        assert "hypothesis_check_skipped" in categories


# ── Results-conclusion alignment ───────────────────────────────────────────


class TestResultsConclusion:
    @pytest.mark.asyncio
    async def test_well_supported_conclusions(self, layer, config_with_llm, sample_clean_tex):
        """Well-supported conclusions should not trigger warnings."""
        paper = load_paper(str(sample_clean_tex))

        mock_hyp_result = HypothesisExperimentResult(
            hypothesis="Testing works",
            experimental_elements=["scoring"],
            alignment="adequate",
            gaps=[],
            explanation="OK",
        )
        mock_rc_result = ResultsConclusionResult(
            overclaimed=[],
            underdiscussed_negatives=[],
            overall="well_supported",
            explanation="All conclusions are warranted by results.",
        )

        with patch("papercheck.layers.layer5_logic.LLMClient") as MockLLM:
            instance = MockLLM.return_value
            instance.query = AsyncMock(side_effect=[mock_hyp_result, mock_rc_result])
            result = await layer.verify(paper, config_with_llm)

        categories = [f.category for f in result.findings]
        assert "conclusions_well_supported" in categories
        assert "overclaimed_conclusion" not in categories

    @pytest.mark.asyncio
    async def test_missing_results_skips(self, layer, config_with_llm):
        """If no results section, results-conclusion check should be skipped."""
        from papercheck.models import PaperData, Section
        paper = PaperData(
            source_type="latex",
            abstract="Abstract text",
            sections=[
                Section(heading="Introduction", level=1, text="Intro"),
                Section(heading="Methodology", level=1, text="Methods here"),
                Section(heading="Conclusion", level=1, text="We conclude"),
            ],
            raw_text="Abstract text. Intro. Methods. Conclusion.",
        )

        mock_hyp_result = HypothesisExperimentResult(
            hypothesis="Something",
            experimental_elements=["test"],
            alignment="adequate",
            gaps=[],
            explanation="OK",
        )

        with patch("papercheck.layers.layer5_logic.LLMClient") as MockLLM:
            instance = MockLLM.return_value
            instance.query = AsyncMock(return_value=mock_hyp_result)
            result = await layer.verify(paper, config_with_llm)

        categories = [f.category for f in result.findings]
        assert "results_conclusion_skipped" in categories


# ── Layer output structure ─────────────────────────────────────────────────


class TestLayerOutput:
    @pytest.mark.asyncio
    async def test_layer_result_structure(self, layer, config_no_llm, sample_clean_tex):
        """Layer should return a valid LayerResult."""
        paper = load_paper(str(sample_clean_tex))
        result = await layer.verify(paper, config_no_llm)

        assert result.layer == 5
        assert result.layer_name == "Logical Structure"
        assert 0.0 <= result.score <= 1.0
        assert result.signal in ("pass", "warn", "fail")
        assert result.execution_time_seconds >= 0

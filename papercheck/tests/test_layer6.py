"""Integration tests for Layer 6: Peer-Review Reward Model."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from papercheck.config import PipelineConfig
from papercheck.layers.layer6_reward import RewardModelLayer
from papercheck.models import PaperData, Section
from papercheck.parsing.paper_loader import load_paper
from papercheck.reward_model.calibration import CalibratedScores


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def layer():
    return RewardModelLayer()


@pytest.fixture
def config():
    return PipelineConfig(anthropic_api_key="", reward_model_path="models/reward_model")


@pytest.fixture
def sample_clean_tex() -> Path:
    return FIXTURES_DIR / "sample_clean.tex"


class TestLayer6SkipBehavior:
    @pytest.mark.asyncio
    async def test_skips_when_no_model(self, layer, config, sample_clean_tex):
        """Should skip gracefully when no trained model exists."""
        paper = load_paper(str(sample_clean_tex))
        config.reward_model_path = "/nonexistent/path"

        result = await layer.verify(paper, config)

        assert result.skipped is True
        assert "No trained reward model" in result.skip_reason
        assert result.layer == 6
        assert result.layer_name == "Peer-Review Reward Model"

    @pytest.mark.asyncio
    async def test_layer_result_structure(self, layer, config, sample_clean_tex):
        """Layer should return a valid LayerResult."""
        paper = load_paper(str(sample_clean_tex))
        config.reward_model_path = "/nonexistent/path"

        result = await layer.verify(paper, config)

        assert result.layer == 6
        assert result.execution_time_seconds >= 0


class TestLayer6WithMockedModel:
    @pytest.mark.asyncio
    async def test_produces_score_findings(self, layer, config, sample_clean_tex, tmp_path):
        """With a mocked model, should produce per-dimension score findings."""
        paper = load_paper(str(sample_clean_tex))
        config.reward_model_path = str(tmp_path)

        # Create a fake checkpoint so model_exists returns True
        (tmp_path / "checkpoint_best.pt").write_bytes(b"dummy")

        mock_scores = CalibratedScores(
            overall_rating=0.65,
            overall_percentile=58.0,
            soundness=0.70,
            soundness_percentile=65.0,
            presentation=0.40,
            presentation_percentile=28.0,
            contribution=0.55,
            contribution_percentile=52.0,
            accept_probability=0.72,
        )

        # Mock the entire _load_model and prediction chain
        with patch.object(layer, "_load_model"), \
             patch.object(layer, "_inference") as mock_inf, \
             patch.object(layer, "_extractor") as mock_ext, \
             patch.object(layer, "_calibrator") as mock_cal:

            # Set up mock extractor
            mock_features = MagicMock()
            mock_ext.extract = MagicMock(return_value=mock_features)

            # Set up mock inference
            mock_preds = MagicMock()
            mock_preds.model_dump.return_value = {
                "overall": 0.65, "soundness": 0.70, "presentation": 0.40,
                "contribution": 0.55, "accept_prob": 0.72,
            }
            mock_inf.predict = MagicMock(return_value=mock_preds)

            # Set up mock calibrator
            mock_cal.calibrate = MagicMock(return_value=mock_scores)

            result = await layer.verify(paper, config)

        assert result.skipped is False
        categories = [f.category for f in result.findings]
        assert "predicted_score" in categories

        # Should have 5 score findings (one per dimension)
        score_findings = [f for f in result.findings if f.category == "predicted_score"]
        assert len(score_findings) == 5

    @pytest.mark.asyncio
    async def test_concern_only_for_low_dimensions(self, layer, config, sample_clean_tex, tmp_path):
        """Concerns should only be generated for dimensions below the threshold."""
        paper = load_paper(str(sample_clean_tex))
        config.reward_model_path = str(tmp_path)
        config.anthropic_api_key = "test-key"

        (tmp_path / "checkpoint_best.pt").write_bytes(b"dummy")

        # Presentation is low (28th pct), others are above threshold
        mock_scores = CalibratedScores(
            overall_rating=0.65,
            overall_percentile=58.0,
            soundness=0.70,
            soundness_percentile=65.0,
            presentation=0.40,
            presentation_percentile=28.0,
            contribution=0.55,
            contribution_percentile=52.0,
            accept_probability=0.72,
        )

        with patch.object(layer, "_load_model"), \
             patch.object(layer, "_inference") as mock_inf, \
             patch.object(layer, "_extractor") as mock_ext, \
             patch.object(layer, "_calibrator") as mock_cal, \
             patch("papercheck.reward_model.concern_generator.LLMClient") as MockLLM:

            mock_features = MagicMock()
            mock_ext.extract = MagicMock(return_value=mock_features)

            mock_preds = MagicMock()
            mock_preds.model_dump.return_value = {
                "overall": 0.65, "soundness": 0.70, "presentation": 0.40,
                "contribution": 0.55, "accept_prob": 0.72,
            }
            mock_inf.predict = MagicMock(return_value=mock_preds)
            mock_cal.calibrate = MagicMock(return_value=mock_scores)

            # Mock LLM to return anticipated concerns
            from papercheck.llm.schemas import AnticipatedConcerns, ReviewerConcern
            mock_concerns = AnticipatedConcerns(
                dimension="presentation",
                concerns=[
                    ReviewerConcern(
                        concern="Figures lack error bars",
                        location="Section 3",
                        suggestion="Add confidence intervals",
                        severity="moderate",
                    ),
                ],
            )
            mock_llm_instance = MockLLM.return_value
            mock_llm_instance.query = AsyncMock(return_value=mock_concerns)

            result = await layer.verify(paper, config)

        categories = [f.category for f in result.findings]
        # Should have concerns for presentation (low) but not others
        concern_findings = [f for f in result.findings if f.category == "anticipated_concern"]
        assert len(concern_findings) >= 1
        assert "presentation" in concern_findings[0].message.lower() or "Presentation" in concern_findings[0].message


class TestPipelineIntegration:
    @pytest.mark.asyncio
    async def test_full_pipeline_with_layer_6(self, sample_clean_tex):
        """Full pipeline run should include Layer 6 (skipped if no model)."""
        from papercheck.pipeline import run_pipeline

        paper = load_paper(str(sample_clean_tex))
        config = PipelineConfig(anthropic_api_key="", halt_on_fail=False)

        report = await run_pipeline(paper, config)

        assert len(report.layer_results) == 6
        layer_6_result = report.layer_results[-1]
        assert layer_6_result.layer == 6
        assert layer_6_result.skipped is True  # No model trained

    @pytest.mark.asyncio
    async def test_layer_selection_includes_6(self, sample_clean_tex):
        """Should be able to select Layer 6 specifically."""
        from papercheck.pipeline import run_pipeline

        paper = load_paper(str(sample_clean_tex))
        config = PipelineConfig(anthropic_api_key="")

        report = await run_pipeline(paper, config, layers=[6])

        assert len(report.layer_results) == 1
        assert report.layer_results[0].layer == 6

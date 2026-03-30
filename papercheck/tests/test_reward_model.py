"""Tests for the reward model components (model architecture, calibration, integration)."""

from __future__ import annotations

from pathlib import Path

import pytest

from papercheck.reward_model.calibration import CalibratedScores
from papercheck.reward_model.integration import (
    model_exists,
    scores_to_findings,
    scores_to_layer_score,
)


class TestIntegration:
    def test_scores_to_findings(self):
        """Should produce INFO findings for each score dimension."""
        scores = CalibratedScores(
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
        findings = scores_to_findings(scores)
        assert len(findings) == 5  # one per dimension
        assert all(f.category == "predicted_score" for f in findings)
        assert all(f.severity == "info" for f in findings)
        # Check percentile formatting
        overall_f = [f for f in findings if "Overall" in f.message][0]
        assert "58th percentile" in overall_f.message

    def test_scores_to_layer_score_pass(self):
        """Papers above 50th percentile should pass."""
        scores = CalibratedScores(overall_rating=0.65, overall_percentile=58.0)
        score, signal = scores_to_layer_score(scores)
        assert score == 0.65
        assert signal == "pass"

    def test_scores_to_layer_score_warn(self):
        """Papers between 25th-50th percentile should warn."""
        scores = CalibratedScores(overall_rating=0.40, overall_percentile=35.0)
        score, signal = scores_to_layer_score(scores)
        assert signal == "warn"

    def test_scores_to_layer_score_fail(self):
        """Papers below 25th percentile should fail."""
        scores = CalibratedScores(overall_rating=0.20, overall_percentile=15.0)
        score, signal = scores_to_layer_score(scores)
        assert signal == "fail"

    def test_model_exists_false(self, tmp_path):
        """model_exists should return False for empty directory."""
        assert model_exists(tmp_path) is False

    def test_model_exists_true(self, tmp_path):
        """model_exists should return True when checkpoint exists."""
        (tmp_path / "checkpoint_best.pt").write_bytes(b"dummy")
        assert model_exists(tmp_path) is True


class TestCalibratedScores:
    def test_default_values(self):
        """CalibratedScores should have sensible defaults."""
        scores = CalibratedScores()
        assert scores.overall_rating == 0.5
        assert scores.overall_percentile == 50.0
        assert scores.accept_probability == 0.5

    def test_all_dimensions(self):
        """Should store all five score dimensions."""
        scores = CalibratedScores(
            overall_rating=0.7,
            overall_percentile=70.0,
            soundness=0.8,
            soundness_percentile=80.0,
            presentation=0.6,
            presentation_percentile=60.0,
            contribution=0.5,
            contribution_percentile=50.0,
            accept_probability=0.75,
        )
        assert scores.overall_rating == 0.7
        assert scores.soundness == 0.8
        assert scores.presentation == 0.6
        assert scores.contribution == 0.5
        assert scores.accept_probability == 0.75

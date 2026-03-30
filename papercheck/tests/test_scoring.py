"""Tests for composite scoring."""

from __future__ import annotations

import pytest

from papercheck.models import LayerResult, Finding
from papercheck.scoring.composite import compute_composite_score


class TestCompositeScoring:
    def test_perfect_scores(self):
        results = [
            LayerResult(layer=1, layer_name="L1", score=1.0, signal="pass"),
            LayerResult(layer=2, layer_name="L2", score=1.0, signal="pass"),
        ]
        weights = {1: 0.5, 2: 0.5}
        score, signal = compute_composite_score(results, weights)
        assert score == 1.0
        assert signal == "pass"

    def test_skipped_layers_excluded(self):
        results = [
            LayerResult(layer=1, layer_name="L1", score=0.9, signal="pass"),
            LayerResult(layer=2, layer_name="L2", score=0.0, signal="fail", skipped=True),
        ]
        weights = {1: 0.5, 2: 0.5}
        score, signal = compute_composite_score(results, weights)
        assert score == 0.9
        assert signal == "pass"

    def test_weighted_average(self):
        results = [
            LayerResult(layer=1, layer_name="L1", score=1.0, signal="pass"),
            LayerResult(layer=2, layer_name="L2", score=0.0, signal="fail"),
        ]
        weights = {1: 0.75, 2: 0.25}
        score, signal = compute_composite_score(results, weights)
        assert score == 0.75
        assert signal == "pass"

    def test_fail_signal(self):
        results = [
            LayerResult(layer=1, layer_name="L1", score=0.1, signal="fail"),
        ]
        weights = {1: 1.0}
        score, signal = compute_composite_score(results, weights)
        assert score == 0.1
        assert signal == "fail"

    def test_warn_signal(self):
        results = [
            LayerResult(layer=1, layer_name="L1", score=0.45, signal="warn"),
        ]
        weights = {1: 1.0}
        score, signal = compute_composite_score(results, weights)
        assert signal == "warn"

    def test_empty_results(self):
        score, signal = compute_composite_score([], {})
        assert score == 1.0
        assert signal == "pass"

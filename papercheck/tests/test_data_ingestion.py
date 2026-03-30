"""Tests for OpenReview data ingestion."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from papercheck.reward_model.data_ingestion import (
    ReviewRecord,
    SubmissionRecord,
    VenueData,
    _extract_score,
    _extract_text,
)


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "mock_openreview"


class TestDataModels:
    def test_submission_record_creation(self):
        """SubmissionRecord should be creatable with basic fields."""
        record = SubmissionRecord(
            openreview_id="test123",
            title="Test Paper",
            abstract="An abstract",
            decision="Accept",
            venue="iclr",
            year=2024,
        )
        assert record.openreview_id == "test123"
        assert record.decision == "Accept"

    def test_review_record_defaults(self):
        """ReviewRecord should have sensible defaults for optional fields."""
        review = ReviewRecord(reviewer_id="r1", overall_rating=7.0)
        assert review.soundness is None
        assert review.confidence == 3.0

    def test_venue_data_from_fixture(self):
        """Should load sample data from fixture file."""
        data = json.loads((FIXTURES_DIR / "iclr2024_sample.json").read_text())
        papers = [SubmissionRecord(**p) for p in data]
        venue = VenueData(
            venue="iclr",
            year=2024,
            papers=papers,
            total_reviews=sum(len(p.reviews) for p in papers),
        )
        assert len(venue.papers) == 2
        assert venue.total_reviews == 6
        assert venue.papers[0].decision == "Accept"
        assert venue.papers[1].decision == "Reject"

    def test_fixture_reviews_complete(self):
        """All fixture papers should have >= 3 reviews."""
        data = json.loads((FIXTURES_DIR / "iclr2024_sample.json").read_text())
        for paper_data in data:
            paper = SubmissionRecord(**paper_data)
            assert len(paper.reviews) >= 3, f"{paper.title} has < 3 reviews"


class TestScoreExtraction:
    def test_extract_numeric_score(self):
        """Should extract numeric scores from dict."""
        scores = {"rating": 8, "confidence": 4}
        assert _extract_score(scores, ["rating"]) == 8.0

    def test_extract_string_score(self):
        """Should parse string scores like '8: Strong Accept'."""
        scores = {"rating": "8: Strong Accept"}
        assert _extract_score(scores, ["rating"]) == 8.0

    def test_extract_missing_score(self):
        """Should return None for missing scores."""
        scores = {"rating": 8}
        assert _extract_score(scores, ["soundness"]) is None

    def test_extract_with_fallback_fields(self):
        """Should try multiple field names."""
        scores = {"recommendation": 7}
        assert _extract_score(scores, ["rating", "recommendation"]) == 7.0

    def test_extract_text_field(self):
        """Should extract text fields."""
        scores = {"summary": "Good paper", "strengths": "Novel approach"}
        assert _extract_text(scores, "summary") == "Good paper"
        assert _extract_text(scores, "missing") == ""


class TestReviewRecord:
    def test_handles_missing_fields_gracefully(self):
        """ReviewRecord should handle None scores without crashing."""
        review = ReviewRecord(
            reviewer_id="r1",
            overall_rating=7.0,
            soundness=None,
            presentation=None,
            contribution=None,
        )
        assert review.soundness is None
        assert review.overall_rating == 7.0

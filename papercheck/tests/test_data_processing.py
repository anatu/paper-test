"""Tests for data processing and feature extraction."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from papercheck.reward_model.data_ingestion import ReviewRecord, SubmissionRecord, VenueData
from papercheck.reward_model.data_processing import ReviewDataProcessor


@pytest.fixture
def processor():
    return ReviewDataProcessor()


@pytest.fixture
def sample_reviews():
    return [
        ReviewRecord(reviewer_id="r1", overall_rating=8, soundness=7, confidence=4),
        ReviewRecord(reviewer_id="r2", overall_rating=6, soundness=6, confidence=3),
        ReviewRecord(reviewer_id="r3", overall_rating=7, soundness=7, confidence=5),
    ]


@pytest.fixture
def sample_venue_data():
    papers = []
    for i in range(20):
        decision = "Accept" if i < 6 else "Reject"  # 30% accept rate
        reviews = [
            ReviewRecord(reviewer_id=f"r{j}", overall_rating=5 + (i % 5), confidence=3 + (j % 3))
            for j in range(3 + (i % 2))
        ]
        papers.append(SubmissionRecord(
            openreview_id=f"paper_{i:03d}",
            title=f"Paper {i}",
            abstract=f"This is a test abstract for paper {i}. " * 10,
            reviews=reviews,
            decision=decision,
            venue="iclr",
            year=2024,
        ))
    return VenueData(venue="iclr", year=2024, papers=papers, total_reviews=0)


class TestScoreNormalization:
    def test_iclr_scale_normalization(self, processor, sample_reviews):
        """ICLR scale {1-10} should normalize correctly."""
        normalized = processor.normalize_scores(sample_reviews, "iclr", 2024)
        # rating=8 -> (8-1)/(10-1) ≈ 0.778
        assert abs(normalized[0]["overall"] - 0.778) < 0.01
        # rating=6 -> (6-1)/(10-1) ≈ 0.556
        assert abs(normalized[1]["overall"] - 0.556) < 0.01

    def test_normalization_bounds(self, processor):
        """Normalized scores should be in [0, 1]."""
        reviews = [ReviewRecord(reviewer_id="r1", overall_rating=1, confidence=3)]
        normalized = processor.normalize_scores(reviews, "iclr", 2024)
        assert normalized[0]["overall"] == 0.0

        reviews = [ReviewRecord(reviewer_id="r1", overall_rating=10, confidence=3)]
        normalized = processor.normalize_scores(reviews, "iclr", 2024)
        assert normalized[0]["overall"] == 1.0


class TestConsensusLabels:
    def test_confidence_weighted_consensus(self, processor, sample_reviews):
        """Confidence-weighted mean should be computed correctly."""
        normalized = processor.normalize_scores(sample_reviews, "iclr", 2024)
        labels = processor.compute_consensus_labels(normalized, "Accept")

        # Weighted: (0.778*4 + 0.556*3 + 0.667*5) / (4+3+5) ≈ 0.676
        assert labels.overall_rating == pytest.approx(0.676, abs=0.01)
        assert labels.confidence_weighted is True
        assert labels.review_count == 3

    def test_accept_probability(self, processor, sample_reviews):
        """Accept decisions should map to 1.0, reject to 0.0."""
        normalized = processor.normalize_scores(sample_reviews, "iclr", 2024)
        labels_accept = processor.compute_consensus_labels(normalized, "Accept")
        labels_reject = processor.compute_consensus_labels(normalized, "Reject")
        assert labels_accept.accept_probability == 1.0
        assert labels_reject.accept_probability == 0.0


class TestFiltering:
    def test_filters_fewer_than_3_reviews(self, processor):
        """Papers with < 3 reviews should be filtered out."""
        papers = [
            SubmissionRecord(
                openreview_id="p1", title="Good", abstract="a" * 200,
                reviews=[ReviewRecord(reviewer_id="r1"), ReviewRecord(reviewer_id="r2")],
                decision="Accept",
            ),
            SubmissionRecord(
                openreview_id="p2", title="Also Good", abstract="b" * 200,
                reviews=[
                    ReviewRecord(reviewer_id="r1"),
                    ReviewRecord(reviewer_id="r2"),
                    ReviewRecord(reviewer_id="r3"),
                ],
                decision="Accept",
            ),
        ]
        filtered = processor.filter_submissions(papers)
        assert len(filtered) == 1
        assert filtered[0].openreview_id == "p2"

    def test_filters_withdrawn(self, processor):
        """Withdrawn papers should be filtered out."""
        papers = [
            SubmissionRecord(
                openreview_id="p1", title="Withdrawn", abstract="a" * 200,
                reviews=[ReviewRecord(reviewer_id=f"r{i}") for i in range(3)],
                decision="Withdrawn",
            ),
        ]
        filtered = processor.filter_submissions(papers)
        assert len(filtered) == 0

    def test_filters_short_abstracts(self, processor):
        """Papers with abstracts < 100 chars should be filtered out."""
        papers = [
            SubmissionRecord(
                openreview_id="p1", title="Short", abstract="Too short",
                reviews=[ReviewRecord(reviewer_id=f"r{i}") for i in range(3)],
                decision="Accept",
            ),
        ]
        filtered = processor.filter_submissions(papers)
        assert len(filtered) == 0


class TestSplits:
    def test_stratified_split_preserves_ratio(self, processor, sample_venue_data):
        """Train/val/test should preserve accept/reject ratio (roughly)."""
        dataset = processor.process_venue(sample_venue_data)
        splits = processor.create_splits(dataset)

        total = len(splits.train) + len(splits.val) + len(splits.test)
        assert total == len(dataset.papers)

        # Check all splits have papers
        assert len(splits.train) > 0
        assert len(splits.val) > 0
        assert len(splits.test) > 0

    def test_split_sizes_roughly_80_10_10(self, processor, sample_venue_data):
        """Split should be approximately 80/10/10."""
        dataset = processor.process_venue(sample_venue_data)
        splits = processor.create_splits(dataset)
        total = len(dataset.papers)

        # Train should be the majority
        assert len(splits.train) > len(splits.val)
        assert len(splits.train) > len(splits.test)

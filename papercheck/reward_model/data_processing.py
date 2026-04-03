"""Transform raw OpenReview data into training-ready format."""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path

from pydantic import BaseModel, Field

from papercheck.reward_model.data_ingestion import (
    ReviewRecord,
    SubmissionRecord,
    VenueData,
)

logger = logging.getLogger(__name__)


# ── Data models ────────────────────────────────────────────────────────────


class ConsensusLabels(BaseModel):
    """Aggregated review scores for one paper."""

    overall_rating: float = 0.5
    soundness: float | None = None
    presentation: float | None = None
    contribution: float | None = None
    accept_probability: float = 0.5
    reviewer_variance: dict[str, float] = Field(default_factory=dict)
    review_count: int = 0
    confidence_weighted: bool = True


class ProcessedPaper(BaseModel):
    """A paper ready for feature extraction."""

    openreview_id: str
    title: str = ""
    abstract: str = ""
    full_text: str | None = None
    sections: dict[str, str] | None = None
    labels: ConsensusLabels = Field(default_factory=ConsensusLabels)
    venue: str = ""
    year: int = 0
    decision: str = ""


class ProcessedDataset(BaseModel):
    """Full processed dataset."""

    papers: list[ProcessedPaper] = Field(default_factory=list)
    venue: str = ""
    years: list[int] = Field(default_factory=list)


class TrainValTestSplit(BaseModel):
    """Dataset splits."""

    train: list[ProcessedPaper] = Field(default_factory=list)
    val: list[ProcessedPaper] = Field(default_factory=list)
    test: list[ProcessedPaper] = Field(default_factory=list)


# ── Score scale ranges per venue ───────────────────────────────────────────

_VENUE_SCALES = {
    "iclr": {"min": 1, "max": 10},
    "neurips": {"min": 1, "max": 10},
}


# ── Processor ──────────────────────────────────────────────────────────────


class ReviewDataProcessor:
    """Transforms raw OpenReview data into training-ready format."""

    def process_venue(self, venue_data: VenueData) -> ProcessedDataset:
        """Full processing pipeline for one venue-year."""
        filtered = self.filter_submissions(venue_data.papers)
        papers = []
        for sub in filtered:
            normalized = self.normalize_scores(sub.reviews, venue_data.venue, venue_data.year)
            labels = self.compute_consensus_labels(normalized, sub.decision)
            papers.append(ProcessedPaper(
                openreview_id=sub.openreview_id,
                title=sub.title,
                abstract=sub.abstract,
                full_text=sub.full_text,
                labels=labels,
                venue=venue_data.venue,
                year=venue_data.year,
                decision=sub.decision,
            ))
        return ProcessedDataset(
            papers=papers,
            venue=venue_data.venue,
            years=[venue_data.year],
        )

    def filter_submissions(
        self, papers: list[SubmissionRecord]
    ) -> list[SubmissionRecord]:
        """Remove papers that don't meet quality criteria."""
        filtered = []
        for p in papers:
            if len(p.reviews) < 3:
                continue
            if p.decision == "Withdrawn":
                continue
            if len(p.abstract) < 100:
                continue
            filtered.append(p)

        # Remove top/bottom 1% by abstract length
        if len(filtered) > 100:
            lengths = sorted(len(p.abstract) for p in filtered)
            low = lengths[len(lengths) // 100]
            high = lengths[-len(lengths) // 100]
            filtered = [p for p in filtered if low <= len(p.abstract) <= high]

        return filtered

    def normalize_scores(
        self, reviews: list[ReviewRecord], venue: str, year: int
    ) -> list[dict]:
        """Normalize venue-specific scores to 0-1 range."""
        scale = _VENUE_SCALES.get(venue, {"min": 1, "max": 10})
        s_min, s_max = scale["min"], scale["max"]
        rng = s_max - s_min
        if rng == 0:
            rng = 1

        normalized = []
        for r in reviews:
            norm = {
                "overall": _normalize(r.overall_rating, s_min, rng),
                "soundness": _normalize(r.soundness, s_min, rng),
                "presentation": _normalize(r.presentation, s_min, rng),
                "contribution": _normalize(r.contribution, s_min, rng),
                "confidence": r.confidence,
            }
            normalized.append(norm)
        return normalized

    def compute_consensus_labels(
        self, normalized_reviews: list[dict], decision: str
    ) -> ConsensusLabels:
        """Compute confidence-weighted consensus scores."""
        if not normalized_reviews:
            return ConsensusLabels()

        dims = ["overall", "soundness", "presentation", "contribution"]
        results: dict[str, float | None] = {}
        variance: dict[str, float] = {}

        for dim in dims:
            scores = []
            confidences = []
            for r in normalized_reviews:
                s = r.get(dim)
                c = r.get("confidence", 3.0) or 3.0
                if s is not None:
                    scores.append(s)
                    confidences.append(c)

            if not scores:
                results[dim] = None
                continue

            total_conf = sum(confidences)
            if total_conf > 0:
                weighted_mean = sum(s * c for s, c in zip(scores, confidences)) / total_conf
            else:
                weighted_mean = sum(scores) / len(scores)

            results[dim] = weighted_mean
            if len(scores) > 1:
                mean = sum(scores) / len(scores)
                variance[dim] = sum((s - mean) ** 2 for s in scores) / len(scores)

        accept_prob = 1.0 if decision == "Accept" else 0.0

        return ConsensusLabels(
            overall_rating=results["overall"] or 0.5,
            soundness=results["soundness"],
            presentation=results["presentation"],
            contribution=results["contribution"],
            accept_probability=accept_prob,
            reviewer_variance=variance,
            review_count=len(normalized_reviews),
            confidence_weighted=True,
        )

    def create_splits(
        self, dataset: ProcessedDataset, seed: int = 42
    ) -> TrainValTestSplit:
        """80/10/10 stratified split by decision and year."""
        rng = random.Random(seed)
        papers = list(dataset.papers)
        rng.shuffle(papers)

        # Stratify by decision
        accepted = [p for p in papers if p.decision == "Accept"]
        rejected = [p for p in papers if p.decision != "Accept"]

        def split_list(lst):
            n = len(lst)
            n_val = max(1, n // 10)
            n_test = max(1, n // 10)
            return lst[:n - n_val - n_test], lst[n - n_val - n_test:n - n_test], lst[n - n_test:]

        a_train, a_val, a_test = split_list(accepted)
        r_train, r_val, r_test = split_list(rejected)

        return TrainValTestSplit(
            train=a_train + r_train,
            val=a_val + r_val,
            test=a_test + r_test,
        )

    def save_processed(self, dataset: ProcessedDataset, output_dir: Path) -> None:
        """Save processed dataset to disk as all.jsonl."""
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_jsonl(output_dir / "all.jsonl", dataset.papers)
        logger.info("Saved %d papers to %s/all.jsonl", len(dataset.papers), output_dir)

    def save_splits(self, splits: TrainValTestSplit, output_dir: Path) -> None:
        """Save train/val/test splits to disk."""
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_jsonl(output_dir / "train.jsonl", splits.train)
        _write_jsonl(output_dir / "val.jsonl", splits.val)
        _write_jsonl(output_dir / "test.jsonl", splits.test)
        logger.info(
            "Saved splits: train=%d, val=%d, test=%d to %s",
            len(splits.train), len(splits.val), len(splits.test), output_dir,
        )


def load_processed_dataset(data_dir: Path) -> ProcessedDataset:
    """Load a processed dataset from all.jsonl."""
    all_path = data_dir / "all.jsonl"
    if not all_path.exists():
        raise FileNotFoundError(f"No processed dataset at {all_path}")
    papers = _read_jsonl(all_path)
    return ProcessedDataset(papers=papers)


def load_splits(data_dir: Path) -> TrainValTestSplit:
    """Load train/val/test splits from JSONL files."""
    train_path = data_dir / "train.jsonl"
    val_path = data_dir / "val.jsonl"
    test_path = data_dir / "test.jsonl"
    if not train_path.exists():
        raise FileNotFoundError(f"No splits found at {data_dir} (missing train.jsonl)")
    return TrainValTestSplit(
        train=_read_jsonl(train_path),
        val=_read_jsonl(val_path),
        test=_read_jsonl(test_path),
    )


def load_venue_data_from_disk(data_dir: Path, venue: str, year: int) -> VenueData:
    """Load fetched VenueData from cached paper files on disk."""
    venue_dir = data_dir / f"{venue}_{year}" / "papers"
    if not venue_dir.exists():
        raise FileNotFoundError(f"No fetched data at {venue_dir}")
    papers = []
    for f in sorted(venue_dir.glob("*.json")):
        papers.append(SubmissionRecord.model_validate_json(f.read_text()))
    total_reviews = sum(len(p.reviews) for p in papers)
    return VenueData(venue=venue, year=year, papers=papers, total_reviews=total_reviews)


def _write_jsonl(path: Path, papers: list[ProcessedPaper]) -> None:
    with open(path, "w") as f:
        for p in papers:
            f.write(p.model_dump_json() + "\n")


def _read_jsonl(path: Path) -> list[ProcessedPaper]:
    papers = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                papers.append(ProcessedPaper.model_validate_json(line))
    return papers


def _normalize(val: float | None, s_min: float, rng: float) -> float | None:
    if val is None:
        return None
    return max(0.0, min(1.0, (val - s_min) / rng))

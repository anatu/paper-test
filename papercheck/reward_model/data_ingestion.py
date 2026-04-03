"""OpenReview API scraper — downloads submissions and reviews."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Optional import — degrades gracefully
try:
    import openreview

    HAS_OPENREVIEW = True
except ImportError:
    HAS_OPENREVIEW = False


# ── Data models ────────────────────────────────────────────────────────────


class ReviewRecord(BaseModel):
    """A single peer review."""

    reviewer_id: str = ""
    overall_rating: float | None = None
    soundness: float | None = None
    presentation: float | None = None
    contribution: float | None = None
    confidence: float = 3.0
    summary: str = ""
    strengths: str = ""
    weaknesses: str = ""
    questions: str = ""
    raw_scores: dict[str, Any] = Field(default_factory=dict)


class SubmissionRecord(BaseModel):
    """A single paper submission with its reviews."""

    openreview_id: str
    title: str = ""
    authors: list[str] = Field(default_factory=list)
    abstract: str = ""
    full_text: str | None = None
    pdf_url: str | None = None
    reviews: list[ReviewRecord] = Field(default_factory=list)
    decision: str = ""  # "Accept", "Reject", "Withdrawn"
    venue: str = ""
    year: int = 0


class VenueData(BaseModel):
    """All submissions for a venue-year."""

    venue: str
    year: int
    papers: list[SubmissionRecord] = Field(default_factory=list)
    total_reviews: int = 0


# ── Score field mappings per venue ─────────────────────────────────────────

# ICLR field names vary by year
_ICLR_SCORE_FIELDS = {
    "overall": ["rating", "recommendation", "overall_assessment", "overall"],
    "soundness": ["soundness"],
    "presentation": ["presentation"],
    "contribution": ["contribution", "significance"],
    "confidence": ["confidence"],
}


# ── OpenReview scraper ─────────────────────────────────────────────────────


class OpenReviewScraper:
    """Downloads submissions and reviews from OpenReview API v2."""

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        cache_dir: Path | None = None,
    ):
        if not HAS_OPENREVIEW:
            raise ImportError(
                "openreview-py is required: pip install openreview-py"
            )
        if not username or not password:
            raise ValueError(
                "OpenReview credentials required. Set OPENREVIEW_USERNAME and "
                "OPENREVIEW_PASSWORD in your .env file (free account at openreview.net)."
            )
        self._client = openreview.api.OpenReviewClient(
            baseurl="https://api2.openreview.net",
            username=username,
            password=password,
        )
        self._cache_dir = cache_dir
        self._request_delay = 1.0  # 1 req/sec rate limit

    def fetch_venue(self, venue: str, year: int) -> VenueData:
        """Download all submissions + reviews for a venue-year.

        Supports resume via manifest.json. Tries multiple invitation
        formats since OpenReview changed naming conventions over time.
        """
        manifest = self._load_manifest(venue, year)
        already_fetched = set(manifest.get("fetched_ids", []))

        submissions = None
        for invitation in self._submission_invitations(venue, year):
            logger.info("Trying invitation: %s", invitation)
            try:
                submissions = self._client.get_all_notes(invitation=invitation)
                if submissions:
                    logger.info("Found %d submissions via %s", len(submissions), invitation)
                    break
            except Exception as e:
                logger.debug("Invitation %s failed: %s", invitation, e)
                continue

        if not submissions:
            raise RuntimeError(
                f"Could not fetch submissions for {venue} {year}. "
                f"Check your credentials and that the venue/year exists on OpenReview."
            )

        papers: list[SubmissionRecord] = []
        total_reviews = 0

        for i, note in enumerate(submissions):
            note_id = note.id
            if note_id in already_fetched:
                # Load from cache
                cached = self._load_cached_paper(venue, year, note_id)
                if cached:
                    papers.append(cached)
                    total_reviews += len(cached.reviews)
                    continue

            # Fetch reviews and decision
            # note.number is the submission number used in invitation strings
            sub_number = getattr(note, "number", None)
            time.sleep(self._request_delay)
            reviews = self._get_reviews(note_id, venue, year, sub_number)
            time.sleep(self._request_delay)
            decision = self._get_decision(note_id, venue, year, sub_number)

            content = note.content or {}
            record = SubmissionRecord(
                openreview_id=note_id,
                title=_extract_field(content, "title"),
                authors=_extract_list(content, "authors"),
                abstract=_extract_field(content, "abstract"),
                pdf_url=_extract_field(content, "pdf"),
                reviews=reviews,
                decision=decision,
                venue=venue,
                year=year,
            )
            papers.append(record)
            total_reviews += len(reviews)

            # Cache and update manifest
            self._cache_paper(venue, year, record)
            already_fetched.add(note_id)
            self._save_manifest(venue, year, list(already_fetched))

            if (i + 1) % 50 == 0:
                logger.info("Progress: %d/%d papers fetched", i + 1, len(submissions))

        return VenueData(
            venue=venue,
            year=year,
            papers=papers,
            total_reviews=total_reviews,
        )

    def _get_reviews(self, note_id: str, venue: str, year: int, sub_number: int | None = None) -> list[ReviewRecord]:
        """Get all official reviews for a submission."""
        notes = None
        for invitation in self._review_invitations(venue, year, sub_number):
            try:
                notes = self._client.get_all_notes(forum=note_id, invitation=invitation)
                if notes:
                    break
            except Exception:
                continue
        if not notes:
            logger.warning("No reviews found for %s", note_id)
            return []

        reviews = []
        for note in notes:
            content = note.content or {}
            raw_scores = {}
            for key, val in content.items():
                if isinstance(val, dict) and "value" in val:
                    raw_scores[key] = val["value"]
                elif not isinstance(val, dict):
                    raw_scores[key] = val

            reviews.append(ReviewRecord(
                reviewer_id=note.signatures[0] if note.signatures else "",
                overall_rating=_extract_score(raw_scores, _ICLR_SCORE_FIELDS["overall"]),
                soundness=_extract_score(raw_scores, _ICLR_SCORE_FIELDS["soundness"]),
                presentation=_extract_score(raw_scores, _ICLR_SCORE_FIELDS["presentation"]),
                contribution=_extract_score(raw_scores, _ICLR_SCORE_FIELDS["contribution"]),
                confidence=_extract_score(raw_scores, _ICLR_SCORE_FIELDS["confidence"]) or 3.0,
                summary=_extract_text(raw_scores, "summary"),
                strengths=_extract_text(raw_scores, "strengths"),
                weaknesses=_extract_text(raw_scores, "weaknesses"),
                questions=_extract_text(raw_scores, "questions"),
                raw_scores=raw_scores,
            ))
        return reviews

    def _get_decision(self, note_id: str, venue: str, year: int, sub_number: int | None = None) -> str:
        """Get accept/reject decision for a submission."""
        notes = None
        for invitation in self._decision_invitations(venue, year, sub_number):
            try:
                notes = self._client.get_all_notes(forum=note_id, invitation=invitation)
                if notes:
                    break
            except Exception:
                continue
        if not notes:
            return ""
        content = notes[0].content or {}
        decision = _extract_field(content, "decision")
        if "accept" in decision.lower():
            return "Accept"
        elif "reject" in decision.lower():
            return "Reject"
        elif "withdraw" in decision.lower():
            return "Withdrawn"
        return decision

    def _submission_invitations(self, venue: str, year: int) -> list[str]:
        """Return candidate invitation strings, newest format first."""
        v = venue.upper()
        if venue == "iclr":
            return [
                f"ICLR.cc/{year}/Conference/-/Submission",
                f"ICLR.cc/{year}/Conference/-/Blind_Submission",
            ]
        elif venue == "neurips":
            return [
                f"NeurIPS.cc/{year}/Conference/-/Submission",
                f"NeurIPS.cc/{year}/Conference/-/Blind_Submission",
            ]
        return [f"{v}/{year}/-/Submission", f"{v}/{year}/-/Blind_Submission"]

    def _review_invitations(self, venue: str, year: int, sub_number: int | None = None) -> list[str]:
        """Build review invitation strings. Uses exact submission number when available."""
        prefix = self._venue_prefix(venue)
        invitations = []
        if sub_number is not None:
            # Exact match — this is what the API actually requires
            invitations.append(f"{prefix}/{year}/Conference/Submission{sub_number}/-/Official_Review")
            invitations.append(f"{prefix}/{year}/Conference/Paper{sub_number}/-/Official_Review")
        # Wildcard fallback (may not work on newer API)
        invitations.append(f"{prefix}/{year}/Conference/Submission.*/-/Official_Review")
        invitations.append(f"{prefix}/{year}/Conference/Paper.*/-/Official_Review")
        return invitations

    def _decision_invitations(self, venue: str, year: int, sub_number: int | None = None) -> list[str]:
        """Build decision invitation strings. Uses exact submission number when available."""
        prefix = self._venue_prefix(venue)
        invitations = []
        if sub_number is not None:
            invitations.append(f"{prefix}/{year}/Conference/Submission{sub_number}/-/Decision")
            invitations.append(f"{prefix}/{year}/Conference/Paper{sub_number}/-/Decision")
        invitations.append(f"{prefix}/{year}/Conference/Submission.*/-/Decision")
        invitations.append(f"{prefix}/{year}/Conference/Paper.*/-/Decision")
        return invitations

    def _venue_prefix(self, venue: str) -> str:
        return {"iclr": "ICLR.cc", "neurips": "NeurIPS.cc"}.get(venue, venue.upper())

    # ── Caching / manifest ────────────────────────────────────────────────

    def _load_manifest(self, venue: str, year: int) -> dict:
        if not self._cache_dir:
            return {}
        path = self._cache_dir / f"{venue}_{year}" / "manifest.json"
        if path.exists():
            return json.loads(path.read_text())
        return {}

    def _save_manifest(self, venue: str, year: int, fetched_ids: list[str]) -> None:
        if not self._cache_dir:
            return
        d = self._cache_dir / f"{venue}_{year}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "manifest.json").write_text(json.dumps({"fetched_ids": fetched_ids}))

    def _cache_paper(self, venue: str, year: int, record: SubmissionRecord) -> None:
        if not self._cache_dir:
            return
        d = self._cache_dir / f"{venue}_{year}" / "papers"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{record.openreview_id}.json").write_text(record.model_dump_json())

    def _load_cached_paper(self, venue: str, year: int, note_id: str) -> SubmissionRecord | None:
        if not self._cache_dir:
            return None
        path = self._cache_dir / f"{venue}_{year}" / "papers" / f"{note_id}.json"
        if path.exists():
            return SubmissionRecord.model_validate_json(path.read_text())
        return None


# ── Helpers ────────────────────────────────────────────────────────────────


def _extract_field(content: dict, key: str) -> str:
    """Extract a text field from OpenReview note content."""
    val = content.get(key, "")
    if isinstance(val, dict):
        val = val.get("value", "")
    if isinstance(val, list):
        return str(val)  # Caller should use _extract_list for list fields
    return str(val) if val else ""


def _extract_list(content: dict, key: str) -> list:
    """Extract a list field from OpenReview note content (e.g. authors)."""
    val = content.get(key, [])
    if isinstance(val, dict):
        val = val.get("value", [])
    if isinstance(val, list):
        return val
    return [str(val)] if val else []


def _extract_score(scores: dict, field_names: list[str]) -> float | None:
    """Extract a numeric score, trying multiple field names.

    Handles formats like: 8, "8: Strong Accept", "2 fair", "3: reject, not good enough"
    """
    for name in field_names:
        val = scores.get(name)
        if val is None:
            continue
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            # Try splitting on ":" first ("8: Strong Accept")
            # then on space ("2 fair"), then leading digits
            for sep in [":", " "]:
                try:
                    return float(val.split(sep)[0].strip())
                except (ValueError, TypeError):
                    continue
    return None


def _extract_text(scores: dict, key: str) -> str:
    """Extract a text field from review scores."""
    val = scores.get(key, "")
    return str(val) if val else ""

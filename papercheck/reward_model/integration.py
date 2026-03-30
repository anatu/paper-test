"""Adapter: reward model -> VerificationLayer findings."""

from __future__ import annotations

import logging
from pathlib import Path

from papercheck.models import Finding, PaperData
from papercheck.reward_model.calibration import CalibratedScores

logger = logging.getLogger(__name__)

DIMENSIONS = [
    ("overall_rating", "overall_percentile", "Overall"),
    ("soundness", "soundness_percentile", "Soundness"),
    ("presentation", "presentation_percentile", "Presentation"),
    ("contribution", "contribution_percentile", "Contribution"),
    ("accept_probability", None, "Accept Probability"),
]


def scores_to_findings(scores: CalibratedScores) -> list[Finding]:
    """Convert calibrated scores to INFO findings for the report."""
    findings: list[Finding] = []

    for score_attr, pct_attr, label in DIMENSIONS:
        score_val = getattr(scores, score_attr, None)
        if score_val is None:
            continue
        pct_val = getattr(scores, pct_attr) if pct_attr else None
        pct_str = f" ({pct_val:.0f}th percentile)" if pct_val is not None else ""

        findings.append(Finding(
            severity="info",
            category="predicted_score",
            message=f"Predicted {label}: {score_val:.2f}{pct_str}",
        ))

    return findings


def scores_to_layer_score(scores: CalibratedScores) -> tuple[float, str]:
    """Convert calibrated scores to layer (score, signal).

    Score = calibrated overall_rating (0-1).
    Signal: pass if >= 50th percentile, warn if >= 25th, fail if < 25th.
    """
    score = scores.overall_rating
    pct = scores.overall_percentile

    if pct >= 50:
        signal = "pass"
    elif pct >= 25:
        signal = "warn"
    else:
        signal = "fail"

    return score, signal


def model_exists(model_dir: Path) -> bool:
    """Check if a trained model checkpoint exists."""
    return (model_dir / "checkpoint_best.pt").exists()

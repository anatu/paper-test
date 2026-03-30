"""Composite scoring and report assembly."""

from __future__ import annotations

from datetime import datetime, timezone

from papercheck import __version__
from papercheck.config import PipelineConfig
from papercheck.models import DiagnosticReport, LayerResult, PaperData


def compute_composite_score(
    layer_results: list[LayerResult],
    weights: dict[int, float],
) -> tuple[float, str]:
    """Weighted average of layer scores, excluding skipped layers.

    Re-normalizes weights after excluding skipped layers.
    Returns (composite_score, composite_signal).
    """
    active = [(r, weights.get(r.layer, 0.0)) for r in layer_results if not r.skipped]
    if not active:
        return 1.0, "pass"

    total_weight = sum(w for _, w in active)
    if total_weight == 0:
        return 1.0, "pass"

    score = sum(r.score * w for r, w in active) / total_weight

    if score >= 0.6:
        signal = "pass"
    elif score >= 0.3:
        signal = "warn"
    else:
        signal = "fail"

    return round(score, 4), signal


def generate_report(
    paper: PaperData,
    layer_results: list[LayerResult],
    config: PipelineConfig,
    total_time: float,
    llm_cost: float = 0.0,
) -> DiagnosticReport:
    """Assemble a complete DiagnosticReport."""
    composite_score, composite_signal = compute_composite_score(
        layer_results, config.layer_weights
    )

    return DiagnosticReport(
        paper=paper.metadata,
        title=paper.title,
        authors=paper.authors,
        layer_results=layer_results,
        composite_score=composite_score,
        composite_signal=composite_signal,
        scoring_weights=config.layer_weights,
        timestamp=datetime.now(timezone.utc).isoformat(),
        pipeline_version=__version__,
        total_execution_time_seconds=round(total_time, 6),
        total_llm_cost_usd=llm_cost,
    )

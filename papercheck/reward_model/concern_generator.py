"""LLM-based anticipated reviewer concern generation."""

from __future__ import annotations

import logging

from papercheck.config import PipelineConfig
from papercheck.extractors.metadata import (
    get_abstract,
    get_conclusion,
    get_introduction,
    get_methods,
    get_results,
)
from papercheck.llm.client import LLMClient, LLMParseError
from papercheck.models import Finding, PaperData
from papercheck.reward_model.calibration import CalibratedScores

logger = logging.getLogger(__name__)

# Map dimensions to relevant sections
_DIMENSION_SECTIONS = {
    "soundness": ["methods", "results"],
    "presentation": ["abstract", "introduction", "methods", "results", "conclusion"],
    "contribution": ["introduction", "conclusion"],
    "overall": ["abstract", "introduction", "conclusion"],
}

_DIMENSION_DEFINITIONS = {
    "soundness": "Technical correctness, rigor of methodology, validity of experimental design",
    "presentation": "Clarity of writing, organization, figure quality, readability",
    "contribution": "Novelty, significance, impact on the field, advancement over prior work",
    "overall": "Overall paper quality combining all dimensions",
}

# Only generate concerns for dimensions below this percentile
CONCERN_THRESHOLD_PERCENTILE = 40.0
MAX_CONCERN_DIMENSIONS = 3


async def generate_concerns(
    paper: PaperData,
    scores: CalibratedScores,
    config: PipelineConfig,
) -> list[Finding]:
    """Generate anticipated reviewer concerns for low-scoring dimensions."""
    findings: list[Finding] = []

    if not config.anthropic_api_key:
        return findings

    # Find dimensions below the concern threshold
    low_dims = []
    for dim, percentile in [
        ("soundness", scores.soundness_percentile),
        ("presentation", scores.presentation_percentile),
        ("contribution", scores.contribution_percentile),
        ("overall", scores.overall_percentile),
    ]:
        if percentile is not None and percentile < CONCERN_THRESHOLD_PERCENTILE:
            low_dims.append((dim, percentile, getattr(scores, dim, None)))

    if not low_dims:
        return findings

    # Sort by percentile (lowest first) and cap
    low_dims.sort(key=lambda x: x[1])
    low_dims = low_dims[:MAX_CONCERN_DIMENSIONS]

    llm = LLMClient(config)

    for dim, percentile, score in low_dims:
        section_text = _get_relevant_text(paper, dim)
        if not section_text:
            continue

        try:
            result = await llm.query(
                "anticipated_concerns",
                variables={
                    "dimension": dim,
                    "dimension_definition": _DIMENSION_DEFINITIONS.get(dim, dim),
                    "predicted_score": f"{score:.2f}" if score else "low",
                    "percentile": f"{percentile:.0f}th",
                    "paper_text": section_text[:3000],
                },
            )
        except (LLMParseError, Exception) as e:
            logger.warning("Concern generation failed for %s: %s", dim, e)
            continue

        for concern in result.concerns:
            severity = "warning" if concern.severity in ("major", "moderate") else "info"
            findings.append(Finding(
                severity=severity,
                category="anticipated_concern",
                message=f"[{dim.title()} — {percentile:.0f}th percentile] {concern.concern}",
                location=concern.location,
                suggestion=concern.suggestion,
            ))

    return findings


def _get_relevant_text(paper: PaperData, dimension: str) -> str:
    """Get the paper text sections relevant to a given review dimension."""
    section_getters = {
        "abstract": get_abstract,
        "introduction": get_introduction,
        "methods": get_methods,
        "results": get_results,
        "conclusion": get_conclusion,
    }
    sections = _DIMENSION_SECTIONS.get(dimension, ["abstract"])
    parts = []
    for sec in sections:
        getter = section_getters.get(sec)
        if getter:
            text = getter(paper)
            if text:
                parts.append(f"[{sec.upper()}]\n{text}")
    return "\n\n".join(parts)

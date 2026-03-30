"""Abstract↔conclusion alignment checking via LLM."""

from __future__ import annotations

import logging

from papercheck.config import PipelineConfig
from papercheck.extractors.metadata import get_abstract, get_conclusion, get_introduction
from papercheck.llm.client import LLMClient, LLMParseError
from papercheck.llm.schemas import AlignmentResult
from papercheck.models import Finding, PaperData

logger = logging.getLogger(__name__)


async def check_claim_alignment(
    paper: PaperData, config: PipelineConfig, llm_client: LLMClient | None = None
) -> list[Finding]:
    """Check whether abstract claims are supported by the conclusion.

    Uses LLM-based analysis. If no API key is configured or the LLM call fails,
    returns an info finding and degrades gracefully.
    """
    abstract = get_abstract(paper)
    conclusion = get_conclusion(paper)

    if not abstract:
        return [Finding(
            severity="info",
            category="claim_alignment_skipped",
            message="Claim alignment skipped: no abstract found",
        )]

    if not conclusion:
        return [Finding(
            severity="info",
            category="claim_alignment_skipped",
            message="Claim alignment skipped: no conclusion section found",
        )]

    if not config.anthropic_api_key:
        return [Finding(
            severity="info",
            category="claim_alignment_skipped",
            message="Claim alignment skipped: no Anthropic API key configured",
        )]

    if llm_client is None:
        llm_client = LLMClient(config)

    try:
        result: AlignmentResult = await llm_client.query(
            prompt_name="abstract_conclusion_alignment",
            variables={"abstract": abstract, "conclusion": conclusion},
        )
    except LLMParseError as e:
        logger.warning("LLM claim alignment failed: %s", e)
        return [Finding(
            severity="warning",
            category="claim_alignment_error",
            message=f"Claim alignment check failed: {e}",
        )]

    findings: list[Finding] = []

    for claim in result.aligned_claims:
        if claim.alignment == "overclaimed":
            findings.append(Finding(
                severity="warning",
                category="overclaiming",
                message=f"Abstract overclaims: \"{claim.abstract_claim}\"",
                evidence=claim.explanation,
                suggestion="Soften the claim or add supporting evidence in the conclusion.",
            ))
        elif claim.alignment == "unsupported":
            findings.append(Finding(
                severity="warning",
                category="unsupported_claim",
                message=f"Abstract claim not supported by conclusion: \"{claim.abstract_claim}\"",
                evidence=claim.explanation,
                suggestion="Add conclusion text supporting this claim, or remove it from abstract.",
            ))
        elif claim.alignment == "partially_supported":
            findings.append(Finding(
                severity="info",
                category="partial_support",
                message=f"Abstract claim only partially supported: \"{claim.abstract_claim}\"",
                evidence=claim.explanation,
            ))

    if result.overall_assessment == "significant_overclaiming":
        findings.append(Finding(
            severity="error",
            category="overclaiming",
            message="Significant overclaiming detected between abstract and conclusion",
            evidence=result.explanation,
        ))
    elif result.overall_assessment == "minor_gaps":
        findings.append(Finding(
            severity="info",
            category="minor_gaps",
            message="Minor gaps between abstract claims and conclusion findings",
            evidence=result.explanation,
        ))

    return findings

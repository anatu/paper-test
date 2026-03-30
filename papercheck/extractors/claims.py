"""Extract empirical claims from a paper via LLM."""

from __future__ import annotations

import logging

from papercheck.config import PipelineConfig
from papercheck.extractors.metadata import get_abstract, get_introduction
from papercheck.llm.client import LLMClient, LLMParseError
from papercheck.llm.schemas import ClaimExtractionResult
from papercheck.models import PaperData

logger = logging.getLogger(__name__)


async def extract_claims(
    paper: PaperData,
    config: PipelineConfig,
    llm: LLMClient | None = None,
) -> ClaimExtractionResult | None:
    """Extract stated contributions and empirical claims from a paper.

    Uses the claim_extraction_abstract prompt. Returns None if LLM is
    unavailable or extraction fails.
    """
    abstract = get_abstract(paper)
    introduction = get_introduction(paper)

    if not abstract and not introduction:
        logger.info("No abstract or introduction found — skipping claim extraction")
        return None

    if llm is None:
        if not config.anthropic_api_key:
            logger.info("No API key — skipping LLM claim extraction")
            return None
        llm = LLMClient(config)

    try:
        result = await llm.query(
            "claim_extraction_abstract",
            variables={
                "abstract": abstract or "(not available)",
                "introduction": introduction[:3000] if introduction else "(not available)",
            },
        )
        return result
    except (LLMParseError, Exception) as e:
        logger.warning("Claim extraction failed: %s", e)
        return None

"""Layer 2: Citation Verification — existence, claim alignment, coverage."""

from __future__ import annotations

import logging
import time

from papercheck.cache.store import CacheStore
from papercheck.config import PipelineConfig
from papercheck.external.crossref import CrossRefClient
from papercheck.external.openal import OpenAlexClient
from papercheck.external.semantic_scholar import SemanticScholarClient
from papercheck.extractors.metadata import get_introduction
from papercheck.extractors.references import extract_citation_contexts
from papercheck.layers.base import VerificationLayer
from papercheck.llm.client import LLMClient, LLMParseError
from papercheck.models import Finding, LayerResult, PaperData, Reference

logger = logging.getLogger(__name__)


class CitationVerificationLayer(VerificationLayer):
    layer_number = 2
    layer_name = "Citation Verification"

    async def verify(self, paper: PaperData, config: PipelineConfig) -> LayerResult:
        """Run citation verification checks.

        1. Citation existence — verify each reference exists via S2/CrossRef/OpenAlex
        2. Claim-citation alignment — check claims match cited paper (LLM)
        3. Related work coverage — assess literature completeness (LLM + S2 recs)
        """
        start = time.time()
        findings: list[Finding] = []

        # Enrich references with citation contexts
        references = extract_citation_contexts(paper)
        if not references:
            # Fall back to paper's references if extractor returns nothing
            references = paper.references

        if not references:
            findings.append(Finding(
                severity="warning",
                category="no_references",
                message="No references found in the paper",
                suggestion="Ensure the paper includes a bibliography section",
            ))
            score, signal = self._score_findings(findings, config)
            return LayerResult(
                layer=self.layer_number,
                layer_name=self.layer_name,
                score=score,
                signal=signal,
                findings=findings,
                execution_time_seconds=time.time() - start,
            )

        # Set up API clients with caching
        cache = _make_cache(config)
        s2 = SemanticScholarClient(
            api_key=config.s2_api_key,
            cache=cache,
            cache_ttl_hours=config.cache_ttl_hours,
        )
        crossref = CrossRefClient(cache=cache, cache_ttl_hours=720)
        openalex = OpenAlexClient(cache=cache, cache_ttl_hours=720)

        # Set up LLM client (may be None if no API key)
        llm = None
        if config.anthropic_api_key:
            llm = LLMClient(config)

        try:
            # 1. Citation existence check
            verified_papers = {}  # key -> S2Paper or dict with abstract
            try:
                findings.extend(
                    _check_citation_existence(references, s2, crossref, openalex, verified_papers)
                )
            except Exception as e:
                logger.warning("Citation existence check failed: %s", e)
                findings.append(Finding(
                    severity="info",
                    category="existence_check_error",
                    message=f"Citation existence check encountered an error: {type(e).__name__}",
                ))

            # 2. Claim-citation alignment (LLM-based, degrades without API key)
            findings.extend(
                await _check_claim_alignment(references, verified_papers, llm)
            )

            # 3. Related work coverage (LLM + S2 recommendations)
            findings.extend(
                await _check_related_work_coverage(paper, references, s2, verified_papers, llm)
            )
        finally:
            s2.close()
            crossref.close()
            openalex.close()
            if cache:
                cache.close()

        score, signal = self._score_findings(findings, config)
        return LayerResult(
            layer=self.layer_number,
            layer_name=self.layer_name,
            score=score,
            signal=signal,
            findings=findings,
            execution_time_seconds=time.time() - start,
        )


def _make_cache(config: PipelineConfig) -> CacheStore | None:
    """Create a cache store for API responses."""
    try:
        return CacheStore(
            config.cache_dir / "layer2.db",
            default_ttl_hours=config.cache_ttl_hours,
        )
    except Exception:
        logger.warning("Failed to create cache for Layer 2, proceeding without cache")
        return None


def _check_citation_existence(
    references: list[Reference],
    s2: SemanticScholarClient,
    crossref: CrossRefClient,
    openalex: OpenAlexClient,
    verified_papers: dict,
) -> list[Finding]:
    """Check that each cited reference actually exists.

    Lookup chain: Semantic Scholar → CrossRef → OpenAlex.
    """
    findings: list[Finding] = []

    for ref in references:
        if not ref.title:
            # Can't verify without a title
            findings.append(Finding(
                severity="info",
                category="citation_unverifiable",
                message=f"Reference [{ref.key}] has no extractable title — cannot verify existence",
                evidence=ref.raw_text[:200] if ref.raw_text else None,
            ))
            continue

        # Try Semantic Scholar first
        paper = s2.get_paper_by_title(
            ref.title,
            authors=ref.authors or None,
            year=ref.year,
        )
        if paper:
            verified_papers[ref.key] = {
                "title": paper.title,
                "abstract": paper.abstract or "",
                "paper_id": paper.paper_id,
                "year": paper.year,
                "authors": paper.authors,
            }
            continue

        # Fallback: CrossRef
        cr_result = crossref.lookup_by_title(
            ref.title,
            author=ref.authors[0] if ref.authors else None,
        )
        if cr_result:
            verified_papers[ref.key] = {
                "title": cr_result.get("title", ""),
                "abstract": "",  # CrossRef doesn't provide abstracts
                "year": cr_result.get("year"),
                "authors": cr_result.get("authors", []),
            }
            continue

        # Fallback: OpenAlex
        oa_result = openalex.search_by_title(ref.title)
        if oa_result:
            verified_papers[ref.key] = {
                "title": oa_result.get("title", ""),
                "abstract": "",
                "year": oa_result.get("year"),
                "authors": oa_result.get("authors", []),
            }
            continue

        # Not found anywhere
        findings.append(Finding(
            severity="error",
            category="citation_not_found",
            message=(
                f"Reference [{ref.key}] could not be verified: "
                f"\"{ref.title}\" ({ref.year or 'n/a'})"
            ),
            evidence=ref.raw_text[:200] if ref.raw_text else None,
            suggestion=(
                "Verify that this citation is correct. It may be a preprint not yet indexed, "
                "or the title/authors may contain errors."
            ),
        ))

    found_count = len(verified_papers)
    total_count = len(references)
    findings.append(Finding(
        severity="info",
        category="citation_summary",
        message=f"Verified {found_count}/{total_count} references via external databases",
    ))

    return findings


async def _check_claim_alignment(
    references: list[Reference],
    verified_papers: dict,
    llm: LLMClient | None,
) -> list[Finding]:
    """Check that claims attributed to cited papers are actually supported."""
    findings: list[Finding] = []

    if llm is None:
        findings.append(Finding(
            severity="info",
            category="claim_alignment_skipped",
            message="Claim-citation alignment check skipped (no API key)",
        ))
        return findings

    for ref in references:
        if ref.key not in verified_papers:
            continue
        verified = verified_papers[ref.key]
        cited_abstract = verified.get("abstract", "")
        if not cited_abstract:
            continue  # Can't check alignment without abstract

        for ctx in ref.in_text_contexts:
            if not ctx.claim_text:
                continue

            try:
                result = await llm.query(
                    "citation_claim_alignment",
                    variables={
                        "citing_sentence": ctx.surrounding_text,
                        "claim_text": ctx.claim_text,
                        "cited_title": verified.get("title", ref.title or ""),
                        "cited_abstract": cited_abstract,
                    },
                )
            except (LLMParseError, Exception) as e:
                logger.warning("LLM claim alignment check failed for [%s]: %s", ref.key, e)
                continue

            if result.judgment in ("misrepresented", "fabricated"):
                severity = "error" if result.judgment == "fabricated" else "warning"
                findings.append(Finding(
                    severity=severity,
                    category="claim_misattribution",
                    message=(
                        f"Claim attributed to [{ref.key}] appears to be {result.judgment}: "
                        f"\"{ctx.claim_text[:100]}\""
                    ),
                    location=ctx.section,
                    evidence=result.explanation,
                    suggestion=(
                        f"Review the claim about [{ref.key}]. "
                        f"{result.key_evidence or ''}"
                    ),
                ))

    return findings


async def _check_related_work_coverage(
    paper: PaperData,
    references: list[Reference],
    s2: SemanticScholarClient,
    verified_papers: dict,
    llm: LLMClient | None,
) -> list[Finding]:
    """Assess whether the related work section covers the relevant literature."""
    findings: list[Finding] = []

    if llm is None:
        findings.append(Finding(
            severity="info",
            category="coverage_check_skipped",
            message="Related work coverage check skipped (no API key)",
        ))
        return findings

    # Find the related work section text
    related_work_text = _find_related_work_text(paper)
    if not related_work_text:
        # Use introduction as fallback (many papers embed related work there)
        related_work_text = get_introduction(paper)
    if not related_work_text:
        return findings  # Can't assess coverage without text

    # Get recommendations from S2 for any verified paper
    recommended = []
    for key, info in verified_papers.items():
        pid = info.get("paper_id", "")
        if pid:
            recs = s2.get_recommendations(pid, limit=10)
            for r in recs:
                recommended.append({
                    "title": r.title,
                    "authors": ", ".join(r.authors[:3]),
                    "year": r.year,
                    "abstract": (r.abstract or "")[:300],
                })
            if recommended:
                break  # One good seed is enough

    if not recommended:
        return findings  # Can't assess without recommendations

    # Deduplicate by title
    seen = set()
    unique_recs = []
    for r in recommended:
        t = r["title"].lower().strip()
        if t not in seen:
            seen.add(t)
            unique_recs.append(r)
    recommended = unique_recs[:15]

    recs_text = "\n".join(
        f"- {r['title']} ({r['authors']}, {r['year']}): {r['abstract'][:200]}"
        for r in recommended
    )

    try:
        result = await llm.query(
            "related_work_coverage",
            variables={
                "related_work_text": related_work_text[:3000],
                "recommended_papers": recs_text,
            },
        )
    except (LLMParseError, Exception) as e:
        logger.warning("LLM coverage assessment failed: %s", e)
        return findings

    for missing in result.missing_important:
        if missing.severity == "critical_omission":
            findings.append(Finding(
                severity="warning",
                category="incomplete_related_work",
                message=f"Potentially missing important reference: \"{missing.title}\"",
                evidence=missing.why_important,
                suggestion="Consider discussing this paper in the related work section",
            ))
        elif missing.severity == "should_discuss":
            findings.append(Finding(
                severity="info",
                category="incomplete_related_work",
                message=f"Consider citing: \"{missing.title}\"",
                evidence=missing.why_important,
            ))

    return findings


def _find_related_work_text(paper: PaperData) -> str:
    """Find the related work section text."""
    candidates = [
        "related work", "related works", "background",
        "literature review", "prior work", "previous work",
    ]
    for section in paper.sections:
        heading_lower = section.heading.lower().strip()
        for candidate in candidates:
            if candidate in heading_lower:
                return section.text
    return ""

"""Layer 3: Cross-Paper Consistency — claim extraction + contradiction search."""

from __future__ import annotations

import logging
import time

from papercheck.config import PipelineConfig
from papercheck.extractors.claims import extract_claims
from papercheck.extractors.metadata import get_abstract, get_introduction, get_results
from papercheck.layers.base import VerificationLayer
from papercheck.llm.client import LLMClient, LLMParseError
from papercheck.models import Finding, LayerResult, PaperData

logger = logging.getLogger(__name__)

# Optional imports — Layer 3 degrades gracefully without corpus deps
try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False

try:
    from sentence_transformers import SentenceTransformer

    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False


class CrossPaperConsistencyLayer(VerificationLayer):
    layer_number = 3
    layer_name = "Cross-Paper Consistency"

    async def verify(self, paper: PaperData, config: PipelineConfig) -> LayerResult:
        """Run cross-paper consistency checks.

        1. Extract core claims via LLM
        2. Embed claims and search ChromaDB corpus for similar claims
        3. Check top matches for contradictions (LLM)

        Degrades gracefully if chromadb/sentence-transformers not installed
        or if no corpus is available.
        """
        start = time.time()
        findings: list[Finding] = []

        # Set up LLM client
        llm = None
        if config.anthropic_api_key:
            llm = LLMClient(config)

        # 1. Extract claims
        claims_result = await extract_claims(paper, config, llm)
        if claims_result is None:
            findings.append(Finding(
                severity="info",
                category="claim_extraction_skipped",
                message="Claim extraction skipped (no API key or no abstract/intro)",
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

        # Report extracted claims
        n_empirical = len(claims_result.empirical_claims)
        n_contributions = len(claims_result.stated_contributions)
        findings.append(Finding(
            severity="info",
            category="claims_extracted",
            message=(
                f"Extracted {n_contributions} stated contributions and "
                f"{n_empirical} empirical claims"
            ),
        ))

        # 2. Corpus search for contradictions
        if not HAS_CHROMADB or not HAS_SENTENCE_TRANSFORMERS:
            findings.append(Finding(
                severity="info",
                category="corpus_search_skipped",
                message=(
                    "Corpus contradiction search skipped "
                    "(install chromadb and sentence-transformers: "
                    "pip install papercheck[corpus])"
                ),
            ))
        else:
            corpus_findings = await _search_corpus_for_contradictions(
                claims_result, paper, config, llm
            )
            findings.extend(corpus_findings)

        # 3. Internal consistency: check claims against results
        internal_findings = _check_internal_claim_consistency(claims_result, paper)
        findings.extend(internal_findings)

        score, signal = self._score_findings(findings, config)
        return LayerResult(
            layer=self.layer_number,
            layer_name=self.layer_name,
            score=score,
            signal=signal,
            findings=findings,
            execution_time_seconds=time.time() - start,
        )


async def _search_corpus_for_contradictions(
    claims_result,
    paper: PaperData,
    config: PipelineConfig,
    llm: LLMClient | None,
) -> list[Finding]:
    """Search a ChromaDB corpus for contradicting claims."""
    findings: list[Finding] = []

    corpus_dir = config.cache_dir / "corpus_db"
    try:
        client = chromadb.Client(ChromaSettings(
            persist_directory=str(corpus_dir),
            anonymized_telemetry=False,
        ))
        collection = client.get_or_create_collection("paper_claims")
    except Exception as e:
        logger.warning("Failed to open corpus database: %s", e)
        findings.append(Finding(
            severity="info",
            category="corpus_unavailable",
            message="Corpus database not available for contradiction search",
        ))
        return findings

    if collection.count() == 0:
        findings.append(Finding(
            severity="info",
            category="corpus_empty",
            message="Corpus is empty — no cross-paper contradiction search performed",
            suggestion="Index papers with `papercheck corpus build` to enable this check",
        ))
        return findings

    # Embed and search for each empirical claim
    model = SentenceTransformer("all-MiniLM-L6-v2")

    for claim in claims_result.empirical_claims:
        embedding = model.encode(claim.claim_text).tolist()
        results = collection.query(
            query_embeddings=[embedding],
            n_results=5,
        )

        if not results or not results.get("documents"):
            continue

        # Check top matches for contradictions via LLM
        if llm is None:
            continue

        for doc, meta in zip(
            results["documents"][0],
            results.get("metadatas", [[]])[0],
        ):
            if not doc:
                continue
            try:
                result = await llm.query(
                    "contradiction_check",
                    variables={
                        "paper_claim": claim.claim_text,
                        "corpus_claim": doc,
                        "paper_context": get_abstract(paper)[:500],
                        "corpus_context": meta.get("context", "")[:500] if meta else "",
                    },
                )
            except (LLMParseError, Exception) as e:
                logger.warning("Contradiction check failed: %s", e)
                continue

            if result.relationship == "contradicts":
                source = meta.get("source", "corpus paper") if meta else "corpus paper"
                findings.append(Finding(
                    severity="warning",
                    category="contradiction_detected",
                    message=(
                        f"Potential contradiction with {source}: "
                        f"\"{doc[:100]}...\""
                    ),
                    evidence=result.explanation,
                    suggestion="Review this claim in the context of existing literature",
                ))
            elif result.relationship == "tensions":
                findings.append(Finding(
                    severity="info",
                    category="tension_detected",
                    message=f"Tension with corpus claim: \"{doc[:100]}...\"",
                    evidence=result.explanation,
                ))

    return findings


def _check_internal_claim_consistency(claims_result, paper: PaperData) -> list[Finding]:
    """Basic heuristic checks on extracted claims vs paper content."""
    findings: list[Finding] = []

    results_text = get_results(paper).lower()
    if not results_text:
        return findings

    # Check if quantitative claims mention specific values that appear in results
    for claim in claims_result.empirical_claims:
        if claim.quantitative and claim.value:
            # Check if the claimed value appears in the results section
            value_str = claim.value.replace("%", "").strip()
            if value_str and value_str not in results_text:
                findings.append(Finding(
                    severity="info",
                    category="claim_value_not_in_results",
                    message=(
                        f"Claimed value \"{claim.value}\" for metric \"{claim.metric}\" "
                        f"not found in results section"
                    ),
                    suggestion="Verify that the claimed value matches the reported results",
                ))

    return findings

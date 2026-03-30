"""Layer 5: Logical Structure Verification — hypothesis and results alignment."""

from __future__ import annotations

import logging
import time

from papercheck.config import PipelineConfig
from papercheck.extractors.metadata import (
    get_abstract,
    get_conclusion,
    get_introduction,
    get_methods,
    get_results,
)
from papercheck.layers.base import VerificationLayer
from papercheck.llm.client import LLMClient, LLMParseError
from papercheck.models import Finding, LayerResult, PaperData

logger = logging.getLogger(__name__)


class LogicalStructureLayer(VerificationLayer):
    layer_number = 5
    layer_name = "Logical Structure"

    async def verify(self, paper: PaperData, config: PipelineConfig) -> LayerResult:
        """Run logical structure verification.

        1. Extract hypothesis from abstract/intro, check alignment with methods (LLM)
        2. Check results↔conclusion alignment (LLM)

        Degrades gracefully without API key.
        """
        start = time.time()
        findings: list[Finding] = []

        if not config.anthropic_api_key:
            findings.append(Finding(
                severity="info",
                category="logic_check_skipped",
                message="Logical structure checks skipped (no API key)",
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

        llm = LLMClient(config)

        # 1. Hypothesis↔experiment alignment
        hyp_findings = await _check_hypothesis_experiment(paper, llm)
        findings.extend(hyp_findings)

        # 2. Results↔conclusion alignment
        rc_findings = await _check_results_conclusion(paper, llm)
        findings.extend(rc_findings)

        score, signal = self._score_findings(findings, config)
        return LayerResult(
            layer=self.layer_number,
            layer_name=self.layer_name,
            score=score,
            signal=signal,
            findings=findings,
            execution_time_seconds=time.time() - start,
        )


async def _check_hypothesis_experiment(paper: PaperData, llm: LLMClient) -> list[Finding]:
    """Check that experimental design tests the stated hypothesis."""
    findings: list[Finding] = []

    abstract = get_abstract(paper)
    intro = get_introduction(paper)
    methods = get_methods(paper)

    abstract_intro = ""
    if abstract:
        abstract_intro += f"ABSTRACT: {abstract}\n\n"
    if intro:
        abstract_intro += f"INTRODUCTION: {intro[:2000]}"

    if not abstract_intro:
        findings.append(Finding(
            severity="info",
            category="hypothesis_check_skipped",
            message="No abstract or introduction found — skipping hypothesis check",
        ))
        return findings

    if not methods:
        findings.append(Finding(
            severity="info",
            category="hypothesis_check_skipped",
            message="No methodology section found — skipping hypothesis-experiment alignment",
        ))
        return findings

    try:
        result = await llm.query(
            "hypothesis_experiment_alignment",
            variables={
                "abstract_intro": abstract_intro[:3000],
                "methodology": methods[:3000],
            },
        )
    except (LLMParseError, Exception) as e:
        logger.warning("Hypothesis-experiment alignment check failed: %s", e)
        findings.append(Finding(
            severity="info",
            category="hypothesis_check_error",
            message=f"Hypothesis-experiment alignment check failed: {type(e).__name__}",
        ))
        return findings

    # Report the extracted hypothesis
    if result.hypothesis:
        findings.append(Finding(
            severity="info",
            category="hypothesis_extracted",
            message=f"Extracted hypothesis: \"{result.hypothesis[:200]}\"",
        ))

    # Report alignment assessment
    if result.alignment in ("weak", "misaligned"):
        severity = "error" if result.alignment == "misaligned" else "warning"
        findings.append(Finding(
            severity=severity,
            category="hypothesis_experiment_gap",
            message=f"Hypothesis-experiment alignment is {result.alignment}",
            evidence=result.explanation,
            suggestion="Ensure experimental design directly tests the stated hypothesis",
        ))

        for gap in result.gaps:
            findings.append(Finding(
                severity="warning" if result.alignment == "misaligned" else "info",
                category="experimental_gap",
                message=f"Experimental gap: {gap}",
            ))
    else:
        findings.append(Finding(
            severity="info",
            category="hypothesis_experiment_aligned",
            message=f"Hypothesis-experiment alignment is {result.alignment}",
            evidence=result.explanation,
        ))

    return findings


async def _check_results_conclusion(paper: PaperData, llm: LLMClient) -> list[Finding]:
    """Check that conclusions are warranted by the reported results."""
    findings: list[Finding] = []

    results_text = get_results(paper)
    conclusion_text = get_conclusion(paper)

    if not results_text:
        findings.append(Finding(
            severity="info",
            category="results_conclusion_skipped",
            message="No results section found — skipping results-conclusion alignment",
        ))
        return findings

    if not conclusion_text:
        findings.append(Finding(
            severity="info",
            category="results_conclusion_skipped",
            message="No conclusion section found — skipping results-conclusion alignment",
        ))
        return findings

    try:
        result = await llm.query(
            "results_conclusion_alignment",
            variables={
                "results": results_text[:3000],
                "conclusion": conclusion_text[:2000],
            },
        )
    except (LLMParseError, Exception) as e:
        logger.warning("Results-conclusion alignment check failed: %s", e)
        findings.append(Finding(
            severity="info",
            category="results_conclusion_error",
            message=f"Results-conclusion alignment check failed: {type(e).__name__}",
        ))
        return findings

    # Report overclaimed conclusions
    for oc in result.overclaimed:
        findings.append(Finding(
            severity="warning",
            category="overclaimed_conclusion",
            message=f"Potentially overclaimed: \"{oc.conclusion_claim[:150]}\"",
            evidence=f"Gap: {oc.gap}" if oc.gap else None,
            suggestion=(
                f"Strongest supporting result: \"{oc.strongest_supporting_result[:150]}\""
                if oc.strongest_supporting_result else
                "No direct supporting result identified"
            ),
        ))

    # Report underdiscussed negative results
    for neg in result.underdiscussed_negatives:
        findings.append(Finding(
            severity="info",
            category="underdiscussed_negative",
            message=f"Underdiscussed negative result: {neg}",
            suggestion="Consider acknowledging this limitation in the conclusion",
        ))

    # Overall assessment
    if result.overall == "significant_overclaiming":
        findings.append(Finding(
            severity="error",
            category="significant_overclaiming",
            message="Conclusions significantly overclaim relative to reported results",
            evidence=result.explanation,
        ))
    elif result.overall == "minor_overclaiming":
        findings.append(Finding(
            severity="warning",
            category="minor_overclaiming",
            message="Some conclusions may slightly overclaim relative to reported results",
            evidence=result.explanation,
        ))
    else:
        findings.append(Finding(
            severity="info",
            category="conclusions_well_supported",
            message="Conclusions appear well-supported by the reported results",
            evidence=result.explanation,
        ))

    return findings

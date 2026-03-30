"""Layer 1: Formal Consistency Checks."""

from __future__ import annotations

import time

from papercheck.checkers.claim_alignment import check_claim_alignment
from papercheck.checkers.math_consistency import check_math_consistency
from papercheck.checkers.statcheck import check_statistical_consistency
from papercheck.checkers.xref_integrity import check_xref_integrity
from papercheck.config import PipelineConfig
from papercheck.layers.base import VerificationLayer
from papercheck.models import Finding, LayerResult, PaperData


class FormalConsistencyLayer(VerificationLayer):
    layer_number = 1
    layer_name = "Formal Consistency"

    async def verify(self, paper: PaperData, config: PipelineConfig) -> LayerResult:
        """Run all formal consistency checks.

        1. Statistical audit — check reported statistics for internal consistency
        2. Math consistency — variable naming, duplicate equation labels
        3. Cross-reference integrity — dangling \\ref{} and \\cite{}
        4. Claim alignment — abstract↔conclusion consistency (LLM-based)
        """
        start = time.time()
        findings: list[Finding] = []

        # 1. Statistical audit
        findings.extend(check_statistical_consistency(paper.raw_text))

        # 2. Math consistency
        findings.extend(check_math_consistency(paper.equations, paper.raw_text))

        # 3. Cross-reference integrity
        findings.extend(check_xref_integrity(paper))

        # 4. Claim alignment (LLM — degrades gracefully without API key)
        findings.extend(await check_claim_alignment(paper, config))

        score, signal = self._score_findings(findings, config)
        return LayerResult(
            layer=self.layer_number,
            layer_name=self.layer_name,
            score=score,
            signal=signal,
            findings=findings,
            execution_time_seconds=time.time() - start,
        )

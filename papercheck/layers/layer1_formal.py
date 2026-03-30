"""Layer 1: Formal Consistency Checks — stub for Phase 1."""

from __future__ import annotations

import time

from papercheck.config import PipelineConfig
from papercheck.layers.base import VerificationLayer
from papercheck.models import Finding, LayerResult, PaperData


class FormalConsistencyLayer(VerificationLayer):
    layer_number = 1
    layer_name = "Formal Consistency"

    async def verify(self, paper: PaperData, config: PipelineConfig) -> LayerResult:
        """Phase 1 stub — returns placeholder pass result.

        Full implementation (Phase 2) runs:
        1. statistical_audit
        2. math_consistency
        3. xref_integrity
        4. metadata_alignment (LLM)
        """
        start = time.time()
        findings: list[Finding] = []

        findings.append(
            Finding(
                severity="info",
                category="stub",
                message="Layer 1 is a stub — full formal consistency checks in Phase 2",
            )
        )

        score, signal = self._score_findings(findings, config)
        return LayerResult(
            layer=self.layer_number,
            layer_name=self.layer_name,
            score=score,
            signal=signal,
            findings=findings,
            execution_time_seconds=time.time() - start,
        )

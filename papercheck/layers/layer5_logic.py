"""Layer 5: Logical Structure Verification — stub for Phase 1."""

from __future__ import annotations

import time

from papercheck.config import PipelineConfig
from papercheck.layers.base import VerificationLayer
from papercheck.models import Finding, LayerResult, PaperData


class LogicalStructureLayer(VerificationLayer):
    layer_number = 5
    layer_name = "Logical Structure"

    async def verify(self, paper: PaperData, config: PipelineConfig) -> LayerResult:
        """Phase 1 stub — no LLM analysis.

        Phase 4 will implement hypothesis-experiment alignment,
        results-conclusion alignment, and argumentation DAG.
        """
        start = time.time()
        findings = [
            Finding(
                severity="info",
                category="stub",
                message="Layer 5 is a stub — logical structure checks in Phase 4",
            )
        ]
        score, signal = self._score_findings(findings, config)
        return LayerResult(
            layer=self.layer_number,
            layer_name=self.layer_name,
            score=score,
            signal=signal,
            findings=findings,
            execution_time_seconds=time.time() - start,
        )

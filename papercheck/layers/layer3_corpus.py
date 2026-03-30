"""Layer 3: Cross-Paper Consistency — stub for Phase 1."""

from __future__ import annotations

import time

from papercheck.config import PipelineConfig
from papercheck.layers.base import VerificationLayer
from papercheck.models import Finding, LayerResult, PaperData


class CrossPaperConsistencyLayer(VerificationLayer):
    layer_number = 3
    layer_name = "Cross-Paper Consistency"

    async def verify(self, paper: PaperData, config: PipelineConfig) -> LayerResult:
        """Phase 1 stub — no corpus analysis.

        Phase 4 will implement claim extraction, embedding, contradiction detection.
        """
        start = time.time()
        findings = [
            Finding(
                severity="info",
                category="stub",
                message="Layer 3 is a stub — cross-paper consistency checks in Phase 4",
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

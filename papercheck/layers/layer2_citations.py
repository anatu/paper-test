"""Layer 2: Citation Verification — stub for Phase 1."""

from __future__ import annotations

import time

from papercheck.config import PipelineConfig
from papercheck.layers.base import VerificationLayer
from papercheck.models import Finding, LayerResult, PaperData


class CitationVerificationLayer(VerificationLayer):
    layer_number = 2
    layer_name = "Citation Verification"

    async def verify(self, paper: PaperData, config: PipelineConfig) -> LayerResult:
        """Phase 1 stub — reports reference count, no external lookups.

        Full implementation (Phase 3) checks citation existence, claim-citation
        alignment, and related work coverage.
        """
        start = time.time()
        findings: list[Finding] = []

        ref_count = len(paper.references)
        findings.append(
            Finding(
                severity="info",
                category="stub",
                message=f"Layer 2 is a stub — found {ref_count} references, verification in Phase 3",
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

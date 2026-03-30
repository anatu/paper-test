"""Layer 4: Reproducibility Check — stub for Phase 1."""

from __future__ import annotations

import time

from papercheck.config import PipelineConfig
from papercheck.layers.base import VerificationLayer
from papercheck.models import Finding, LayerResult, PaperData


class ReproducibilityLayer(VerificationLayer):
    layer_number = 4
    layer_name = "Reproducibility Check"

    async def verify(self, paper: PaperData, config: PipelineConfig) -> LayerResult:
        """Phase 1 stub — skips because no repo detection is implemented.

        Phase 4 will detect repos, clone, build-verify, and run smoke tests.
        """
        start = time.time()
        return LayerResult(
            layer=self.layer_number,
            layer_name=self.layer_name,
            score=1.0,
            signal="pass",
            findings=[],
            execution_time_seconds=time.time() - start,
            skipped=True,
            skip_reason="Reproducibility checks not yet implemented (Phase 4)",
        )

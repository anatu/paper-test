"""Abstract base class for verification layers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from papercheck.config import PipelineConfig
from papercheck.models import Finding, LayerResult, PaperData


SEVERITY_PENALTIES = {
    "critical": 0.3,
    "error": 0.15,
    "warning": 0.05,
    "info": 0.0,
}


class VerificationLayer(ABC):
    """Base class for all verification layers."""

    layer_number: int
    layer_name: str

    @abstractmethod
    async def verify(self, paper: PaperData, config: PipelineConfig) -> LayerResult:
        """Run verification and return a LayerResult."""
        ...

    def _score_findings(
        self, findings: list[Finding], config: PipelineConfig
    ) -> tuple[float, str]:
        """Convert findings list to (score, signal).

        Score starts at 1.0, subtracts per finding based on severity.
        Clamped to [0.0, 1.0].
        """
        score = 1.0
        for f in findings:
            score -= SEVERITY_PENALTIES.get(f.severity, 0.0)
        score = max(0.0, min(1.0, score))

        warn_threshold = config.warn_thresholds.get(self.layer_number, 0.6)
        fail_threshold = config.fail_thresholds.get(self.layer_number, 0.3)

        if score >= warn_threshold:
            signal = "pass"
        elif score >= fail_threshold:
            signal = "warn"
        else:
            signal = "fail"

        return score, signal

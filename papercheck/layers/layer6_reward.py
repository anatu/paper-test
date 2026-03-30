"""Layer 6: Peer-Review Reward Model — predicted review scores + concerns."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from papercheck.config import PipelineConfig
from papercheck.layers.base import VerificationLayer
from papercheck.models import Finding, LayerResult, PaperData

logger = logging.getLogger(__name__)


class RewardModelLayer(VerificationLayer):
    layer_number = 6
    layer_name = "Peer-Review Reward Model"

    def __init__(self):
        self._inference = None
        self._calibrator = None
        self._extractor = None

    async def verify(self, paper: PaperData, config: PipelineConfig) -> LayerResult:
        """Run reward model prediction and generate anticipated concerns.

        1. Load trained model (lazy, cached after first load)
        2. Extract features from PaperData
        3. Run inference -> raw predictions
        4. Calibrate scores -> CalibratedScores with percentiles
        5. Generate anticipated concerns for low-scoring dimensions (LLM)
        6. Construct LayerResult

        Skips if no trained model found.
        """
        start = time.time()

        model_dir = Path(config.reward_model_path)

        # Check model exists
        from papercheck.reward_model.integration import model_exists

        if not model_exists(model_dir):
            return LayerResult(
                layer=self.layer_number,
                layer_name=self.layer_name,
                score=1.0,
                signal="pass",
                findings=[],
                execution_time_seconds=time.time() - start,
                skipped=True,
                skip_reason="No trained reward model found (run `papercheck reward train` first)",
            )

        findings: list[Finding] = []

        try:
            # Lazy-load model components
            if self._inference is None:
                self._load_model(model_dir, config)

            # Extract features
            from papercheck.reward_model.data_processing import ProcessedPaper

            processed = ProcessedPaper(
                openreview_id="",
                title=paper.title,
                abstract=paper.abstract,
                full_text=paper.raw_text,
            )
            features = self._extractor.extract(processed)

            # Predict
            raw_preds = self._inference.predict(features)

            # Calibrate
            if self._calibrator:
                from papercheck.reward_model.calibration import CalibratedScores

                scores = self._calibrator.calibrate(raw_preds.model_dump())
            else:
                from papercheck.reward_model.calibration import CalibratedScores

                scores = CalibratedScores(
                    overall_rating=raw_preds.overall,
                    overall_percentile=raw_preds.overall * 100,
                    soundness=raw_preds.soundness,
                    soundness_percentile=raw_preds.soundness * 100,
                    presentation=raw_preds.presentation,
                    presentation_percentile=raw_preds.presentation * 100,
                    contribution=raw_preds.contribution,
                    contribution_percentile=raw_preds.contribution * 100,
                    accept_probability=raw_preds.accept_prob,
                )

            # Convert scores to findings
            from papercheck.reward_model.integration import (
                scores_to_findings,
                scores_to_layer_score,
            )

            findings.extend(scores_to_findings(scores))
            layer_score, signal = scores_to_layer_score(scores)

            # Generate anticipated concerns for low-scoring dimensions
            from papercheck.reward_model.concern_generator import generate_concerns

            concern_findings = await generate_concerns(paper, scores, config)
            findings.extend(concern_findings)

        except ImportError as e:
            return LayerResult(
                layer=self.layer_number,
                layer_name=self.layer_name,
                score=1.0,
                signal="pass",
                findings=[],
                execution_time_seconds=time.time() - start,
                skipped=True,
                skip_reason=f"Missing dependencies for reward model: {e}",
            )
        except Exception as e:
            logger.warning("Reward model inference failed: %s", e)
            findings.append(Finding(
                severity="info",
                category="reward_model_error",
                message=f"Reward model inference failed: {type(e).__name__}",
            ))
            layer_score = 1.0
            signal = "pass"

        return LayerResult(
            layer=self.layer_number,
            layer_name=self.layer_name,
            score=layer_score,
            signal=signal,
            findings=findings,
            execution_time_seconds=time.time() - start,
        )

    def _load_model(self, model_dir: Path, config: PipelineConfig) -> None:
        """Lazy-load model, calibrator, and feature extractor."""
        from papercheck.reward_model.feature_extraction import PaperFeatureExtractor
        from papercheck.reward_model.inference import RewardModelInference

        self._inference = RewardModelInference(
            model_dir=model_dir,
            device=config.reward_model_device,
        )
        self._inference.load()

        # Load calibrator if available
        cal_path = model_dir / "calibration.pkl"
        if cal_path.exists():
            from papercheck.reward_model.calibration import ScoreCalibrator

            self._calibrator = ScoreCalibrator.load(cal_path)

        # Feature extractor
        self._extractor = PaperFeatureExtractor()

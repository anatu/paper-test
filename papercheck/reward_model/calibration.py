"""Post-hoc calibration for reward model predictions."""

from __future__ import annotations

import logging
import pickle
from pathlib import Path

from pydantic import BaseModel

logger = logging.getLogger(__name__)

try:
    import numpy as np
    from sklearn.isotonic import IsotonicRegression

    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


class CalibratedScores(BaseModel):
    """Calibrated model predictions with percentile rankings."""

    overall_rating: float = 0.5
    overall_percentile: float = 50.0
    soundness: float | None = None
    soundness_percentile: float | None = None
    presentation: float | None = None
    presentation_percentile: float | None = None
    contribution: float | None = None
    contribution_percentile: float | None = None
    accept_probability: float = 0.5
    model_confidence: float = 0.5


class ScoreCalibrator:
    """Isotonic regression calibration for each score dimension."""

    def __init__(self):
        if not HAS_SKLEARN:
            raise ImportError("scikit-learn required: pip install scikit-learn")
        self._calibrators: dict[str, IsotonicRegression] = {}
        self._train_distributions: dict[str, list[float]] = {}

    def fit(
        self,
        val_predictions: dict[str, list[float]],
        val_labels: dict[str, list[float]],
    ) -> None:
        """Fit one isotonic regressor per dimension."""
        for dim in ["overall", "soundness", "presentation", "contribution", "accept_prob"]:
            preds = val_predictions.get(dim, [])
            labels = val_labels.get(dim, [])
            if not preds or not labels:
                continue
            # Filter NaN
            valid = [(p, l) for p, l in zip(preds, labels) if p == p and l == l]
            if len(valid) < 5:
                continue
            p_arr, l_arr = zip(*valid)
            iso = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
            iso.fit(np.array(p_arr), np.array(l_arr))
            self._calibrators[dim] = iso
            self._train_distributions[dim] = sorted(l_arr)

    def calibrate(self, raw_predictions: dict[str, float]) -> CalibratedScores:
        """Apply fitted calibrators to raw model output."""
        results = {}
        for dim in ["overall", "soundness", "presentation", "contribution"]:
            raw = raw_predictions.get(dim)
            if raw is None:
                results[dim] = None
                results[f"{dim}_percentile"] = None
                continue
            cal = self._calibrators.get(dim)
            if cal:
                calibrated = float(cal.predict(np.array([raw]))[0])
            else:
                calibrated = raw
            results[dim] = calibrated
            results[f"{dim}_percentile"] = self.get_percentile(calibrated, dim)

        accept_raw = raw_predictions.get("accept_prob", 0.5)
        cal = self._calibrators.get("accept_prob")
        accept_cal = float(cal.predict(np.array([accept_raw]))[0]) if cal else accept_raw

        return CalibratedScores(
            overall_rating=results.get("overall", 0.5) or 0.5,
            overall_percentile=results.get("overall_percentile", 50.0) or 50.0,
            soundness=results.get("soundness"),
            soundness_percentile=results.get("soundness_percentile"),
            presentation=results.get("presentation"),
            presentation_percentile=results.get("presentation_percentile"),
            contribution=results.get("contribution"),
            contribution_percentile=results.get("contribution_percentile"),
            accept_probability=accept_cal,
            model_confidence=0.5,
        )

    def get_percentile(self, score: float, dimension: str) -> float:
        """What percentile does this score fall at in the training distribution?"""
        dist = self._train_distributions.get(dimension, [])
        if not dist:
            return 50.0
        count_below = sum(1 for v in dist if v <= score)
        return round(100.0 * count_below / len(dist), 1)

    def save(self, path: Path) -> None:
        """Save calibrator to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({
                "calibrators": self._calibrators,
                "distributions": self._train_distributions,
            }, f)

    @classmethod
    def load(cls, path: Path) -> ScoreCalibrator:
        """Load calibrator from disk."""
        cal = cls.__new__(cls)
        cal._calibrators = {}
        cal._train_distributions = {}
        with open(path, "rb") as f:
            data = pickle.load(f)
        cal._calibrators = data.get("calibrators", {})
        cal._train_distributions = data.get("distributions", {})
        return cal

"""Load a trained reward model and predict scores for new papers."""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

try:
    import torch

    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


class RawPredictions(BaseModel):
    """Raw model output before calibration."""

    overall: float = 0.5
    soundness: float = 0.5
    presentation: float = 0.5
    contribution: float = 0.5
    accept_prob: float = 0.5


class RewardModelInference:
    """Load checkpoint and predict scores for new papers."""

    def __init__(self, model_dir: Path, device: str = "auto"):
        if not HAS_TORCH:
            raise ImportError("torch required: pip install torch transformers")

        self._device = self._resolve_device(device)
        self._model = None
        self._model_dir = model_dir

    def load(self, backbone: str = "allenai/specter2", dropout: float = 0.1) -> None:
        """Load model from checkpoint."""
        from papercheck.reward_model.model import PaperRewardModel

        checkpoint_path = self._model_dir / "checkpoint_best.pt"
        if not checkpoint_path.exists():
            raise FileNotFoundError(f"No checkpoint at {checkpoint_path}")

        self._model = PaperRewardModel(backbone=backbone, dropout=dropout)
        state_dict = torch.load(checkpoint_path, map_location=self._device, weights_only=True)
        self._model.load_state_dict(state_dict)
        self._model.to(self._device)
        self._model.eval()
        logger.info("Loaded reward model from %s", checkpoint_path)

    def predict(self, features) -> RawPredictions:
        """Predict review scores for a single paper."""
        if self._model is None:
            raise RuntimeError("Model not loaded — call load() first")

        with torch.no_grad():
            input_ids = torch.tensor([features.input_ids], dtype=torch.long).to(self._device)
            attention_mask = torch.tensor([features.attention_mask], dtype=torch.long).to(self._device)
            structural = torch.tensor([features.structural_features], dtype=torch.float).to(self._device)

            outputs = self._model(input_ids, attention_mask, structural)

        return RawPredictions(
            overall=outputs["overall"].item(),
            soundness=outputs["soundness"].item(),
            presentation=outputs["presentation"].item(),
            contribution=outputs["contribution"].item(),
            accept_prob=outputs["accept_prob"].item(),
        )

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def _resolve_device(self, device: str) -> str:
        if device == "auto":
            if torch.cuda.is_available():
                return "cuda"
            if torch.backends.mps.is_available():
                return "mps"
            return "cpu"
        return device

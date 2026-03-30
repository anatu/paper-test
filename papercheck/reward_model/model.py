"""Multi-head regression model for predicting peer review scores."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn
    from transformers import AutoModel

    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

# Number of structural features concatenated to [CLS] embedding
N_STRUCTURAL_FEATURES = 10
ENCODER_DIM = 768  # SPECTER2 / SciBERT hidden size
SHARED_DIM = 256
DIMENSIONS = ["overall", "soundness", "presentation", "contribution", "accept_prob"]


def _check_torch():
    if not HAS_TORCH:
        raise ImportError("torch and transformers required: pip install torch transformers")


class PaperRewardModel(nn.Module if HAS_TORCH else object):
    """Multi-head regression model predicting peer review scores.

    Architecture:
        Paper text -> SPECTER2 encoder -> [CLS] (768-d)
        Concat with structural features (10-d) -> 778-d
        Shared projection: Linear(778, 256) + ReLU + Dropout
        Per-dimension heads: Linear(256, 1) + Sigmoid -> [0, 1]
    """

    def __init__(self, backbone: str = "allenai/specter2", dropout: float = 0.1):
        _check_torch()
        super().__init__()
        self.encoder = AutoModel.from_pretrained(backbone)
        encoder_dim = self.encoder.config.hidden_size

        self.projection = nn.Sequential(
            nn.Linear(encoder_dim + N_STRUCTURAL_FEATURES, SHARED_DIM),
            nn.ReLU(),
            nn.Dropout(dropout),
        )

        self.overall_head = nn.Sequential(nn.Linear(SHARED_DIM, 1), nn.Sigmoid())
        self.soundness_head = nn.Sequential(nn.Linear(SHARED_DIM, 1), nn.Sigmoid())
        self.presentation_head = nn.Sequential(nn.Linear(SHARED_DIM, 1), nn.Sigmoid())
        self.contribution_head = nn.Sequential(nn.Linear(SHARED_DIM, 1), nn.Sigmoid())
        self.accept_head = nn.Sequential(nn.Linear(SHARED_DIM, 1), nn.Sigmoid())

    def forward(self, input_ids, attention_mask, structural_features):
        encoder_output = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        cls_embedding = encoder_output.last_hidden_state[:, 0, :]
        combined = torch.cat([cls_embedding, structural_features], dim=-1)
        shared = self.projection(combined)
        return {
            "overall": self.overall_head(shared),
            "soundness": self.soundness_head(shared),
            "presentation": self.presentation_head(shared),
            "contribution": self.contribution_head(shared),
            "accept_prob": self.accept_head(shared),
        }


class MultiTaskLoss(nn.Module if HAS_TORCH else object):
    """Weighted multi-task loss with masking for missing dimensions."""

    def __init__(self, weights: dict[str, float] | None = None):
        _check_torch()
        super().__init__()
        self.weights = weights or {
            "overall": 2.0,
            "soundness": 1.0,
            "presentation": 1.0,
            "contribution": 1.0,
            "accept_prob": 1.5,
        }
        self.mse = nn.MSELoss(reduction="none")
        self.bce = nn.BCELoss(reduction="none")

    def forward(self, predictions: dict, labels: dict) -> torch.Tensor:
        total_loss = torch.tensor(0.0, device=next(iter(predictions.values())).device)

        for dim in ["overall", "soundness", "presentation", "contribution"]:
            pred = predictions[dim].squeeze(-1)
            target = labels.get(dim)
            if target is None:
                continue
            mask = ~torch.isnan(target)
            if mask.sum() == 0:
                continue
            loss = self.mse(pred[mask], target[mask]).mean()
            total_loss = total_loss + self.weights.get(dim, 1.0) * loss

        # Binary cross-entropy for accept probability
        pred_accept = predictions["accept_prob"].squeeze(-1)
        target_accept = labels.get("accept_prob")
        if target_accept is not None:
            mask = ~torch.isnan(target_accept)
            if mask.sum() > 0:
                loss = self.bce(pred_accept[mask], target_accept[mask]).mean()
                total_loss = total_loss + self.weights.get("accept_prob", 1.5) * loss

        return total_loss

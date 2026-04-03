"""Training loop for the peer-review reward model."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

try:
    import torch
    from torch.utils.data import DataLoader, Dataset

    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


class TrainingConfig(BaseModel):
    """Training hyperparameters — loaded from YAML config files."""

    backbone: str = "allenai/specter2"
    max_length: int = 512
    batch_size: int = 16
    gradient_accumulation_steps: int = 2
    learning_rate: float = 2e-5
    weight_decay: float = 0.01
    warmup_ratio: float = 0.1
    lr_scheduler: str = "cosine"
    num_epochs: int = 10
    patience: int = 3
    dropout: float = 0.1
    loss_weights: dict[str, float] = Field(default_factory=lambda: {
        "overall": 2.0, "soundness": 1.0, "presentation": 1.0,
        "contribution": 1.0, "accept_prob": 1.5,
    })
    freeze_encoder: bool = False
    encoder_lr: float | None = None  # If set, use this LR for encoder; main LR for heads
    device: str = "auto"
    seed: int = 42
    output_dir: str = "models/reward_model"
    data_dir: str = "data/openreview/processed"

    @classmethod
    def from_yaml(cls, path: str | Path) -> TrainingConfig:
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)


class TrainingResult(BaseModel):
    """Summary of a completed training run."""

    best_epoch: int = 0
    best_val_loss: float = float("inf")
    final_test_metrics: dict[str, float] = Field(default_factory=dict)
    total_epochs: int = 0
    early_stopped: bool = False


class PaperDataset(Dataset if HAS_TORCH else object):
    """PyTorch dataset wrapping extracted paper features."""

    def __init__(self, features_list: list):
        self._features = features_list

    def __len__(self):
        return len(self._features)

    def __getitem__(self, idx):
        f = self._features[idx]
        labels = f.labels
        label_dict = {
            "overall": labels.overall_rating,
            "soundness": labels.soundness,
            "presentation": labels.presentation,
            "contribution": labels.contribution,
            "accept_prob": labels.accept_probability,
        }
        # Replace None with NaN for masking in loss
        for k, v in label_dict.items():
            if v is None:
                label_dict[k] = float("nan")

        return {
            "input_ids": torch.tensor(f.input_ids, dtype=torch.long),
            "attention_mask": torch.tensor(f.attention_mask, dtype=torch.long),
            "structural_features": torch.tensor(f.structural_features, dtype=torch.float),
            "labels": {k: torch.tensor(v, dtype=torch.float) for k, v in label_dict.items()},
        }


class RewardModelTrainer:
    """Training loop with early stopping and checkpoint management."""

    def __init__(self, config: TrainingConfig):
        if not HAS_TORCH:
            raise ImportError("torch required: pip install torch transformers")
        self.config = config
        self.device = self._resolve_device(config.device)

    def train(self, train_features: list, val_features: list) -> TrainingResult:
        """Full training run."""
        from papercheck.reward_model.model import MultiTaskLoss, PaperRewardModel

        torch.manual_seed(self.config.seed)

        model = PaperRewardModel(
            backbone=self.config.backbone,
            dropout=self.config.dropout,
            freeze_encoder=self.config.freeze_encoder,
        ).to(self.device)

        # Discriminative learning rates: lower LR for pretrained encoder,
        # higher LR for randomly-initialized projection + heads.
        if self.config.encoder_lr is not None and not self.config.freeze_encoder:
            encoder_params = list(model.encoder.parameters())
            head_params = [p for n, p in model.named_parameters() if not n.startswith("encoder.")]
            param_groups = [
                {"params": encoder_params, "lr": self.config.encoder_lr},
                {"params": head_params, "lr": self.config.learning_rate},
            ]
        else:
            param_groups = [{"params": [p for p in model.parameters() if p.requires_grad]}]

        optimizer = torch.optim.AdamW(
            param_groups,
            lr=self.config.learning_rate,
            weight_decay=self.config.weight_decay,
        )
        loss_fn = MultiTaskLoss(self.config.loss_weights)

        train_loader = DataLoader(
            PaperDataset(train_features),
            batch_size=self.config.batch_size,
            shuffle=True,
        )
        val_loader = DataLoader(
            PaperDataset(val_features),
            batch_size=self.config.batch_size,
        )

        best_val_loss = float("inf")
        best_epoch = 0
        patience_counter = 0
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        log_path = output_dir / "training_log.jsonl"

        for epoch in range(self.config.num_epochs):
            # Train
            model.train()
            train_loss = 0.0
            n_batches = 0
            for batch in train_loader:
                batch = {k: _to_device(v, self.device) for k, v in batch.items()}
                preds = model(
                    batch["input_ids"],
                    batch["attention_mask"],
                    batch["structural_features"],
                )
                loss = loss_fn(preds, batch["labels"])
                loss.backward()

                if (n_batches + 1) % self.config.gradient_accumulation_steps == 0:
                    optimizer.step()
                    optimizer.zero_grad()

                train_loss += loss.item()
                n_batches += 1

            avg_train_loss = train_loss / max(n_batches, 1)

            # Validate
            model.eval()
            val_loss = 0.0
            n_val = 0
            with torch.no_grad():
                for batch in val_loader:
                    batch = {k: _to_device(v, self.device) for k, v in batch.items()}
                    preds = model(
                        batch["input_ids"],
                        batch["attention_mask"],
                        batch["structural_features"],
                    )
                    loss = loss_fn(preds, batch["labels"])
                    val_loss += loss.item()
                    n_val += 1

            avg_val_loss = val_loss / max(n_val, 1)

            # Log
            log_entry = {
                "epoch": epoch + 1,
                "train_loss": round(avg_train_loss, 6),
                "val_loss": round(avg_val_loss, 6),
            }
            with open(log_path, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
            logger.info("Epoch %d: train=%.4f val=%.4f", epoch + 1, avg_train_loss, avg_val_loss)

            # Checkpoint
            if avg_val_loss < best_val_loss:
                best_val_loss = avg_val_loss
                best_epoch = epoch + 1
                patience_counter = 0
                torch.save(model.state_dict(), output_dir / "checkpoint_best.pt")
            else:
                patience_counter += 1
                if patience_counter >= self.config.patience:
                    logger.info("Early stopping at epoch %d", epoch + 1)
                    break

        return TrainingResult(
            best_epoch=best_epoch,
            best_val_loss=best_val_loss,
            total_epochs=epoch + 1,
            early_stopped=patience_counter >= self.config.patience,
        )

    def _resolve_device(self, device: str) -> str:
        if device == "auto":
            if torch.cuda.is_available():
                return "cuda"
            if torch.backends.mps.is_available():
                return "mps"
            return "cpu"
        return device


def _to_device(v, device: str):
    """Recursively move tensors or dicts of tensors to device."""
    if isinstance(v, dict):
        return {k: _to_device(val, device) for k, val in v.items()}
    if hasattr(v, "to"):
        return v.to(device)
    return v

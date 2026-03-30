"""Convert processed papers into model input features."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from papercheck.reward_model.data_processing import ConsensusLabels, ProcessedPaper

logger = logging.getLogger(__name__)

# Optional imports
try:
    import torch
    from transformers import AutoTokenizer

    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


class PaperFeatures(BaseModel):
    """Model input features for one paper."""

    input_ids: list[int] = Field(default_factory=list)
    attention_mask: list[int] = Field(default_factory=list)
    structural_features: list[float] = Field(default_factory=list)
    labels: ConsensusLabels = Field(default_factory=ConsensusLabels)


@dataclass
class NormStats:
    """Normalization statistics for structural features."""

    means: list[float] = field(default_factory=list)
    stds: list[float] = field(default_factory=list)


class PaperFeatureExtractor:
    """Converts processed papers into model input tensors."""

    def __init__(self, backbone: str = "allenai/specter2", max_length: int = 512):
        if not HAS_TORCH:
            raise ImportError("torch and transformers required: pip install torch transformers")
        self._tokenizer = AutoTokenizer.from_pretrained(backbone)
        self._max_length = max_length
        self._norm_stats: NormStats | None = None

    def extract(self, paper: ProcessedPaper) -> PaperFeatures:
        """Extract features for a single paper."""
        # Text features: abstract + intro/conclusion if available
        text = paper.abstract
        if paper.sections:
            intro = paper.sections.get("introduction", "")
            conclusion = paper.sections.get("conclusion", "")
            if intro:
                text += " " + intro
            if conclusion:
                text += " " + conclusion

        encoding = self._tokenizer(
            text,
            max_length=self._max_length,
            truncation=True,
            padding="max_length",
            return_attention_mask=True,
        )

        structural = self._extract_structural(paper)
        if self._norm_stats:
            structural = self._normalize(structural)

        return PaperFeatures(
            input_ids=encoding["input_ids"],
            attention_mask=encoding["attention_mask"],
            structural_features=structural,
            labels=paper.labels,
        )

    def batch_extract(self, papers: list[ProcessedPaper]) -> list[PaperFeatures]:
        """Extract features for a batch of papers."""
        return [self.extract(p) for p in papers]

    def compute_normalization_stats(self, papers: list[ProcessedPaper]) -> NormStats:
        """Compute mean/std for structural features on training set."""
        all_features = [self._extract_structural(p) for p in papers]
        n_features = len(all_features[0]) if all_features else 0
        means = []
        stds = []
        for i in range(n_features):
            vals = [f[i] for f in all_features]
            mean = sum(vals) / len(vals) if vals else 0.0
            var = sum((v - mean) ** 2 for v in vals) / len(vals) if vals else 1.0
            std = var ** 0.5 if var > 0 else 1.0
            means.append(mean)
            stds.append(std)
        self._norm_stats = NormStats(means=means, stds=stds)
        return self._norm_stats

    def set_norm_stats(self, stats: NormStats) -> None:
        self._norm_stats = stats

    def _extract_structural(self, paper: ProcessedPaper) -> list[float]:
        """Extract structural features from a paper."""
        text = paper.full_text or paper.abstract
        tokens = len(text.split())
        n_refs = text.lower().count("\\cite{") + text.lower().count("[")
        n_figures = text.lower().count("\\begin{figure")
        n_tables = text.lower().count("\\begin{table")
        n_equations = text.lower().count("\\begin{equation")
        has_code = 1.0 if ("github.com" in text or "gitlab.com" in text) else 0.0
        citation_density = (n_refs / max(tokens, 1)) * 1000

        return [
            float(tokens),
            float(n_refs),
            float(n_figures),
            float(n_tables),
            float(n_equations),
            0.0,  # methods_to_results_ratio (placeholder)
            citation_density,
            has_code,
            0.0,  # num_empirical_claims (placeholder)
            0.0,  # padding
        ]

    def _normalize(self, features: list[float]) -> list[float]:
        """Zero-mean, unit-variance normalization."""
        if not self._norm_stats:
            return features
        return [
            (f - m) / s if s > 0 else 0.0
            for f, m, s in zip(features, self._norm_stats.means, self._norm_stats.stds)
        ]

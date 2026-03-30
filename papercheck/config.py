"""Pipeline configuration — loaded from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field


class PipelineConfig(BaseModel):
    """Global pipeline configuration."""

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    s2_api_key: str | None = None
    grobid_url: str = "http://localhost:8070"
    cache_dir: Path = Path(".papercheck_cache")
    cache_ttl_hours: int = 168  # 1 week
    layer_weights: dict[int, float] = Field(
        default_factory=lambda: {1: 0.30, 2: 0.25, 3: 0.20, 4: 0.15, 5: 0.10}
    )
    fail_thresholds: dict[int, float] = Field(
        default_factory=lambda: {1: 0.3, 2: 0.3, 3: 0.2, 4: 0.2, 5: 0.2}
    )
    warn_thresholds: dict[int, float] = Field(
        default_factory=lambda: {1: 0.6, 2: 0.6, 3: 0.5, 4: 0.5, 5: 0.5}
    )
    halt_on_fail: bool = True
    max_concurrent_api_calls: int = 5
    docker_timeout_seconds: int = 300

    @classmethod
    def from_env(cls) -> PipelineConfig:
        """Build config from environment variables."""
        return cls(
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            s2_api_key=os.environ.get("S2_API_KEY"),
        )

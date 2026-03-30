"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from papercheck.config import PipelineConfig


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def sample_clean_tex() -> Path:
    return FIXTURES_DIR / "sample_clean.tex"


@pytest.fixture
def sample_dangling_ref_tex() -> Path:
    return FIXTURES_DIR / "sample_dangling_ref.tex"


@pytest.fixture
def sample_statbug_tex() -> Path:
    return FIXTURES_DIR / "sample_statbug.tex"


@pytest.fixture
def sample_overclaim_tex() -> Path:
    return FIXTURES_DIR / "sample_overclaim.tex"


@pytest.fixture
def default_config() -> PipelineConfig:
    """Config without a real API key — LLM-based checks degrade gracefully."""
    return PipelineConfig(anthropic_api_key="")

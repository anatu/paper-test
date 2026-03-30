"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from papercheck.config import PipelineConfig


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _block_network(request, monkeypatch):
    """Block outbound HTTP in all tests unless marked @pytest.mark.live.

    This ensures the CI test suite never makes real network calls.
    Layer 2/3/4 degrade gracefully when connections fail.
    """
    if "live" in [m.name for m in request.node.iter_markers()]:
        return  # Allow network for tests explicitly marked as live

    import httpx

    def _blocked_request(*args, **kwargs):
        raise httpx.ConnectError("Network blocked in tests (use @pytest.mark.live to allow)")

    monkeypatch.setattr("httpx.Client.send", _blocked_request)
    monkeypatch.setattr("httpx.AsyncClient.send", _blocked_request)


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
def sample_hallucinated_cite_tex() -> Path:
    return FIXTURES_DIR / "sample_hallucinated_cite.tex"


@pytest.fixture
def sample_misattribution_tex() -> Path:
    return FIXTURES_DIR / "sample_misattribution.tex"


@pytest.fixture
def sample_good_citations_tex() -> Path:
    return FIXTURES_DIR / "sample_good_citations.tex"


@pytest.fixture
def default_config() -> PipelineConfig:
    """Config without a real API key — LLM-based checks degrade gracefully."""
    return PipelineConfig(anthropic_api_key="")

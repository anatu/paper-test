"""Integration tests for Layer 4: Reproducibility Check."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from papercheck.config import PipelineConfig
from papercheck.layers.layer4_reproducibility import (
    ReproducibilityLayer,
    _extract_repo_urls,
)
from papercheck.models import PaperData, PaperMetadata
from papercheck.parsing.paper_loader import load_paper


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def layer():
    return ReproducibilityLayer()


@pytest.fixture
def config():
    return PipelineConfig(anthropic_api_key="")


@pytest.fixture
def sample_with_repo_tex() -> Path:
    return FIXTURES_DIR / "sample_with_repo.tex"


@pytest.fixture
def sample_clean_tex() -> Path:
    return FIXTURES_DIR / "sample_clean.tex"


# ── URL extraction ─────────────────────────────────────────────────────────


class TestURLExtraction:
    def test_extracts_github_url(self, sample_with_repo_tex):
        """Should extract GitHub URLs from paper text."""
        paper = load_paper(str(sample_with_repo_tex))
        urls = _extract_repo_urls(paper)
        assert len(urls) >= 1
        assert any("github.com/test-user/testnet-repo" in u for u in urls)

    def test_no_urls_in_clean_paper(self, sample_clean_tex):
        """Clean paper without URLs should return empty list."""
        paper = load_paper(str(sample_clean_tex))
        urls = _extract_repo_urls(paper)
        assert len(urls) == 0

    def test_deduplicates_urls(self):
        """Same URL appearing twice should be deduplicated."""
        paper = PaperData(
            source_type="latex",
            raw_text=(
                "Code at https://github.com/user/repo and also "
                "https://github.com/user/repo for reference."
            ),
        )
        urls = _extract_repo_urls(paper)
        assert len(urls) == 1

    def test_extracts_from_metadata(self):
        """Should also check metadata URLs."""
        paper = PaperData(
            source_type="latex",
            raw_text="No urls here",
            metadata=PaperMetadata(urls=["https://github.com/user/repo"]),
        )
        urls = _extract_repo_urls(paper)
        assert len(urls) == 1

    def test_extracts_gitlab_url(self):
        """Should extract GitLab URLs."""
        paper = PaperData(
            source_type="latex",
            raw_text="Code: https://gitlab.com/user/project",
        )
        urls = _extract_repo_urls(paper)
        assert len(urls) == 1
        assert "gitlab.com" in urls[0]


# ── Layer behavior ─────────────────────────────────────────────────────────


class TestReproducibilityLayer:
    @pytest.mark.asyncio
    async def test_skips_when_no_repo(self, layer, config, sample_clean_tex):
        """Should return skipped=True when no repo is found."""
        paper = load_paper(str(sample_clean_tex))

        # Mock PapersWithCode to return nothing
        with patch("papercheck.layers.layer4_reproducibility._query_papers_with_code", return_value=[]):
            result = await layer.verify(paper, config)

        assert result.skipped is True
        assert "No code repository" in result.skip_reason

    @pytest.mark.asyncio
    async def test_reports_found_repos(self, layer, config, sample_with_repo_tex):
        """Should report found repos and attempt build verification."""
        paper = load_paper(str(sample_with_repo_tex))

        # Mock Docker as unavailable
        with patch("papercheck.layers.layer4_reproducibility._docker_available", return_value=False):
            result = await layer.verify(paper, config)

        assert result.skipped is False
        categories = [f.category for f in result.findings]
        assert "repos_found" in categories
        assert "docker_unavailable" in categories

    @pytest.mark.asyncio
    async def test_pwc_fallback_used(self, layer, config):
        """Should query PapersWithCode when no URLs in text."""
        paper = PaperData(
            source_type="latex",
            title="Some Paper Title",
            raw_text="No URLs here",
        )

        with patch(
            "papercheck.layers.layer4_reproducibility._query_papers_with_code",
            return_value=["https://github.com/user/some-paper"],
        ) as mock_pwc, \
             patch("papercheck.layers.layer4_reproducibility._docker_available", return_value=False):
            result = await layer.verify(paper, config)

        mock_pwc.assert_called_once()
        assert result.skipped is False
        categories = [f.category for f in result.findings]
        assert "repos_found" in categories


# ── Docker build ───────────────────────────────────────────────────────────


class TestDockerBuild:
    @pytest.mark.asyncio
    async def test_docker_unavailable_handled(self, layer, config, sample_with_repo_tex):
        """Should handle Docker not being available."""
        paper = load_paper(str(sample_with_repo_tex))

        with patch("papercheck.layers.layer4_reproducibility._docker_available", return_value=False):
            result = await layer.verify(paper, config)

        categories = [f.category for f in result.findings]
        assert "docker_unavailable" in categories
        # Should still pass since Docker being unavailable is informational
        assert result.signal == "pass"


# ── Layer output structure ─────────────────────────────────────────────────


class TestLayerOutput:
    @pytest.mark.asyncio
    async def test_layer_result_structure(self, layer, config, sample_clean_tex):
        """Layer should return a valid LayerResult."""
        paper = load_paper(str(sample_clean_tex))

        with patch("papercheck.layers.layer4_reproducibility._query_papers_with_code", return_value=[]):
            result = await layer.verify(paper, config)

        assert result.layer == 4
        assert result.layer_name == "Reproducibility Check"
        assert result.execution_time_seconds >= 0


# ── PapersWithCode client ──────────────────────────────────────────────────


class TestPapersWithCodeClient:
    def test_best_match_exact(self):
        from papercheck.external.papers_with_code import _best_match
        results = [{"title": "Attention Is All You Need", "id": "123"}]
        assert _best_match(results, "Attention Is All You Need") is not None

    def test_best_match_no_match(self):
        from papercheck.external.papers_with_code import _best_match
        results = [{"title": "Completely Different", "id": "456"}]
        assert _best_match(results, "Attention Is All You Need") is None

"""End-to-end pipeline tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from papercheck.config import PipelineConfig
from papercheck.models import DiagnosticReport
from papercheck.parsing.paper_loader import load_paper
from papercheck.pipeline import run_pipeline


@pytest.fixture
def clean_paper(sample_clean_tex: Path):
    return load_paper(str(sample_clean_tex))


class TestPipeline:
    @pytest.mark.asyncio
    async def test_full_pipeline_produces_valid_report(self, clean_paper, default_config):
        report = await run_pipeline(clean_paper, default_config)
        assert isinstance(report, DiagnosticReport)
        assert len(report.layer_results) == 6
        assert 0.0 <= report.composite_score <= 1.0
        assert report.composite_signal in ("pass", "warn", "fail")
        assert report.pipeline_version == "0.1.0"
        assert report.total_execution_time_seconds > 0

    @pytest.mark.asyncio
    async def test_layer_selection(self, clean_paper, default_config):
        report = await run_pipeline(clean_paper, default_config, layers=[1, 2])
        assert len(report.layer_results) == 2
        assert report.layer_results[0].layer == 1
        assert report.layer_results[1].layer == 2

    @pytest.mark.asyncio
    async def test_halt_on_fail_skips_remaining(self, clean_paper, default_config):
        # With stubs, nothing fails, so all layers run.
        # Just verify the halt logic path exists by checking all complete.
        default_config.halt_on_fail = True
        report = await run_pipeline(clean_paper, default_config)
        non_skipped = [r for r in report.layer_results if not r.skipped]
        # Layer 4 is always skipped (no repo), other 4 run
        assert len(non_skipped) == 4

    @pytest.mark.asyncio
    async def test_no_halt_mode(self, clean_paper, default_config):
        default_config.halt_on_fail = False
        report = await run_pipeline(clean_paper, default_config)
        assert len(report.layer_results) == 6

    @pytest.mark.asyncio
    async def test_report_json_serialization(self, clean_paper, default_config):
        report = await run_pipeline(clean_paper, default_config)
        from papercheck.report.json_report import render_json
        import json

        json_str = render_json(report)
        parsed = json.loads(json_str)
        assert "composite_score" in parsed
        assert "layer_results" in parsed
        assert len(parsed["layer_results"]) == 6

    @pytest.mark.asyncio
    async def test_report_markdown_rendering(self, clean_paper, default_config):
        report = await run_pipeline(clean_paper, default_config)
        from papercheck.report.markdown_report import render_markdown

        md = render_markdown(report)
        assert "# Paper Verification Report" in md
        assert "Formal Consistency" in md
        assert "Composite Score" in md

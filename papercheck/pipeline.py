"""Pipeline orchestrator — runs verification layers sequentially."""

from __future__ import annotations

import asyncio
import time

from papercheck.config import PipelineConfig
from papercheck.layers import ALL_LAYERS
from papercheck.layers.base import VerificationLayer
from papercheck.models import DiagnosticReport, LayerResult, PaperData
from papercheck.scoring.composite import generate_report


async def run_pipeline(
    paper: PaperData,
    config: PipelineConfig,
    layers: list[int] | None = None,
) -> DiagnosticReport:
    """Run the verification pipeline on a paper.

    Args:
        paper: Parsed paper data.
        config: Pipeline configuration.
        layers: Optional list of layer numbers to run (default: all).

    Returns:
        A complete DiagnosticReport.
    """
    start = time.time()
    active_layers = _select_layers(layers)
    results: list[LayerResult] = []

    for layer in active_layers:
        result = await layer.verify(paper, config)
        results.append(result)

        if config.halt_on_fail and result.signal == "fail" and not result.skipped:
            # Halt — mark remaining layers as skipped
            for remaining in active_layers[active_layers.index(layer) + 1 :]:
                results.append(
                    LayerResult(
                        layer=remaining.layer_number,
                        layer_name=remaining.layer_name,
                        score=0.0,
                        signal="fail",
                        skipped=True,
                        skip_reason=f"Halted: Layer {layer.layer_number} failed",
                    )
                )
            break

    total_time = time.time() - start
    return generate_report(paper, results, config, total_time)


def _select_layers(layer_numbers: list[int] | None) -> list[VerificationLayer]:
    """Filter and order layers by number."""
    if layer_numbers is None:
        return list(ALL_LAYERS)
    selected = [l for l in ALL_LAYERS if l.layer_number in layer_numbers]
    return sorted(selected, key=lambda l: l.layer_number)

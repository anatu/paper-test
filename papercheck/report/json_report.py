"""Structured JSON diagnostic output."""

from __future__ import annotations

from papercheck.models import DiagnosticReport


def render_json(report: DiagnosticReport) -> str:
    """Serialize a DiagnosticReport to pretty-printed JSON."""
    return report.model_dump_json(indent=2)

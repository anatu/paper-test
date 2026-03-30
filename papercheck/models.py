"""Core data models shared across the pipeline."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PaperMetadata(BaseModel):
    """Bibliographic metadata for a paper."""

    year: int | None = None
    venue: str | None = None
    doi: str | None = None
    urls: list[str] = Field(default_factory=list)


class Section(BaseModel):
    """A section of a paper."""

    heading: str
    level: int  # 1=section, 2=subsection, etc.
    text: str
    label: str | None = None


class CitationContext(BaseModel):
    """A single in-text usage of a citation."""

    section: str
    surrounding_text: str
    claim_text: str | None = None


class Reference(BaseModel):
    """A bibliography entry."""

    key: str
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    doi: str | None = None
    raw_text: str = ""
    in_text_contexts: list[CitationContext] = Field(default_factory=list)


class FigureRef(BaseModel):
    """A figure reference extracted from the paper."""

    label: str | None = None
    caption: str = ""
    page: int | None = None


class TableRef(BaseModel):
    """A table reference extracted from the paper."""

    label: str | None = None
    caption: str = ""
    content: str | None = None
    page: int | None = None


class EquationRef(BaseModel):
    """A labeled equation extracted from the paper."""

    label: str | None = None
    raw_latex: str = ""
    text: str = ""


class PaperData(BaseModel):
    """Unified representation of a parsed paper."""

    source_type: Literal["arxiv", "pdf", "latex"]
    arxiv_id: str | None = None
    title: str = ""
    authors: list[str] = Field(default_factory=list)
    abstract: str = ""
    sections: list[Section] = Field(default_factory=list)
    raw_text: str = ""
    references: list[Reference] = Field(default_factory=list)
    figures: list[FigureRef] = Field(default_factory=list)
    tables: list[TableRef] = Field(default_factory=list)
    equations: list[EquationRef] = Field(default_factory=list)
    latex_source: str | None = None
    tei_xml: str | None = None
    metadata: PaperMetadata = Field(default_factory=PaperMetadata)


class Finding(BaseModel):
    """A single diagnostic finding from a verification layer."""

    severity: Literal["info", "warning", "error", "critical"]
    category: str
    message: str
    location: str | None = None
    evidence: str | None = None
    suggestion: str | None = None


class LayerResult(BaseModel):
    """Output from a single verification layer."""

    layer: int
    layer_name: str
    score: float  # 0.0-1.0
    signal: Literal["pass", "warn", "fail"]
    findings: list[Finding] = Field(default_factory=list)
    execution_time_seconds: float = 0.0
    skipped: bool = False
    skip_reason: str | None = None


class DiagnosticReport(BaseModel):
    """Complete pipeline output."""

    paper: PaperMetadata
    title: str = ""
    authors: list[str] = Field(default_factory=list)
    layer_results: list[LayerResult] = Field(default_factory=list)
    composite_score: float = 0.0
    composite_signal: Literal["pass", "warn", "fail"] = "pass"
    scoring_weights: dict[int, float] = Field(default_factory=dict)
    timestamp: str = ""
    pipeline_version: str = ""
    total_execution_time_seconds: float = 0.0
    total_llm_cost_usd: float = 0.0

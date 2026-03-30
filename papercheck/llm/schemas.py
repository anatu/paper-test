"""Pydantic models for LLM output structures."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EmpiricalClaim(BaseModel):
    claim_text: str
    claim_type: Literal["performance", "comparison", "existence", "causal"]
    quantitative: bool = False
    metric: str | None = None
    value: str | None = None
    dataset: str | None = None


class ClaimExtractionResult(BaseModel):
    stated_contributions: list[str] = Field(default_factory=list)
    empirical_claims: list[EmpiricalClaim] = Field(default_factory=list)
    framing_claims: list[str] = Field(default_factory=list)


class AlignedClaim(BaseModel):
    abstract_claim: str
    conclusion_support: str | None = None
    alignment: Literal["supported", "partially_supported", "unsupported", "overclaimed"]
    explanation: str


class AlignmentResult(BaseModel):
    aligned_claims: list[AlignedClaim] = Field(default_factory=list)
    overall_assessment: Literal["consistent", "minor_gaps", "significant_overclaiming"]
    explanation: str

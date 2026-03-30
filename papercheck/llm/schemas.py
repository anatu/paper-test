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


# ── Layer 2: Citation Verification schemas ──────────────────────────────────


class CitationAlignmentResult(BaseModel):
    """LLM judgment on whether a cited paper supports the attributed claim."""

    judgment: Literal["supported", "plausible", "unverifiable", "misrepresented", "fabricated"]
    confidence: float = 0.5
    explanation: str = ""
    key_evidence: str | None = None


class MissingPaper(BaseModel):
    """A paper that should have been discussed in the related work."""

    title: str
    why_important: str
    severity: Literal["critical_omission", "should_discuss", "nice_to_have"]


class CoverageResult(BaseModel):
    """LLM assessment of related work literature coverage."""

    coverage_score: float = 0.5
    missing_important: list[MissingPaper] = Field(default_factory=list)
    reasonable_coverage: bool = True
    explanation: str = ""


# ── Layer 3: Cross-Paper Consistency schemas ────────────────────────────────


class ContradictionResult(BaseModel):
    """LLM judgment on whether two claims contradict each other."""

    relationship: Literal["contradicts", "tensions", "compatible", "unrelated"]
    confidence: float = 0.5
    explanation: str = ""


# ── Layer 5: Logical Structure schemas ──────────────────────────────────────


class HypothesisExperimentResult(BaseModel):
    """LLM assessment of hypothesis-experiment alignment."""

    hypothesis: str = ""
    experimental_elements: list[str] = Field(default_factory=list)
    alignment: Literal["strong", "adequate", "weak", "misaligned"]
    gaps: list[str] = Field(default_factory=list)
    explanation: str = ""


class OverclaimFinding(BaseModel):
    """A single instance of overclaiming in conclusions."""

    conclusion_claim: str
    strongest_supporting_result: str | None = None
    gap: str = ""


class ResultsConclusionResult(BaseModel):
    """LLM assessment of results-conclusion alignment."""

    overclaimed: list[OverclaimFinding] = Field(default_factory=list)
    underdiscussed_negatives: list[str] = Field(default_factory=list)
    overall: Literal["well_supported", "minor_overclaiming", "significant_overclaiming"]
    explanation: str = ""


# ── Layer 6: Peer-Review Reward Model schemas ──────────────────────────────


class ReviewerConcern(BaseModel):
    """A specific anticipated reviewer concern."""

    concern: str
    location: str | None = None
    suggestion: str | None = None
    severity: Literal["minor", "moderate", "major"] = "moderate"


class AnticipatedConcerns(BaseModel):
    """LLM-generated anticipated reviewer concerns for a dimension."""

    dimension: str = ""
    concerns: list[ReviewerConcern] = Field(default_factory=list)

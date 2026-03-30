"""Central registry of prompt templates for LLM-based analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from papercheck.llm.schemas import AlignmentResult, ClaimExtractionResult


@dataclass
class PromptSpec:
    name: str
    system: str
    user_template: str
    output_schema: type[BaseModel]
    temperature: float = 0.0
    max_tokens: int = 2048


_PROMPTS: dict[str, PromptSpec] = {}


def register_prompt(spec: PromptSpec) -> None:
    _PROMPTS[spec.name] = spec


def get_prompt(name: str) -> PromptSpec:
    if name not in _PROMPTS:
        raise KeyError(f"Unknown prompt: {name}. Registered: {list(_PROMPTS.keys())}")
    return _PROMPTS[name]


# ── Prompt: claim_extraction_abstract ────────────────────────────────────────

register_prompt(PromptSpec(
    name="claim_extraction_abstract",
    system=(
        "You are an academic paper analyst. Extract only claims that are explicitly "
        "stated by the authors about their own work — not background claims or claims "
        "attributed to other papers. Distinguish between empirical claims (testable, "
        "quantitative) and framing claims (positioning, motivation). "
        "Respond with valid JSON matching the requested schema."
    ),
    user_template=(
        "Extract the stated contributions and core claims from the following "
        "paper abstract and introduction.\n\n"
        "ABSTRACT:\n{abstract}\n\n"
        "INTRODUCTION:\n{introduction}\n\n"
        "Respond with JSON matching this schema:\n"
        '{{"stated_contributions": ["..."], '
        '"empirical_claims": [{{"claim_text": "...", "claim_type": "performance|comparison|existence|causal", '
        '"quantitative": true/false, "metric": "...", "value": "...", "dataset": "..."}}], '
        '"framing_claims": ["..."]}}'
    ),
    output_schema=ClaimExtractionResult,
    temperature=0.0,
    max_tokens=2048,
))

# ── Prompt: abstract_conclusion_alignment ────────────────────────────────────

register_prompt(PromptSpec(
    name="abstract_conclusion_alignment",
    system=(
        "You are a peer reviewer checking for overclaiming. Compare each claim "
        "in the abstract against the evidence presented in the conclusion. Quote "
        "specific text from both sections to support your judgment. "
        "Respond with valid JSON matching the requested schema."
    ),
    user_template=(
        "Check whether the abstract's claims are supported by the conclusion.\n\n"
        "ABSTRACT:\n{abstract}\n\n"
        "CONCLUSION:\n{conclusion}\n\n"
        "Respond with JSON matching this schema:\n"
        '{{"aligned_claims": [{{"abstract_claim": "...", "conclusion_support": "...", '
        '"alignment": "supported|partially_supported|unsupported|overclaimed", '
        '"explanation": "..."}}], '
        '"overall_assessment": "consistent|minor_gaps|significant_overclaiming", '
        '"explanation": "..."}}'
    ),
    output_schema=AlignmentResult,
    temperature=0.0,
    max_tokens=2048,
))

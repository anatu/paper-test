"""Central registry of prompt templates for LLM-based analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from papercheck.llm.schemas import (
    AlignmentResult,
    AnticipatedConcerns,
    CitationAlignmentResult,
    ClaimExtractionResult,
    ContradictionResult,
    CoverageResult,
    HypothesisExperimentResult,
    ResultsConclusionResult,
)


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

# ── Prompt: citation_claim_alignment ────────────────────────────────────────

register_prompt(PromptSpec(
    name="citation_claim_alignment",
    system=(
        "You are a fact-checker for academic papers. Given a citing sentence and "
        "the cited paper's abstract, determine whether the cited paper plausibly "
        "supports the claim attributed to it. If you only have the abstract, some "
        "claims may be unverifiable — flag those as 'unverifiable' rather than "
        "'misrepresented'. Respond with valid JSON matching the requested schema."
    ),
    user_template=(
        "Does the cited paper support the claim made about it?\n\n"
        "CITING SENTENCE:\n{citing_sentence}\n\n"
        "CLAIM ATTRIBUTED TO CITED PAPER:\n{claim_text}\n\n"
        "CITED PAPER TITLE:\n{cited_title}\n\n"
        "CITED PAPER ABSTRACT:\n{cited_abstract}\n\n"
        "Respond with JSON matching this schema:\n"
        '{{"judgment": "supported|plausible|unverifiable|misrepresented|fabricated", '
        '"confidence": 0.0-1.0, '
        '"explanation": "...", '
        '"key_evidence": "quote from abstract or null"}}'
    ),
    output_schema=CitationAlignmentResult,
    temperature=0.0,
    max_tokens=512,
))

# ── Prompt: related_work_coverage ───────────────────────────────────────────

register_prompt(PromptSpec(
    name="related_work_coverage",
    system=(
        "You are a senior reviewer assessing whether a paper's related work section "
        "adequately covers the relevant literature. Given the related work text and "
        "a list of recommended related papers, identify important omissions. "
        "Distinguish between critical omissions and papers that are merely nice to "
        "have. Respond with valid JSON matching the requested schema."
    ),
    user_template=(
        "Assess the literature coverage of this related work section.\n\n"
        "RELATED WORK SECTION:\n{related_work_text}\n\n"
        "RECOMMENDED RELATED PAPERS (from Semantic Scholar):\n{recommended_papers}\n\n"
        "Respond with JSON matching this schema:\n"
        '{{"coverage_score": 0.0-1.0, '
        '"missing_important": [{{"title": "...", "why_important": "...", '
        '"severity": "critical_omission|should_discuss|nice_to_have"}}], '
        '"reasonable_coverage": true/false, '
        '"explanation": "..."}}'
    ),
    output_schema=CoverageResult,
    temperature=0.2,
    max_tokens=1024,
))

# ── Prompt: contradiction_check (Layer 3) ───────────────────────────────────

register_prompt(PromptSpec(
    name="contradiction_check",
    system=(
        "You are a scientific fact-checker. Given two claims from different papers, "
        "determine whether they contradict each other, have tensions, are compatible, "
        "or are unrelated. Be precise: minor methodological differences are not "
        "contradictions. Respond with valid JSON matching the requested schema."
    ),
    user_template=(
        "Do these two claims contradict each other?\n\n"
        "CLAIM FROM PAPER UNDER REVIEW:\n{paper_claim}\n\n"
        "CLAIM FROM CORPUS PAPER:\n{corpus_claim}\n\n"
        "CONTEXT FROM PAPER UNDER REVIEW:\n{paper_context}\n\n"
        "CONTEXT FROM CORPUS PAPER:\n{corpus_context}\n\n"
        "Respond with JSON matching this schema:\n"
        '{{"relationship": "contradicts|tensions|compatible|unrelated", '
        '"confidence": 0.0-1.0, '
        '"explanation": "..."}}'
    ),
    output_schema=ContradictionResult,
    temperature=0.0,
    max_tokens=512,
))

# ── Prompt: hypothesis_experiment_alignment (Layer 5) ───────────────────────

register_prompt(PromptSpec(
    name="hypothesis_experiment_alignment",
    system=(
        "You are a methodologist reviewing an academic paper. Extract the main "
        "hypothesis or research question, then evaluate whether the experimental "
        "design (datasets, baselines, metrics, ablations) adequately tests it. "
        "Respond with valid JSON matching the requested schema."
    ),
    user_template=(
        "Evaluate whether the experiments test the stated hypothesis.\n\n"
        "ABSTRACT AND INTRODUCTION:\n{abstract_intro}\n\n"
        "METHODOLOGY:\n{methodology}\n\n"
        "Respond with JSON matching this schema:\n"
        '{{"hypothesis": "...", '
        '"experimental_elements": ["..."], '
        '"alignment": "strong|adequate|weak|misaligned", '
        '"gaps": ["..."], '
        '"explanation": "..."}}'
    ),
    output_schema=HypothesisExperimentResult,
    temperature=0.0,
    max_tokens=1024,
))

# ── Prompt: results_conclusion_alignment (Layer 5) ──────────────────────────

register_prompt(PromptSpec(
    name="results_conclusion_alignment",
    system=(
        "You are a peer reviewer checking whether the conclusions are warranted "
        "by the reported results. Identify overclaimed conclusions, underdiscussed "
        "negative results, and unjustified generalizations. "
        "Respond with valid JSON matching the requested schema."
    ),
    user_template=(
        "Are the conclusions supported by the reported results?\n\n"
        "RESULTS SECTION:\n{results}\n\n"
        "CONCLUSION SECTION:\n{conclusion}\n\n"
        "Respond with JSON matching this schema:\n"
        '{{"overclaimed": [{{"conclusion_claim": "...", '
        '"strongest_supporting_result": "...", '
        '"gap": "..."}}], '
        '"underdiscussed_negatives": ["..."], '
        '"overall": "well_supported|minor_overclaiming|significant_overclaiming", '
        '"explanation": "..."}}'
    ),
    output_schema=ResultsConclusionResult,
    temperature=0.0,
    max_tokens=1024,
))

# ── Prompt: anticipated_concerns (Layer 6) ──────────────────────────────────

register_prompt(PromptSpec(
    name="anticipated_concerns",
    system=(
        "You are an experienced peer reviewer at a top ML venue. A predictive "
        "model has identified that this paper scores in a low percentile on a "
        "specific review dimension. Based on the paper text provided, identify "
        "the 2-3 most likely specific concerns a reviewer would raise about "
        "this dimension. Be concrete — cite specific sections, claims, or "
        "missing elements. Don't be generic. "
        "Respond with valid JSON matching the requested schema."
    ),
    user_template=(
        "This paper scores in the {percentile} percentile on [{dimension}] "
        "({dimension_definition}).\n\n"
        "Predicted score: {predicted_score}\n\n"
        "RELEVANT PAPER TEXT:\n{paper_text}\n\n"
        "Identify the 2-3 most likely reviewer concerns for this dimension.\n\n"
        "Respond with JSON matching this schema:\n"
        '{{"dimension": "{dimension}", '
        '"concerns": [{{"concern": "specific issue description", '
        '"location": "section or paragraph reference", '
        '"suggestion": "concrete improvement suggestion", '
        '"severity": "minor|moderate|major"}}]}}'
    ),
    output_schema=AnticipatedConcerns,
    temperature=0.3,
    max_tokens=1024,
))

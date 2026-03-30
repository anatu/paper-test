# Annotation: sample_overclaim.tex

**Purpose**: Paper where the abstract overclaims relative to the conclusion.

## Planted error

- Abstract claims "state-of-the-art results" and "outperforms all baselines"
- Conclusion only mentions "competitive results" with caveats

## Observations

### Layer 1: Formal Consistency (1.00 PASS)
- No structural errors — the paper is well-formed
- Claim alignment check skipped (requires LLM)
- **Key limitation**: Without an LLM, overclaiming is invisible to Layer 1

### Layer 5: Logical Structure (1.00 PASS)
- Also skipped (requires LLM)
- **With API key**: Layer 5's `results_conclusion_alignment` prompt would catch the gap between abstract claims and conclusion evidence
- **With API key**: Layer 1's `abstract_conclusion_alignment` prompt would also flag this

## Weight tuning notes

- This example demonstrates why LLM-based checks are essential for catching semantic issues
- Rule-based checks (statcheck, xref) can only catch formal/structural problems
- The pipeline correctly reports what it can and skips what it can't, rather than giving false confidence

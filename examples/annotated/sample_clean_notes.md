# Annotation: sample_clean.tex

**Purpose**: Baseline — a well-formed paper with no planted errors.

## Expected behavior

- Layer 1 should pass with a perfect or near-perfect score
- Layers 2-5 should degrade gracefully without API keys

## Observations

### Layer 1: Formal Consistency (1.00 PASS)
- **Correct**: No statistical errors, no dangling references, no equation issues
- **Minor**: Reports `S` and `e` as undefined variables — these are actually defined in the inline text after the equation (`where $S$ is...`). The heuristic variable checker only looks at `\newcommand` and equation definitions, not inline prose definitions. This is a known limitation of the regex-based approach.
- **Minor**: Some labels (`sec:conclusion`, `sec:intro`) are defined but never `\ref{}`'d — accurate but low-signal

### Layer 2: Citation Verification (0.85 PASS)
- **Expected**: One "error" finding for `smith2023` — this is a fictional citation in the test fixture that genuinely doesn't exist in Semantic Scholar. The pipeline correctly flags it as unverifiable.
- **Note**: `jones2022` was found via S2, demonstrating the lookup chain works

### Layers 3-5
- All correctly skip LLM-based checks with informational messages

## Weight tuning notes

- This paper scores 0.96 composite, which is appropriate for a clean paper
- The Layer 2 false positive (fictional citation in test fixture) costs 0.15, bringing it to 0.85 — acceptable since the citation genuinely doesn't exist in any database

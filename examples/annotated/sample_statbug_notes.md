# Annotation: sample_statbug.tex

**Purpose**: Paper with planted statistical errors to test Layer 1's statcheck.

## Planted errors

1. `t(30) = 1.5, p < 0.01` — Recomputed p ~ 0.144, off by an order of magnitude
2. `F(2, 45) = 3.1, p = 0.001` — Recomputed p ~ 0.055, reported as highly significant when it's not
3. `r = 1.35` — Impossible correlation coefficient (must be in [-1, 1])

## Observations

### Layer 1: Formal Consistency (0.40 WARN)
- **All 3 errors detected**:
  - `r = 1.35` flagged as CRITICAL (impossible value) — correct severity
  - Both p-value inconsistencies flagged as ERROR with recomputed values — correct
- Score of 0.40 (WARN) is appropriate: serious issues found but paper isn't completely invalid
- The severity mapping works well: critical (-0.3) + 2 errors (-0.15 each) = 0.40

### Layer 2-5
- Correctly degrade without API keys
- Layer 2 reports a transient S2 rate limit error, handled gracefully

## Weight tuning notes

- Layer 1 score of 0.40 correctly triggers WARN (threshold 0.6)
- Composite score of 0.79 seems slightly high for a paper with critical statistical errors
- Layer 1 weight (0.30) means even a 0.40 Layer 1 score doesn't drag composite below 0.80 when other layers are 1.0
- **Recommendation**: Consider increasing Layer 1 weight to 0.35 or lowering the composite warn threshold

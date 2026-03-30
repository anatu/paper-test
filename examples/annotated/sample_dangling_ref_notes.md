# Annotation: sample_dangling_ref.tex

**Purpose**: Paper with broken cross-references to test Layer 1's xref checker.

## Planted errors

- `\ref{fig:missing}` — references a figure label that doesn't exist
- `\ref{tab:nonexistent}` — references a table label that doesn't exist
- `\cite{ghost2023}` — cites a bibliography key that doesn't exist
- Multiple other dangling references

## Observations

### Layer 1: Formal Consistency (0.25 FAIL)
- **5 errors detected**: All dangling references correctly identified
- Score of 0.25 triggers FAIL signal (below 0.3 threshold) — appropriate for a paper with this many broken references
- Each dangling reference is an ERROR (-0.15), so 5 errors = -0.75 from 1.0 = 0.25

### Layers 2-5
- Correctly degrade without API keys

## Weight tuning notes

- Layer 1 FAIL at 0.25 is correct — a paper with 5 dangling references has serious structural issues
- Composite score of 0.74 still shows as PASS because other layers are 1.0
- This highlights that `halt_on_fail` mode (default) would stop the pipeline at Layer 1, which is the right behavior for a paper this broken

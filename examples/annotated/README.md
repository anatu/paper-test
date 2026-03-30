# Annotated Pipeline Examples

This directory contains annotated output from running the `papercheck` verification pipeline on test papers. Each example includes:

- **`<name>.md`** — Full Markdown report from the pipeline
- **`<name>.json`** — Machine-readable JSON report
- **`<name>_notes.md`** — Human annotations and analysis

## Examples

| Paper | Scenario | Composite Score | Key Findings |
|-------|----------|-----------------|--------------|
| `sample_clean` | Well-formed paper, no errors | 0.96 (PASS) | Baseline: clean papers should score high |
| `sample_statbug` | Planted statistical errors | 0.79 (PASS) | Layer 1 catches inconsistent p-values and impossible correlation |
| `sample_dangling_ref` | Broken cross-references | 0.74 (PASS) | Layer 1 detects dangling \ref{} targets |
| `sample_overclaim` | Abstract-conclusion mismatch | 1.00 (PASS) | Overclaiming only detectable with LLM (Layer 1/5) |
| `sample_hallucinated_cite` | Fabricated citations | 1.00 (PASS) | Citation verification requires live S2/CrossRef APIs |

## How to regenerate

```bash
# Run pipeline on a paper
papercheck run papercheck/tests/fixtures/sample_statbug.tex --format both --output-dir examples/annotated/

# Run on all fixtures
for f in papercheck/tests/fixtures/sample_*.tex; do
  papercheck run "$f" --format both --no-halt --output-dir examples/annotated/
done
```

## Notes on offline mode

These examples were generated without API keys. In production:
- **Layer 2** would verify citations via Semantic Scholar, CrossRef, and OpenAlex
- **Layer 3** would extract and embed claims, searching a ChromaDB corpus for contradictions
- **Layer 5** would check hypothesis-experiment and results-conclusion alignment via LLM

The rule-based checks in Layer 1 (statistical audit, cross-reference integrity, math consistency) work fully offline and produce the most actionable findings in these examples.

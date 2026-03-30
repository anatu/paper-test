# Annotation: sample_hallucinated_cite.tex

**Purpose**: Paper with fabricated citations to test Layer 2's existence check.

## Planted errors

- `fakepaper2023`: "Quantum Transformers for Sentiment Analysis" by Fakerson & Nobody — doesn't exist
- `fakequantum2023`: "Quantum Advantage in Text Classification" by Zhang & Phantom — doesn't exist
- `smith2023real`: legitimate-sounding citation (used as control)

## Observations

### Layer 2: Citation Verification (1.00 PASS)
- **With live API**: Layer 2 would query Semantic Scholar for each reference title, fall back to CrossRef and OpenAlex, and flag the two fabricated citations as `citation_not_found` (ERROR)
- **Without API (this run)**: S2 rate-limited, so the existence check error was caught gracefully
- The test suite (`test_layer2.py::test_hallucinated_citation_detected`) verifies this works correctly with mocked API responses

### Layer 1: Formal Consistency (1.00 PASS)
- No structural errors — fabricated citations are structurally valid LaTeX

## Weight tuning notes

- This is the strongest argument for Layer 2 needing a real API key in production
- The mock-based tests prove the detection logic works; the annotated example shows graceful degradation
- Citation fabrication is one of the highest-value checks for catching dishonest papers

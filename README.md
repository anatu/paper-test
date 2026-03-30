# paper-test

> **This repo is a live work-in-progress.** Everything here reflects the current state of an ongoing experiment — tools may be half-built, directions may shift, and nothing should be treated as stable or production-ready.

## What this is

An experimental workspace exploring two related ideas:

1. **LLM-assisted academic paper authoring** — Can AI-assisted workflows produce publication-quality LaTeX papers, from outlining through citation management?
2. **Automated research paper verification** — Can we build a "CI/CD for research papers" that checks internal consistency, citation accuracy, and logical coherence?

Both threads share the same hypothesis: academic writing has enough structural regularity (rigid sections, formal citations, standardized reporting) to be unusually tractable for automated tooling.

## Architecture

```
paper-test/
├── papers/                  # LaTeX source files for authored papers
├── references/              # Style guides (structure, prose, citations, LaTeX)
├── data/                    # Downloaded ArXiv papers (LaTeX source)
├── plans/                   # Build plans for the verification pipeline
├── examples/annotated/      # Annotated pipeline output on test papers
├── fetch_arxiv.py           # Search and download ArXiv paper source
├── visualize_latex.py       # Local dev server: .tex → live-reloading PDF
└── papercheck/              # Verification pipeline (Python package)
    ├── cli.py               # CLI entry point
    ├── pipeline.py           # Orchestrator: runs layers sequentially
    ├── config.py             # Environment-based configuration
    ├── models.py             # Shared Pydantic data models
    ├── parsing/              # Paper loading (ArXiv, PDF, .tex)
    ├── layers/               # 5-layer verification stack
    ├── extractors/           # Content extraction (stats, claims, refs, metadata)
    ├── checkers/             # Rule-based checks (statcheck, xref, math)
    ├── external/             # API clients (Semantic Scholar, CrossRef, OpenAlex, PapersWithCode)
    ├── llm/                  # Anthropic API wrapper, prompt registry, output schemas
    ├── scoring/              # Composite scoring and report assembly
    ├── report/               # JSON and Markdown report renderers
    ├── cache/                # SQLite-backed API response cache
    └── tests/                # Test suite (94 tests, all pass without API keys)
```

## Verification pipeline

The `papercheck` pipeline takes a paper (PDF, `.tex`, or ArXiv ID) and runs it through five verification layers:

| Layer | Name | What it checks | Requires |
|-------|------|----------------|----------|
| 1 | **Formal Consistency** | Statistical audit (p-value recomputation, impossible values), cross-reference integrity, equation/variable consistency, abstract-conclusion alignment | Offline (LLM optional) |
| 2 | **Citation Verification** | Citation existence via Semantic Scholar/CrossRef/OpenAlex, claim-citation alignment, related work coverage | S2 API (LLM optional) |
| 3 | **Cross-Paper Consistency** | Claim extraction, corpus contradiction search, internal claim-value consistency | LLM + ChromaDB (optional) |
| 4 | **Reproducibility Check** | GitHub/GitLab URL extraction, PapersWithCode lookup, Docker build verification | Docker (optional) |
| 5 | **Logical Structure** | Hypothesis-experiment alignment, results-conclusion alignment, overclaiming detection | LLM |

Each layer produces findings with severity levels (info, warning, error, critical) and a 0-1 score. Scores are combined into a weighted composite:

```
Layer weights: L1=0.35, L2=0.25, L3=0.15, L4=0.10, L5=0.15
Composite: PASS (>=0.7) | WARN (>=0.4) | FAIL (<0.4)
```

Layers degrade gracefully: without API keys, LLM-based checks are skipped with informational messages. Without Docker, Layer 4 skips build verification. Without ChromaDB, Layer 3 skips corpus search.

## Setup

```bash
# Install the package
pip install -e .

# (Optional) Install corpus dependencies for Layer 3
pip install -e ".[corpus]"

# (Optional) Install dev dependencies for testing
pip install -e ".[dev]"
```

### Environment variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `ANTHROPIC_API_KEY` | For LLM checks | Powers claim alignment, hypothesis checking, overclaiming detection |
| `S2_API_KEY` | Optional | Higher Semantic Scholar rate limits (100 req/s vs 10 req/s) |

## Usage

```bash
# Verify a LaTeX paper
papercheck run papers/my_paper.tex

# Verify with specific layers only
papercheck run papers/my_paper.tex --layers 1,2

# Verify without stopping on failure
papercheck run papers/my_paper.tex --no-halt

# Output JSON and Markdown reports
papercheck run papers/my_paper.tex --format both --output-dir results/

# Verify an ArXiv paper by ID
papercheck run 2301.00001

# Cache management
papercheck cache stats
papercheck cache clear
```

### Example output

```
$ papercheck run papercheck/tests/fixtures/sample_statbug.tex --layers 1

Layer 1: Formal Consistency — 0.40 (WARN)
  !! CRITICAL  Correlation coefficient outside [-1, 1]: 1.35
  !  ERROR     Inconsistent p-value: reported p = 0.01, recomputed p ~ 0.144 from t(30) = 1.5
  !  ERROR     Inconsistent p-value: reported p = 0.001, recomputed p ~ 0.055 from F(2,45) = 3.1
```

## Paper authoring tools

- **`papers/`** — LaTeX source files for experimental papers
- **`references/`** — Style guides used as grounding context during drafting
- **`fetch_arxiv.py`** — Search and download ArXiv papers with LaTeX source
- **`visualize_latex.py`** — Local dev server: compiles `.tex` and serves a live-reloading PDF viewer

```bash
# Fetch ArXiv papers as reference material
python fetch_arxiv.py "large language models" --max 5

# View a paper with live reloading
python visualize_latex.py papers/<name>.tex
```

## Testing

The full test suite runs without API keys or network access:

```bash
python -m pytest papercheck/tests/ -v
```

94 tests covering all 5 layers, parsing, scoring, caching, and pipeline orchestration. External API calls are mocked in tests; LLM-based checks degrade gracefully to info findings.

## Annotated examples

See `examples/annotated/` for pipeline output on test papers with human annotations analyzing the results. These demonstrate what each layer catches and where the pipeline's limits are.

## Development status

| Phase | Status | Description |
|-------|--------|-------------|
| 1. Skeleton | Done | CLI, pipeline orchestration, data models, all 5 layer stubs |
| 2. Layer 1 | Done | Statistical audit, cross-refs, math consistency, claim alignment |
| 3. Layer 2 | Done | Citation verification via S2/CrossRef/OpenAlex, claim-citation alignment |
| 4. Layers 3-5 | Done | Cross-paper consistency, reproducibility, logical structure |
| 5. Polish | Done | Annotated examples, tuned weights, documentation, CI-friendly tests |

See `plans/` for the full build plans including a Layer 6 peer-review reward model design.

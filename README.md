# paper-test

> **This repo is a live work-in-progress.** Everything here reflects the current state of an ongoing experiment — tools may be half-built, directions may shift, and nothing should be treated as stable or production-ready. The README is updated as the project evolves, not ahead of it.

## What this is

An experimental workspace exploring two related ideas:

1. **LLM-assisted academic paper authoring** — Can AI-assisted workflows produce publication-quality LaTeX papers, from outlining through citation management?
2. **Automated research paper verification** — Can we build a "CI/CD for research papers" that checks internal consistency, citation accuracy, and logical coherence?

Both threads share the same hypothesis: academic writing has enough structural regularity (rigid sections, formal citations, standardized reporting) to be unusually tractable for automated tooling.

## What's here

### Paper authoring tools

- **`papers/`** — LaTeX source files for experimental papers
- **`references/`** — Style guides (structure, prose, citations, LaTeX conventions) used as grounding context during drafting
- **`fetch_arxiv.py`** — Search and download arXiv papers with LaTeX source
- **`visualize_latex.py`** — Local dev server: compiles `.tex` and serves a live-reloading PDF viewer

### Verification pipeline (`papercheck/`)

A multi-layer pipeline that takes a paper (PDF, .tex, or ArXiv ID) and runs it through verification checks. Currently in early development — see `plans/` for the full build plan.

**What works now (Phases 1-2):**
- CLI: `papercheck run <source>` produces JSON + Markdown reports
- Layer 1 (Formal Consistency): statistical audit (p-value recomputation, impossible values), cross-reference integrity, equation/variable checks, abstract-conclusion alignment
- Layers 2-5 exist as stubs

**What's next (Phases 3-5):**
- Citation verification via Semantic Scholar / CrossRef APIs
- Cross-paper consistency checking against an ArXiv corpus
- Reproducibility checks (repo detection, build verification)
- Logical structure analysis (hypothesis-experiment alignment)

### Plans

- **`plans/`** — Build plans and design docs for the verification pipeline

## Quick start

```bash
# Fetch arXiv papers as reference material
python fetch_arxiv.py "large language models" --max 5

# View a paper with live reloading
python visualize_latex.py papers/<name>.tex

# Run the verification pipeline on a paper
pip install -e .
papercheck run papers/<name>.tex
papercheck run papercheck/tests/fixtures/sample_statbug.tex --layers 1

# Run tests
python -m pytest papercheck/tests/ -v
```

## Current directions

- Building out the verification pipeline layer by layer (Phase 3: citation verification is next)
- Exploring how authoring and verification tools can feed back into each other
- Testing on real ArXiv ML/CS papers to calibrate scoring and find edge cases

## Status

Active experiment. Things change frequently. If something looks broken or incomplete, it probably is — check `plans/` for where it's headed.

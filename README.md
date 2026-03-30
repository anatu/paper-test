# paper-test

Early experiments with using LLMs to write academic research papers.

This project explores how far AI-assisted authoring can go for producing publication-quality LaTeX papers — from outlining and drafting to citation management and style enforcement. The goal is to develop reusable workflows and reference guides that make LLM-generated academic writing rigorous and venue-ready.

## What's here

- **`papers/`** — LaTeX source files for experimental papers
- **`references/`** — Curated style guides covering paper structure, prose style, citation conventions, and LaTeX best practices. These serve as grounding context for the LLM during drafting.
- **`visualize.py`** — A local dev server that compiles `.tex` files and serves a live-reloading PDF viewer in the browser

## Quick start

```bash
# View a paper with live reloading
python visualize.py papers/test_paper.tex

# Or compile manually
pdflatex -interaction=nonstopmode papers/test_paper.tex
```

## How it works

The project uses [Claude Code](https://claude.ai/code) with a custom skill that follows a structured paper-writing workflow:

1. Read reference guides for style, structure, and citation norms
2. Scope the paper (type, venue, audience)
3. Build a hierarchical outline and get approval
4. Draft iteratively, one section at a time
5. Polish — abstract last, consistent notation, citation check

The reference guides in `references/` encode lessons learned about what makes LLM-generated academic prose actually good (or at least not obviously machine-written).

## Status

This is an active experiment. Expect rough edges.

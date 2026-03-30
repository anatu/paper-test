# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Academic paper authoring workspace. Papers are written in LaTeX and stored in `papers/`. Reference guides in `references/` define style, structure, citation, and LaTeX conventions.

## Commands

- **Compile a paper:** `pdflatex -interaction=nonstopmode papers/<name>.tex` (run twice for references)
- **Full compilation with bibtex:** `pdflatex <name>.tex && bibtex <name> && pdflatex <name>.tex && pdflatex <name>.tex`
- **Live PDF viewer:** `python visualize_latex.py papers/<name>.tex [--port PORT]`
- **View existing PDF:** `python visualize_latex.py papers/<name>.pdf`
- **Fetch arXiv papers:** `python fetch_arxiv.py "<query>" --max N [--category cs.CL] [--out data/arxiv]`

## Architecture

- `papers/` — LaTeX source files for papers
- `references/` — Style guides that **must be read before drafting** (structure, style, citations, LaTeX conventions)
- `data/` — Downloaded arXiv papers (LaTeX source) for reference; `data/arxiv/manifest.tsv` tracks fetched papers
- `fetch_arxiv.py` — Search arXiv and download paper LaTeX source into `data/arxiv/<id>/`
- `visualize_latex.py` — Local dev server that compiles `.tex` and serves a live-reloading PDF viewer in browser
- `.claude/skills/` — Custom skills (e.g., `wrap-up.md` for session end-of-day checklist)

## Skills

This project uses the **academic-latex-paper** skill for writing, drafting, structuring, and revising academic research papers intended for LaTeX rendering and peer-reviewed publication.

### Trigger Conditions

Use the academic-latex-paper skill when the user mentions:
- "research paper," "academic paper," "survey paper," "literature review"
- "LaTeX paper," "conference paper," "journal submission"
- "write a paper on," or requests to structure, outline, or draft scholarly prose
- Help with abstracts, related work, methodology, citations, or academic tone
- Casual equivalents like "help me write up my findings" or "I need to publish this"

### Workflow

1. **Read references first** — always read the files in `references/` before drafting content
2. **Scope the paper** — clarify type, venue, audience, and boundaries
3. **Build the outline** — hierarchical outline with theses, lengths, and key refs; get user approval
4. **Draft iteratively** — one section at a time, pause for feedback
5. **Polish** — abstract last, consistent notation, citation check, contribution list

### Reference Files

| File | Purpose |
|------|---------|
| `references/structure.md` | Paper anatomy, section blueprints, length targets |
| `references/style.md` | Prose style, tone, vocabulary, sentence craft |
| `references/citations.md` | Citation density, placement, formatting, bibliography |
| `references/latex.md` | Document class, packages, macros, compilation |

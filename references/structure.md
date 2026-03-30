# Paper Structure Reference

## Section-by-Section Blueprint

### 1. Abstract (150–250 words)

Write this **last**. It must stand alone — a reader who reads only the abstract should know:
- The problem space and why it matters
- The scope of the survey (what is covered, what is excluded)
- The methodology (how papers were selected and organized)
- Key findings or themes (2–3 concrete takeaways)
- A primary recommendation or open challenge

Structure: 1–2 sentences of motivation, 1 sentence of scope, 1–2 sentences of method, 2–3 sentences of findings, 1 sentence of implication.

### 2. Introduction (1.5–2 pages)

**Purpose**: Hook the reader, establish the problem, justify the survey, and state contributions.

Paragraph structure:
1. **Opening hook** — a concrete, recent example or statistic that grounds the problem. Avoid "In recent years..." openings.
2. **Problem statement** — what is the research problem? Why does it matter? Who is affected?
3. **Gap identification** — what is missing from the current literature? Why is a new survey needed?
4. **Scope statement** — what this survey covers and, critically, what it excludes. Be explicit about boundaries.
5. **Methodology paragraph** — how were papers selected? What databases, keywords, time range? (For surveys.)
6. **Contributions** — a numbered list of 3–5 specific contributions. This is the most important paragraph for reviewers.
7. **Paper organization** — "The remainder of this paper is organized as follows..." (brief, 2–3 sentences).

### 3. Background & Definitions (1.5–2 pages)

**Purpose**: Establish shared vocabulary and assumptions.

Include:
- Formal or semi-formal definitions of key terms (bias, fairness, measurement, the specific technical domain)
- Brief history if needed to understand the current landscape
- Notation table if the paper uses mathematical formalism
- Pointers to foundational references the reader should know

Do **not** include: a full literature review (that's the core survey), overly long historical narratives, definitions of standard ML terms the audience already knows.

### 4. Taxonomy / Organizational Framework (0.5–1 page)

**Purpose**: Tell the reader how the survey is organized and why.

This section introduces the classification scheme used to group the surveyed work. Options:
- By **method type** (intrinsic vs. extrinsic, static vs. contextual)
- By **fairness definition** (individual, group, counterfactual)
- By **application domain** (NLP, CV, hiring, healthcare)
- By **lifecycle stage** (data, training, deployment, evaluation)
- Hybrid/multi-axis

Include a **taxonomy figure** (tree diagram, matrix, or Venn diagram) that visually summarizes the organization. This figure is often the most-referenced element of the paper.

### 5. Core Survey Sections (5–10 pages)

**Purpose**: The heart of the paper. Present and analyze the surveyed work.

Structure each subsection consistently:
1. **Opening** — define the category, explain its significance
2. **Method summaries** — for each paper/approach: what it does, how it works (brief), key results, limitations
3. **Synthesis** — what patterns emerge across methods in this category? What are the shared assumptions? Where do they disagree?
4. **Transition** — connect to the next subsection

Aim for **synthesis over summary**. Don't just list papers — compare them, identify trends, note contradictions. A good survey paragraph discusses 3–5 papers in conversation with each other, not sequentially.

### 6. Comparative Analysis (1–2 pages)

**Purpose**: Provide direct, structured comparison across the surveyed methods.

Must include:
- At least one **comparison table** with rows = methods, columns = evaluation criteria (datasets used, metrics, fairness definitions, computational cost, etc.)
- Discussion of **trade-offs** (e.g., accuracy vs. fairness, individual vs. group fairness)
- Identification of **gaps** — what has not been studied? What combinations of method + domain + fairness definition are missing?

### 7. Discussion (1–1.5 pages)

**Purpose**: Step back from the technical details and reflect.

Include:
- **Limitations of the survey itself** — what biases might exist in paper selection? What was excluded and why?
- **Cross-cutting themes** — patterns that span categories
- **Societal implications** — who benefits, who is harmed, what are the stakes
- **Future directions** — specific, actionable research questions, not vague "more work is needed"

### 8. Conclusion (0.5–1 page)

**Purpose**: Summarize findings and leave the reader with a clear takeaway.

Do:
- Restate the scope and key findings (briefly — the reader has read the paper)
- Highlight 2–3 actionable recommendations for practitioners or researchers
- End with a forward-looking sentence that connects to the broader research agenda

Do not: introduce new information, repeat the abstract verbatim, or use the conclusion as a second discussion section.

### 9. References (uncounted)

See `citations.md` for formatting. Aim for:
- 40–80 references for a conference survey
- 100–200 for a journal survey
- Recency: at least 30–40% of references should be from the last 3 years

### 10. Appendix (optional)

Use for:
- Extended comparison tables
- Proofs or derivations too long for the main text
- Supplementary figures
- Full list of surveyed papers with metadata
- Reproducibility details

---

## Length Calibration

| Component | Conference (pages) | Journal (pages) |
|-----------|-------------------|-----------------|
| Abstract | 0.25 | 0.25–0.5 |
| Introduction | 1.5–2 | 2–3 |
| Background | 1.5–2 | 2–4 |
| Taxonomy | 0.5–1 | 1–2 |
| Core survey | 5–10 | 10–20 |
| Comparative analysis | 1–2 | 2–4 |
| Discussion | 1–1.5 | 2–3 |
| Conclusion | 0.5–1 | 0.5–1 |
| **Total (excl. refs)** | **12–18** | **20–35** |

One page ≈ 600–700 words in two-column format.

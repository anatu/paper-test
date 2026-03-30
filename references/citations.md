# Citations Reference

## Citation Density

### Targets by section

| Section | Citations per page | Notes |
|---------|--------------------|-------|
| Abstract | 0 | Never cite in the abstract |
| Introduction | 8–15 | Heavy citation to establish context and prior surveys |
| Background | 10–20 | Definitional — cite the originators of each concept |
| Core survey | 15–30 | This is where most citations live |
| Comparative analysis | 5–10 | References back to already-cited work |
| Discussion | 5–10 | Cite related discussions, position papers, policy documents |
| Conclusion | 0–2 | Minimal; only if introducing a final forward reference |

### Overall target
- Conference survey: 60–100 references
- Journal survey: 100–200 references
- A survey with fewer than 40 references will appear shallow to reviewers

## Citation Placement

### Rules

1. **Cite at the point of claim, not at the end of the paragraph.**
   - Good: "Demographic parity requires equal selection rates across groups (Dwork et al., 2012)."
   - Bad: "There are many definitions of fairness. Demographic parity requires equal selection rates across groups. Equalized odds requires equal error rates. (Dwork et al., 2012; Hardt et al., 2016)."

2. **Multiple citations for contested or multi-sourced claims.**
   - "Fairness metrics can be mutually incompatible (Chouldechova, 2017; Kleinberg et al., 2016; Miconi, 2017)."

3. **Distinguish citation as parenthetical vs. narrative.**
   - Parenthetical: "...as demonstrated in prior work (Smith et al., 2020)."
   - Narrative: "Smith et al. (2020) demonstrated that..."
   - Use narrative when the authors' identity matters (e.g., they introduced the method). Use parenthetical when only the finding matters.

4. **Do not use citations as nouns.**
   - Bad: "[17] showed that..."
   - Good: "Smith et al. [17] showed that..."

5. **Cite the primary source, not a secondary reference.**
   - If you learned about method X from a survey, cite the original method paper, not the survey.

6. **Cite recent work to show currency.**
   - If the most recent citation in a subsection is from 2019, reviewers will question whether you've covered the latest developments.

## Citation Formatting

### Author-year style (preferred for most CS venues)

Use `natbib` or `biblatex` with author-year:
```latex
\usepackage[numbers]{natbib}   % for numbered style
\usepackage{natbib}             % for author-year style
```

- `\citet{key}` → "Smith et al. (2020)" (narrative/textual)
- `\citep{key}` → "(Smith et al., 2020)" (parenthetical)
- `\citep{key1,key2,key3}` → "(Smith et al., 2020; Jones et al., 2021; Lee, 2022)"

### Numbered style (NeurIPS, ICML, some ACM venues)

- `\cite{key}` → "[17]"
- Still prefer narrative form: "Smith et al. [17]" over "[17]"

### BibTeX conventions

```bibtex
@inproceedings{smith2020fairness,
  author    = {Smith, Alice and Jones, Bob and Lee, Carol},
  title     = {Measuring Fairness in Large Language Models},
  booktitle = {Proceedings of the International Conference on Machine Learning (ICML)},
  year      = {2020},
  pages     = {1234--5678},
}

@article{jones2021bias,
  author  = {Jones, Bob and Smith, Alice},
  title   = {Contextual Bias in Transformer Models},
  journal = {Journal of Machine Learning Research},
  volume  = {22},
  number  = {1},
  pages   = {1--45},
  year    = {2021},
}

@misc{lee2022embedding,
  author       = {Lee, Carol},
  title        = {On the Validity of Embedding-Based Bias Metrics},
  year         = {2022},
  eprint       = {2203.12345},
  archiveprefix = {arXiv},
  primaryclass = {cs.CL},
}
```

### Key formatting rules
- Use full venue names in `booktitle` (not abbreviations)
- Include page numbers when available
- For arXiv preprints, use `@misc` with `eprint` field
- Keep BibTeX keys consistent: `lastnameyearkeyword` (e.g., `smith2020fairness`)
- Alphabetize the `.bib` file by key
- Do not include URLs for published papers (the DOI suffices); include URLs for websites, tools, and datasets

## Self-Citation

- Self-citation is acceptable when the prior work is genuinely relevant
- Do not self-cite more than 10–15% of total references
- Anonymous submissions: follow venue guidelines (some require anonymizing self-citations, others do not)

## Handling Preprints

- Cite the published version if one exists (even if you read the arXiv version)
- For unpublished preprints, note the arXiv date and lack of peer review: "Lee (2022, preprint)" or in the text: "In a recent preprint, Lee (2022) proposed..."
- Preprints are acceptable references but should not be the sole evidence for strong claims

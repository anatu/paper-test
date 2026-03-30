# Prose Style Reference

## Voice and Tone

### Register
Academic CS prose sits between formal and technical. It is:
- **Precise**: every word earns its place
- **Neutral**: avoid advocacy unless flagged as opinion
- **Confident but hedged appropriately**: "X outperforms Y on benchmark Z" (confident, specific) vs. "our results suggest that X may generalize" (hedged, appropriate)
- **Third-person by default**: "we" is acceptable (and standard) for the authors' contributions; avoid "I" in multi-author papers

### What to avoid
- **Hype language**: "revolutionary," "groundbreaking," "state-of-the-art" (unless citing a specific benchmark result), "novel" (overused — prefer "we propose" or "we introduce")
- **Hedge stacking**: "It might potentially be possible that..." — one hedge per claim is enough
- **Informal register**: "pretty good results," "this paper is about," "a lot of work has been done"
- **Anthropomorphizing models**: "the model thinks," "the model understands" — prefer "the model predicts," "the model encodes," "the output reflects"
- **Starting sentences with "It is"**: usually signals a weak construction. Prefer active subjects.

## Sentence-Level Craft

### Topic sentences
Every paragraph begins with a sentence that states the paragraph's main claim. A reader skimming only topic sentences should reconstruct the paper's argument.

**Good**: "Counterfactual fairness requires that predictions remain invariant under interventions on protected attributes (Kusner et al., 2017)."

**Bad**: "Another important concept in the fairness literature is counterfactual fairness."

### Sentence length
Vary length. Technical definitions and formal claims benefit from shorter sentences. Contextual explanations and synthesis can use longer ones. Avoid:
- Sentences longer than 35 words (break them up)
- Sequences of 3+ sentences with identical structure (monotonous)

### Transitions
Use explicit logical connectives between paragraphs:
- **Continuation**: "Building on this," "Extending this approach,"
- **Contrast**: "In contrast," "However," "Despite this,"
- **Consequence**: "As a result," "This implies," "Consequently,"
- **Example**: "For instance," "To illustrate," "Concretely,"

Avoid: "Additionally," "Furthermore," "Moreover," in sequence — they signal a list, not an argument.

### Active vs. passive voice
Prefer active voice for clarity:
- Active: "We evaluate three fairness metrics on the CelebA dataset."
- Passive: "Three fairness metrics were evaluated on the CelebA dataset."

Use passive when the actor is irrelevant or unknown:
- "The dataset was collected between 2018 and 2020."

Target: ~70% active, ~30% passive.

## Paragraph Structure

### Length
- **Minimum**: 3 sentences (anything shorter should be merged or is a sign of underdeveloped thought)
- **Maximum**: ~12 sentences or ~200 words (anything longer should be split)
- **Sweet spot**: 5–8 sentences

### Internal structure
1. **Topic sentence** — the claim
2. **Evidence/elaboration** — data, citations, examples that support the claim
3. **Analysis** — what the evidence means, how it connects to the paper's argument
4. **Transition** — (optional) bridge to the next paragraph

### Synthesis paragraphs (critical for surveys)
When discussing multiple papers, weave them into a narrative rather than listing them:

**Bad** (list style):
> Smith et al. (2020) proposed method A. Jones et al. (2021) proposed method B. Lee et al. (2022) proposed method C.

**Good** (synthesis style):
> The embedding-based approach to bias measurement originated with Smith et al. (2020), who demonstrated that geometric relationships in word embeddings encode social stereotypes. Jones et al. (2021) extended this framework to contextual embeddings, revealing that bias manifests differently across layers of a transformer. Most recently, Lee et al. (2022) showed that these geometric measures can diverge significantly from downstream behavioral metrics, raising questions about the validity of embedding-based measurement as a standalone approach.

## Vocabulary Conventions

### Terms to use consistently
- "approach" or "method" (not "technique" for formal methods)
- "evaluate" or "measure" (not "test" when discussing metrics)
- "propose" or "introduce" (not "present" for new contributions; "present" for existing work)
- "demonstrate" (for empirical results) vs. "prove" (for formal results only)
- "widely adopted" (not "popular")

### Notation
- Define every symbol on first use
- Use a notation table for papers with more than ~10 symbols
- Be consistent: if $\theta$ is model parameters in Section 3, it cannot be a threshold in Section 5
- Prefer standard notation from the field (e.g., $\mathcal{D}$ for dataset, $f_\theta$ for parameterized function)

## Figures and Tables

### Figures
- Every figure must be referenced in the text ("as shown in Figure 1" or "Figure 1 illustrates...")
- Captions must be self-contained: a reader should understand the figure without reading the surrounding text
- Caption structure: one sentence describing what is shown, one sentence stating the takeaway
- Use vector graphics (PDF/SVG) for diagrams, high-resolution raster (PNG, 300+ DPI) for photos/screenshots
- Taxonomy figures are near-mandatory for survey papers

### Tables
- Every table must be referenced in the text
- Use `\toprule`, `\midrule`, `\bottomrule` (booktabs) — never `\hline`
- Column headers must be unambiguous
- Include units where applicable
- Comparison tables should highlight the best result (bold) per column

## Common Errors to Watch For

1. **Dangling modifiers**: "Using the BERT model, the bias was measured." (Who used BERT?)
2. **Ambiguous "this"**: "This is problematic." (What is "this"?) — always follow "this" with a noun.
3. **Citation as noun**: "In [17], the authors..." — prefer "Smith et al. [17] demonstrated..."
4. **Tense inconsistency**: use present tense for established facts ("Transformers use self-attention"), past tense for specific experimental results ("The model achieved 92% accuracy").
5. **Orphan acronyms**: define every acronym on first use, even common ones like LLM ("large language model (LLM)").

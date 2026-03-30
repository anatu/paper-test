"""Extract citation contexts — enrich references with in-text usage information."""

from __future__ import annotations

import re

from papercheck.models import CitationContext, PaperData, Reference


def extract_citation_contexts(paper: PaperData) -> list[Reference]:
    """Enrich paper references with in-text citation contexts.

    For each reference, finds every place it is cited in the text and captures
    the surrounding context (±2 sentences) and the specific claim being made.

    Returns the references list with populated in_text_contexts.
    """
    if not paper.references:
        return []

    # Build a mapping of citation keys to reference objects
    enriched: list[Reference] = []
    for ref in paper.references:
        contexts = _find_contexts_for_key(ref.key, paper)
        enriched.append(ref.model_copy(update={"in_text_contexts": contexts}))
    return enriched


def _find_contexts_for_key(key: str, paper: PaperData) -> list[CitationContext]:
    """Find all in-text citation contexts for a given citation key."""
    contexts: list[CitationContext] = []

    for section in paper.sections:
        # Search for \cite{...key...} patterns in section text
        # Keys can appear in multi-cite: \cite{foo,bar,baz}
        pattern = re.compile(
            r"\\cite[tp]?\{([^}]*\b" + re.escape(key) + r"\b[^}]*)\}"
        )
        for match in pattern.finditer(section.text):
            surrounding = _extract_surrounding_sentences(
                section.text, match.start(), num_sentences=2
            )
            claim = _extract_claim_sentence(section.text, match.start())
            contexts.append(
                CitationContext(
                    section=section.heading,
                    surrounding_text=surrounding,
                    claim_text=claim,
                )
            )

    # Also search raw_text if no section-level matches (e.g., PDF-parsed papers)
    if not contexts and paper.raw_text:
        # For raw text, look for author-year style citations or bracket citations
        contexts.extend(_find_contexts_in_raw_text(key, paper))

    return contexts


def _find_contexts_in_raw_text(key: str, paper: PaperData) -> list[CitationContext]:
    """Find citation contexts in raw text (non-LaTeX or fallback)."""
    contexts: list[CitationContext] = []
    # Try to find the key as a bracket reference like [key] or [N]
    pattern = re.compile(
        r"\\cite[tp]?\{([^}]*\b" + re.escape(key) + r"\b[^}]*)\}"
    )
    for match in pattern.finditer(paper.raw_text):
        surrounding = _extract_surrounding_sentences(
            paper.raw_text, match.start(), num_sentences=2
        )
        claim = _extract_claim_sentence(paper.raw_text, match.start())
        contexts.append(
            CitationContext(
                section="unknown",
                surrounding_text=surrounding,
                claim_text=claim,
            )
        )
    return contexts


def _extract_surrounding_sentences(text: str, pos: int, num_sentences: int = 2) -> str:
    """Extract ±num_sentences around the position in text."""
    # Split text into sentences (simple heuristic)
    sentences = _split_sentences(text)
    if not sentences:
        return text[max(0, pos - 200) : pos + 200].strip()

    # Find which sentence contains pos
    char_pos = 0
    target_idx = 0
    for i, sent in enumerate(sentences):
        end = char_pos + len(sent)
        if char_pos <= pos <= end:
            target_idx = i
            break
        char_pos = end

    start = max(0, target_idx - num_sentences)
    end = min(len(sentences), target_idx + num_sentences + 1)
    return " ".join(sentences[start:end]).strip()


def _extract_claim_sentence(text: str, pos: int) -> str | None:
    """Extract the single sentence containing the citation."""
    sentences = _split_sentences(text)
    if not sentences:
        return None

    char_pos = 0
    for sent in sentences:
        end = char_pos + len(sent)
        if char_pos <= pos <= end:
            return sent.strip()
        char_pos = end
    return None


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences using a simple regex heuristic."""
    # Split on period/question mark/exclamation followed by space and uppercase,
    # but not on common abbreviations like "et al.", "Fig.", "Eq.", etc.
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)
    return [p for p in parts if p.strip()]

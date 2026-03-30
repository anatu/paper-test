"""Internal cross-reference integrity checks."""

from __future__ import annotations

from papercheck.models import Finding, PaperData
from papercheck.parsing.latex_parser import parse_latex_string


def check_xref_integrity(paper: PaperData) -> list[Finding]:
    """Check that all \\ref{} targets resolve to existing \\label{} definitions.

    Only works when LaTeX source is available.
    """
    if not paper.latex_source:
        return [Finding(
            severity="info",
            category="xref_skipped",
            message="Cross-reference check skipped: no LaTeX source available",
        )]

    parsed = parse_latex_string(paper.latex_source)
    labels = parsed["labels"]
    refs = parsed["refs"]
    cites = parsed["cites"]
    bib_keys = {r.key for r in parsed["references"]}

    findings: list[Finding] = []

    # Check \ref{} and \eqref{} targets
    dangling = set()
    for ref in refs:
        if ref not in labels and ref not in dangling:
            dangling.add(ref)
            findings.append(Finding(
                severity="error",
                category="dangling_reference",
                message=f"Reference \\ref{{{ref}}} has no matching \\label{{{ref}}}",
                suggestion=f"Add \\label{{{ref}}} to the target element, or fix the reference key.",
            ))

    # Check \cite{} targets against bibliography
    if bib_keys:  # only check if we found bibliography entries
        for cite_key in set(cites):
            if cite_key not in bib_keys:
                findings.append(Finding(
                    severity="warning",
                    category="dangling_citation",
                    message=f"Citation \\cite{{{cite_key}}} not found in bibliography",
                    suggestion="Add a matching \\bibitem or .bib entry.",
                ))

    # Check for labels that are never referenced (informational)
    referenced = set(refs)
    for label in labels:
        if label not in referenced:
            findings.append(Finding(
                severity="info",
                category="unreferenced_label",
                message=f"Label '{label}' is defined but never referenced",
            ))

    return findings

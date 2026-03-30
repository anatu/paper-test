"""Variable naming and equation consistency checks."""

from __future__ import annotations

from papercheck.extractors.equations import find_undefined_variables
from papercheck.models import EquationRef, Finding


def check_math_consistency(equations: list[EquationRef], raw_text: str) -> list[Finding]:
    """Check for math/variable consistency issues.

    Checks:
    - Equations referenced later match their original label
    - Variable naming consistency (undefined variables flagged)
    """
    findings: list[Finding] = []
    findings.extend(_check_undefined_variables(equations, raw_text))
    findings.extend(_check_duplicate_labels(equations))
    return findings


def _check_undefined_variables(
    equations: list[EquationRef], raw_text: str
) -> list[Finding]:
    """Flag variables used in equations but never defined."""
    undefined = find_undefined_variables(equations, raw_text)
    findings: list[Finding] = []
    for var in undefined:
        # Only flag single-character variables that aren't obviously conventional
        if len(var) == 1:
            findings.append(Finding(
                severity="info",
                category="undefined_variable",
                message=f"Variable '{var}' used in equations but not explicitly defined",
                suggestion="Consider defining this variable where it first appears.",
            ))
    return findings


def _check_duplicate_labels(equations: list[EquationRef]) -> list[Finding]:
    """Flag equations with duplicate labels."""
    findings: list[Finding] = []
    seen: dict[str, int] = {}
    for eq in equations:
        if eq.label:
            seen[eq.label] = seen.get(eq.label, 0) + 1
    for label, count in seen.items():
        if count > 1:
            findings.append(Finding(
                severity="error",
                category="duplicate_label",
                message=f"Equation label '{label}' used {count} times",
                suggestion="Each equation label must be unique.",
            ))
    return findings

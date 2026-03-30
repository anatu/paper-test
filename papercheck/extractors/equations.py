"""Equation and variable tracking from LaTeX source."""

from __future__ import annotations

import re

from papercheck.models import EquationRef


class VariableUsage:
    """Tracks where a variable is defined and used."""

    def __init__(self, name: str):
        self.name = name
        self.defined_in: list[str] = []  # equation labels or section headings
        self.used_in: list[str] = []


def extract_variables(equations: list[EquationRef], raw_text: str) -> dict[str, VariableUsage]:
    """Extract variable definitions from equations and track usage in text.

    Returns a dict mapping variable name to its usage record.
    """
    variables: dict[str, VariableUsage] = {}

    for eq in equations:
        # Find single-letter variables (with optional subscripts) on LHS of =
        lhs_match = re.match(r"([A-Za-z](?:_\{?[^}=]+\}?)?)\s*=", eq.raw_latex)
        if lhs_match:
            var_name = lhs_match.group(1).strip()
            if var_name not in variables:
                variables[var_name] = VariableUsage(var_name)
            variables[var_name].defined_in.append(eq.label or "(unlabeled equation)")

        # Find all single-letter variables used in the equation
        var_pattern = re.compile(r"(?<![\\a-zA-Z])([A-Za-z])(?:_\{?([^}]+)\}?)?")
        for m in var_pattern.finditer(eq.raw_latex):
            full = m.group(0).strip()
            # Skip LaTeX commands
            pos = m.start()
            if pos > 0 and eq.raw_latex[pos - 1] == "\\":
                continue
            if full not in variables:
                variables[full] = VariableUsage(full)
            variables[full].used_in.append(eq.label or "(unlabeled equation)")

    return variables


def find_undefined_variables(
    equations: list[EquationRef], raw_text: str
) -> list[str]:
    """Find variables used in equations but never defined (no LHS occurrence).

    Returns list of variable names that appear only on RHS.
    This is a heuristic — some variables are conventionally understood (i, j, k, n, etc.)
    """
    variables = extract_variables(equations, raw_text)
    # Common mathematical conventions that don't need explicit definition
    conventional = {"i", "j", "k", "n", "m", "x", "y", "z", "t", "N", "M", "T"}
    undefined = []
    for name, usage in variables.items():
        if not usage.defined_in and name not in conventional and len(name) > 0:
            undefined.append(name)
    return undefined

"""Statistical consistency checking — Python port of statcheck logic."""

from __future__ import annotations

import math

from papercheck.extractors.statistics import (
    ReportedStatistic,
    LinkedStatGroup,
    extract_linked_stat_groups,
    extract_statistics,
)
from papercheck.models import Finding


def check_statistical_consistency(text: str) -> list[Finding]:
    """Run all statistical consistency checks on paper text.

    Checks:
    1. Test statistic / p-value consistency (statcheck)
    2. Impossible correlation values
    3. Impossible effect sizes / proportions
    4. CI lower > upper
    """
    findings: list[Finding] = []
    findings.extend(_check_test_stat_p_consistency(text))
    stats = extract_statistics(text)
    findings.extend(_check_impossible_values(stats))
    findings.extend(_check_ci_bounds(stats))
    return findings


def _check_test_stat_p_consistency(text: str) -> list[Finding]:
    """For each test statistic with an associated p-value, recompute and compare."""
    findings: list[Finding] = []
    groups = extract_linked_stat_groups(text)

    for group in groups:
        ts = group.test_stat
        pv = group.p_value

        if ts.df is None or ts.test_type is None:
            continue

        recomputed_p = _recompute_p_value(ts.test_type, float(ts.value), ts.df)
        if recomputed_p is None:
            continue

        reported_p = float(pv.value)

        # Check if they're in the same significance bracket
        if not _same_significance_bracket(reported_p, recomputed_p):
            findings.append(Finding(
                severity="error",
                category="statistical_error",
                message=(
                    f"Inconsistent p-value: reported p = {reported_p}, "
                    f"but recomputed p ≈ {recomputed_p:.4f} from {ts.test_type}"
                    f"({','.join(str(d) for d in ts.df)}) = {ts.value}"
                ),
                evidence=group.raw_text,
                suggestion="Verify the reported test statistic and p-value are correct.",
            ))

    return findings


def _recompute_p_value(test_type: str, test_value: float, df: tuple[int, ...]) -> float | None:
    """Recompute p-value from test statistic and degrees of freedom.

    Uses the regularized incomplete beta function for t and F distributions
    to avoid a scipy dependency.
    """
    try:
        if test_type == "t" and len(df) == 1:
            return _t_survival(abs(test_value), df[0]) * 2  # two-tailed
        elif test_type == "f" and len(df) == 2:
            return _f_survival(test_value, df[0], df[1])
        elif test_type == "chi_squared" and len(df) == 1:
            return _chi2_survival(test_value, df[0])
        elif test_type == "z":
            return _z_survival(abs(test_value)) * 2  # two-tailed
    except (ValueError, OverflowError, ZeroDivisionError):
        return None
    return None


def _same_significance_bracket(p1: float, p2: float) -> bool:
    """Check if two p-values fall in the same significance bracket.

    Brackets: <0.001, <0.01, <0.05, <0.10, >=0.10
    """
    brackets = [0.001, 0.01, 0.05, 0.10]
    def bracket(p: float) -> int:
        for i, threshold in enumerate(brackets):
            if p < threshold:
                return i
        return len(brackets)
    return bracket(p1) == bracket(p2)


def _check_impossible_values(stats: list[ReportedStatistic]) -> list[Finding]:
    """Check for statistically impossible values."""
    findings: list[Finding] = []
    for s in stats:
        if s.stat_type == "correlation":
            val = float(s.value)
            if abs(val) > 1.0:
                findings.append(Finding(
                    severity="critical",
                    category="impossible_value",
                    message=f"Correlation coefficient outside [-1, 1]: {val}",
                    evidence=s.raw_text,
                ))
        elif s.stat_type == "p_value":
            val = float(s.value)
            if val < 0 or val > 1:
                findings.append(Finding(
                    severity="critical",
                    category="impossible_value",
                    message=f"P-value outside [0, 1]: {val}",
                    evidence=s.raw_text,
                ))
        elif s.stat_type == "effect_size" and s.test_type == "eta_squared":
            val = float(s.value)
            if val < 0 or val > 1:
                findings.append(Finding(
                    severity="critical",
                    category="impossible_value",
                    message=f"Eta-squared outside [0, 1]: {val}",
                    evidence=s.raw_text,
                ))
    return findings


def _check_ci_bounds(stats: list[ReportedStatistic]) -> list[Finding]:
    """Check that CI lower bound < upper bound."""
    findings: list[Finding] = []
    for s in stats:
        if s.stat_type == "ci" and isinstance(s.value, str):
            # Parse "[lower, upper]"
            try:
                parts = s.value.strip("[]").split(",")
                lower = float(parts[0].strip())
                upper = float(parts[1].strip())
                if lower > upper:
                    findings.append(Finding(
                        severity="error",
                        category="statistical_error",
                        message=f"CI lower bound ({lower}) > upper bound ({upper})",
                        evidence=s.raw_text,
                    ))
            except (ValueError, IndexError):
                pass
    return findings


# ── Pure-Python statistical distribution functions ───────────────────────────
# These avoid requiring scipy. Accuracy is sufficient for bracket-level checks.

def _lgamma(x: float) -> float:
    """Log-gamma via Stirling's approximation + Lanczos."""
    return math.lgamma(x)


def _beta_incomplete_regularized(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta function I_x(a, b) via continued fraction."""
    if x < 0 or x > 1:
        return 0.0
    if x == 0 or x == 1:
        return x

    # Use symmetry relation if x > (a+1)/(a+b+2)
    if x > (a + 1) / (a + b + 2):
        return 1.0 - _beta_incomplete_regularized(b, a, 1.0 - x)

    ln_prefix = (
        _lgamma(a + b) - _lgamma(a) - _lgamma(b)
        + a * math.log(x) + b * math.log(1 - x)
    )
    prefix = math.exp(ln_prefix) / a

    # Lentz's continued fraction
    cf = 1.0
    c = 1.0
    d = 1.0 - (a + b) * x / (a + 1)
    if abs(d) < 1e-30:
        d = 1e-30
    d = 1.0 / d
    cf = d

    for m in range(1, 200):
        # Even step
        numerator = m * (b - m) * x / ((a + 2 * m - 1) * (a + 2 * m))
        d = 1.0 + numerator * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + numerator / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        cf *= c * d

        # Odd step
        numerator = -(a + m) * (a + b + m) * x / ((a + 2 * m) * (a + 2 * m + 1))
        d = 1.0 + numerator * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + numerator / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        delta = c * d
        cf *= delta

        if abs(delta - 1.0) < 1e-10:
            break

    return prefix * cf


def _t_survival(t: float, df: int) -> float:
    """Upper-tail probability for Student's t-distribution."""
    x = df / (df + t * t)
    return 0.5 * _beta_incomplete_regularized(df / 2, 0.5, x)


def _f_survival(f: float, df1: int, df2: int) -> float:
    """Upper-tail probability for F-distribution."""
    if f <= 0:
        return 1.0
    x = df2 / (df2 + df1 * f)
    return _beta_incomplete_regularized(df2 / 2, df1 / 2, x)


def _chi2_survival(x: float, df: int) -> float:
    """Upper-tail probability for chi-squared distribution."""
    if x <= 0:
        return 1.0
    return 1.0 - _gamma_regularized(df / 2, x / 2)


def _gamma_regularized(a: float, x: float) -> float:
    """Regularized lower incomplete gamma function P(a, x)."""
    if x < 0:
        return 0.0
    if x == 0:
        return 0.0
    if x < a + 1:
        # Series expansion
        s = 1.0 / a
        term = 1.0 / a
        for n in range(1, 200):
            term *= x / (a + n)
            s += term
            if abs(term) < abs(s) * 1e-10:
                break
        return s * math.exp(-x + a * math.log(x) - _lgamma(a))
    else:
        # Continued fraction
        return 1.0 - _gamma_cf_upper(a, x)


def _gamma_cf_upper(a: float, x: float) -> float:
    """Upper incomplete gamma via continued fraction Q(a, x)."""
    f = 1e-30
    c = 1e-30
    d = x + 1 - a
    if abs(d) < 1e-30:
        d = 1e-30
    d = 1.0 / d
    result = d

    for n in range(1, 200):
        an = n * (a - n)
        bn = x + 2 * n + 1 - a
        d = bn + an * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = bn + an / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        delta = c * d
        result *= delta
        if abs(delta - 1.0) < 1e-10:
            break

    return result * math.exp(-x + a * math.log(x) - _lgamma(a))


def _z_survival(z: float) -> float:
    """Upper-tail probability for standard normal (via error function)."""
    return 0.5 * math.erfc(z / math.sqrt(2))

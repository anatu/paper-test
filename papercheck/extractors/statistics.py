"""Regex-based extraction of reported statistics from paper text."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field


class ReportedStatistic(BaseModel):
    """A single statistical value extracted from text."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    stat_type: str  # "p_value", "ci", "test_statistic", "effect_size", "sample_size", "correlation"
    value: float | str
    test_type: str | None = None  # "t", "F", "chi_squared"
    df: tuple[int, ...] | None = None
    location: str = ""
    raw_text: str = ""


class LinkedStatGroup(BaseModel):
    """A test statistic linked with its reported p-value."""

    test_stat: ReportedStatistic
    p_value: ReportedStatistic
    raw_text: str = ""


def extract_statistics(text: str) -> list[ReportedStatistic]:
    """Extract all reported statistics from text.

    Extracts: p-values, test statistics with df, correlations,
    effect sizes, sample sizes, confidence intervals.
    """
    stats: list[ReportedStatistic] = []
    stats.extend(_extract_test_stats_with_p(text))
    stats.extend(_extract_standalone_p_values(text))
    stats.extend(_extract_correlations(text))
    stats.extend(_extract_effect_sizes(text))
    stats.extend(_extract_sample_sizes(text))
    stats.extend(_extract_confidence_intervals(text))
    return stats


def extract_linked_stat_groups(text: str) -> list[LinkedStatGroup]:
    """Extract test statistics linked to their p-values (for statcheck)."""
    groups: list[LinkedStatGroup] = []

    # Pattern: t(df) = value, p = value  or  t(df) = value, p < value
    pattern = re.compile(
        r"([tFz])\s*\((\d+(?:\s*,\s*\d+)?)\)\s*=\s*(-?\d+\.?\d*)"
        r"\s*,?\s*p\s*([<=<>])\s*(\d*\.?\d+)",
        re.IGNORECASE,
    )
    for m in pattern.finditer(text):
        test_type = m.group(1).lower()
        df_str = m.group(2)
        df_parts = tuple(int(x.strip()) for x in df_str.split(","))
        test_value = float(m.group(3))
        p_comparator = m.group(4)
        p_value = float(m.group(5))

        test_stat = ReportedStatistic(
            stat_type="test_statistic",
            value=test_value,
            test_type=test_type,
            df=df_parts,
            raw_text=m.group(0),
        )
        p_stat = ReportedStatistic(
            stat_type="p_value",
            value=p_value,
            raw_text=f"p {p_comparator} {p_value}",
        )
        groups.append(LinkedStatGroup(test_stat=test_stat, p_value=p_stat, raw_text=m.group(0)))

    # Chi-squared: χ²(df) = value, p = value (also chi2, chi-squared)
    chi_pattern = re.compile(
        r"(?:χ²|chi[_-]?(?:squared?|2))\s*\((\d+)\)\s*=\s*(-?\d+\.?\d*)"
        r"\s*,?\s*p\s*([<=<>])\s*(\d*\.?\d+)",
        re.IGNORECASE,
    )
    for m in chi_pattern.finditer(text):
        df = (int(m.group(1)),)
        test_value = float(m.group(2))
        p_value = float(m.group(4))

        test_stat = ReportedStatistic(
            stat_type="test_statistic",
            value=test_value,
            test_type="chi_squared",
            df=df,
            raw_text=m.group(0),
        )
        p_stat = ReportedStatistic(
            stat_type="p_value",
            value=p_value,
            raw_text=f"p {m.group(3)} {p_value}",
        )
        groups.append(LinkedStatGroup(test_stat=test_stat, p_value=p_stat, raw_text=m.group(0)))

    return groups


def _extract_test_stats_with_p(text: str) -> list[ReportedStatistic]:
    """Extract standalone test statistics (even without p-values)."""
    stats: list[ReportedStatistic] = []
    pattern = re.compile(
        r"([tFz])\s*\((\d+(?:\s*,\s*\d+)?)\)\s*=\s*(-?\d+\.?\d*)",
        re.IGNORECASE,
    )
    for m in pattern.finditer(text):
        test_type = m.group(1).lower()
        df_parts = tuple(int(x.strip()) for x in m.group(2).split(","))
        stats.append(ReportedStatistic(
            stat_type="test_statistic",
            value=float(m.group(3)),
            test_type=test_type,
            df=df_parts,
            raw_text=m.group(0),
        ))
    return stats


def _extract_standalone_p_values(text: str) -> list[ReportedStatistic]:
    """Extract p-values not already captured as part of test stat groups."""
    stats: list[ReportedStatistic] = []
    pattern = re.compile(
        r"(?<![a-zA-Z])p\s*[-–]?\s*(?:value)?\s*([<=<>≤≥])\s*(\d*\.?\d+)",
        re.IGNORECASE,
    )
    for m in pattern.finditer(text):
        stats.append(ReportedStatistic(
            stat_type="p_value",
            value=float(m.group(2)),
            raw_text=m.group(0),
        ))
    return stats


def _extract_correlations(text: str) -> list[ReportedStatistic]:
    """Extract correlation coefficients (r = ...)."""
    stats: list[ReportedStatistic] = []
    pattern = re.compile(r"(?<![a-zA-Z])r\s*=\s*(-?\d+\.?\d*)", re.IGNORECASE)
    for m in pattern.finditer(text):
        stats.append(ReportedStatistic(
            stat_type="correlation",
            value=float(m.group(1)),
            raw_text=m.group(0),
        ))
    return stats


def _extract_effect_sizes(text: str) -> list[ReportedStatistic]:
    """Extract effect sizes: d = ..., η² = ..., Cohen's d, etc."""
    stats: list[ReportedStatistic] = []
    # Cohen's d
    d_pattern = re.compile(r"(?:Cohen'?s?\s+)?d\s*=\s*(-?\d+\.?\d*)", re.IGNORECASE)
    for m in d_pattern.finditer(text):
        stats.append(ReportedStatistic(
            stat_type="effect_size",
            value=float(m.group(1)),
            test_type="cohens_d",
            raw_text=m.group(0),
        ))
    # η² (eta squared)
    eta_pattern = re.compile(r"η²?\s*=\s*(-?\d+\.?\d*)")
    for m in eta_pattern.finditer(text):
        stats.append(ReportedStatistic(
            stat_type="effect_size",
            value=float(m.group(1)),
            test_type="eta_squared",
            raw_text=m.group(0),
        ))
    return stats


def _extract_sample_sizes(text: str) -> list[ReportedStatistic]:
    """Extract sample sizes: n = ..., N = ..."""
    stats: list[ReportedStatistic] = []
    pattern = re.compile(r"(?<![a-zA-Z])[nN]\s*=\s*(\d+(?:,\d{3})*)")
    for m in pattern.finditer(text):
        val = int(m.group(1).replace(",", ""))
        stats.append(ReportedStatistic(
            stat_type="sample_size",
            value=val,
            raw_text=m.group(0),
        ))
    return stats


def _extract_confidence_intervals(text: str) -> list[ReportedStatistic]:
    """Extract confidence intervals: 95% CI [lower, upper]."""
    stats: list[ReportedStatistic] = []
    pattern = re.compile(
        r"(\d+)%?\s*CI\s*[\[(\{]\s*(-?\d+\.?\d*)\s*[,;–-]\s*(-?\d+\.?\d*)\s*[\])\}]",
        re.IGNORECASE,
    )
    for m in pattern.finditer(text):
        lower = float(m.group(2))
        upper = float(m.group(3))
        stats.append(ReportedStatistic(
            stat_type="ci",
            value=f"[{lower}, {upper}]",
            raw_text=m.group(0),
        ))
    return stats

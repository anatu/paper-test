"""Tests for statistical consistency checker."""

from __future__ import annotations

from papercheck.checkers.statcheck import (
    check_statistical_consistency,
    _recompute_p_value,
    _same_significance_bracket,
)
from papercheck.extractors.statistics import (
    extract_linked_stat_groups,
    extract_statistics,
)


class TestStatisticalExtraction:
    def test_extract_t_test_with_p(self):
        text = "The result was significant, t(24) = 2.50, p = 0.019."
        groups = extract_linked_stat_groups(text)
        assert len(groups) >= 1
        g = groups[0]
        assert g.test_stat.test_type == "t"
        assert g.test_stat.df == (24,)
        assert float(g.test_stat.value) == 2.50
        assert float(g.p_value.value) == 0.019

    def test_extract_f_test_with_p(self):
        text = "ANOVA: F(2, 45) = 3.1, p = 0.05."
        groups = extract_linked_stat_groups(text)
        assert len(groups) >= 1
        g = groups[0]
        assert g.test_stat.test_type == "f"
        assert g.test_stat.df == (2, 45)

    def test_extract_correlation(self):
        text = "We found r = 0.85 between X and Y."
        stats = extract_statistics(text)
        correlations = [s for s in stats if s.stat_type == "correlation"]
        assert len(correlations) >= 1
        assert float(correlations[0].value) == 0.85

    def test_extract_confidence_interval(self):
        text = "The 95% CI [1.2, 3.4] indicates significance."
        stats = extract_statistics(text)
        cis = [s for s in stats if s.stat_type == "ci"]
        assert len(cis) >= 1
        assert cis[0].value == "[1.2, 3.4]"

    def test_extract_sample_size(self):
        text = "Our sample consisted of N = 1200 participants (n = 600 per group)."
        stats = extract_statistics(text)
        sizes = [s for s in stats if s.stat_type == "sample_size"]
        assert len(sizes) >= 2

    def test_extract_p_value_standalone(self):
        text = "The effect was significant (p < 0.05)."
        stats = extract_statistics(text)
        pvals = [s for s in stats if s.stat_type == "p_value"]
        assert len(pvals) >= 1
        assert float(pvals[0].value) == 0.05


class TestPValueRecomputation:
    def test_t_recomputation(self):
        # t(24) = 2.50 should give p ≈ 0.019 (two-tailed)
        p = _recompute_p_value("t", 2.50, (24,))
        assert p is not None
        assert 0.015 < p < 0.025  # approximately 0.019

    def test_t_large_value_small_p(self):
        # t(30) = 5.0 should give very small p
        p = _recompute_p_value("t", 5.0, (30,))
        assert p is not None
        assert p < 0.001

    def test_z_recomputation(self):
        # z = 1.96 should give p ≈ 0.05 (two-tailed)
        p = _recompute_p_value("z", 1.96, ())
        assert p is not None
        assert 0.04 < p < 0.06


class TestSignificanceBrackets:
    def test_same_bracket(self):
        assert _same_significance_bracket(0.03, 0.04) is True  # both < 0.05
        assert _same_significance_bracket(0.005, 0.008) is True  # both < 0.01

    def test_different_bracket(self):
        assert _same_significance_bracket(0.001, 0.04) is False  # <0.001 vs <0.05
        assert _same_significance_bracket(0.03, 0.08) is False  # <0.05 vs <0.10


class TestStatisticalConsistency:
    def test_detects_inconsistent_p_value(self):
        # t(24) = 2.50, p = 0.001 → actual p ≈ 0.019, not < 0.001
        text = "We found t(24) = 2.50, p = 0.001."
        findings = check_statistical_consistency(text)
        stat_errors = [f for f in findings if f.category == "statistical_error"]
        assert len(stat_errors) >= 1

    def test_accepts_correct_p_value(self):
        # t(24) = 2.50, p = 0.019 → correct
        text = "We found t(24) = 2.50, p = 0.019."
        findings = check_statistical_consistency(text)
        stat_errors = [f for f in findings if f.category == "statistical_error"]
        assert len(stat_errors) == 0

    def test_detects_impossible_correlation(self):
        text = "The correlation was r = 1.35."
        findings = check_statistical_consistency(text)
        impossible = [f for f in findings if f.category == "impossible_value"]
        assert len(impossible) >= 1
        assert impossible[0].severity == "critical"

    def test_detects_ci_lower_gt_upper(self):
        text = "We report 95% CI [4.2, 2.1] for the mean."
        findings = check_statistical_consistency(text)
        ci_errors = [f for f in findings if f.category == "statistical_error"]
        assert len(ci_errors) >= 1

    def test_handles_missing_df_gracefully(self):
        # Just a p-value without test statistic — no error should be raised
        text = "The result was significant (p = 0.019)."
        findings = check_statistical_consistency(text)
        stat_errors = [f for f in findings if f.category == "statistical_error"]
        assert len(stat_errors) == 0

    def test_statbug_fixture(self, sample_statbug_tex):
        text = sample_statbug_tex.read_text()
        findings = check_statistical_consistency(text)
        categories = [f.category for f in findings]
        # Should catch: inconsistent p-value, impossible correlation, CI bounds
        assert "statistical_error" in categories or "impossible_value" in categories

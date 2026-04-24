"""Extended tests for ai_readiness.core.models — new fields and category scoring."""
from __future__ import annotations

import pytest

from ai_readiness.core.models import (
    CategoryScore,
    CheckResult,
    CheckStatus,
    DimensionScore,
    Report,
)


def _cr(name: str, status: CheckStatus = CheckStatus.PASS, **kw) -> CheckResult:
    return CheckResult(name=name, status=status, message="ok", **kw)


# ── CheckResult new fields ───────────────────────────────────────────

def test_check_result_raw_score_default_none():
    cr = CheckResult(name="x", status=CheckStatus.PASS, message="ok")
    assert cr.raw_score is None


def test_check_result_raw_score_set():
    cr = CheckResult(name="x", status=CheckStatus.PASS, message="ok", raw_score=7.5)
    assert cr.raw_score == 7.5


def test_check_result_scorable_default_true():
    cr = CheckResult(name="x", status=CheckStatus.PASS, message="ok")
    assert cr.scorable is True


def test_check_result_scorable_false():
    cr = CheckResult(name="x", status=CheckStatus.PASS, message="ok", scorable=False)
    assert cr.scorable is False


def test_check_result_check_id_default_none():
    cr = CheckResult(name="x", status=CheckStatus.PASS, message="ok")
    assert cr.check_id is None


def test_check_result_check_id_set():
    cr = CheckResult(name="x", status=CheckStatus.PASS, message="ok", check_id="ai_config.x")
    assert cr.check_id == "ai_config.x"


# ── CategoryScore.score computation ──────────────────────────────────

def test_category_score_all_pass():
    cat = CategoryScore(
        category_id="test", category_name="Test", description="", weight=50,
        checks=[_cr("a"), _cr("b")],
    )
    assert cat.score == 10.0


def test_category_score_all_fail():
    cat = CategoryScore(
        category_id="test", category_name="Test", description="", weight=50,
        checks=[_cr("a", CheckStatus.FAIL), _cr("b", CheckStatus.FAIL)],
    )
    assert cat.score == 0.0


def test_category_score_mixed_pass_fail():
    cat = CategoryScore(
        category_id="test", category_name="Test", description="", weight=50,
        checks=[_cr("a", CheckStatus.PASS), _cr("b", CheckStatus.FAIL)],
    )
    # (10 + 0) / 2 = 5.0
    assert cat.score == 5.0


def test_category_score_warn_counts_as_5():
    cat = CategoryScore(
        category_id="test", category_name="Test", description="", weight=50,
        checks=[_cr("a", CheckStatus.WARN)],
    )
    assert cat.score == 5.0


def test_category_score_with_raw_scores():
    cat = CategoryScore(
        category_id="test", category_name="Test", description="", weight=50,
        checks=[
            _cr("a", CheckStatus.PASS, raw_score=7.0),
            _cr("b", CheckStatus.WARN, raw_score=5.0),
        ],
    )
    # (7.0 + 5.0) / 2 = 6.0
    assert cat.score == 6.0


def test_category_score_mixed_raw_and_status():
    cat = CategoryScore(
        category_id="test", category_name="Test", description="", weight=50,
        checks=[
            _cr("a", CheckStatus.PASS, raw_score=8.0),  # uses 8.0
            _cr("b", CheckStatus.PASS),                   # uses 10
        ],
    )
    # (8.0 + 10) / 2 = 9.0
    assert cat.score == 9.0


def test_category_score_skips_excluded():
    cat = CategoryScore(
        category_id="test", category_name="Test", description="", weight=50,
        checks=[
            _cr("a", CheckStatus.PASS),
            _cr("b", CheckStatus.SKIP),
        ],
    )
    # SKIP excluded, only PASS counted: 10/1 = 10.0
    assert cat.score == 10.0


def test_category_score_non_scorable_excluded():
    cat = CategoryScore(
        category_id="test", category_name="Test", description="", weight=50,
        checks=[
            _cr("a", CheckStatus.PASS),
            _cr("b", CheckStatus.PASS, scorable=False),
        ],
    )
    # Only "a" is scorable: 10/1 = 10.0
    assert cat.score == 10.0


def test_category_score_empty_checks():
    cat = CategoryScore(
        category_id="test", category_name="Test", description="", weight=50,
        checks=[],
    )
    assert cat.score == 0.0


# ── CategoryScore.passed_checks / total_checks ──────────────────────

def test_passed_checks_only_scorable():
    cat = CategoryScore(
        category_id="test", category_name="Test", description="", weight=50,
        checks=[
            _cr("a", CheckStatus.PASS),
            _cr("b", CheckStatus.PASS, scorable=False),
            _cr("c", CheckStatus.FAIL),
        ],
    )
    assert cat.passed_checks == 1  # only "a"


def test_total_checks_excludes_skip_and_nonscorable():
    cat = CategoryScore(
        category_id="test", category_name="Test", description="", weight=50,
        checks=[
            _cr("a", CheckStatus.PASS),
            _cr("b", CheckStatus.SKIP),
            _cr("c", CheckStatus.FAIL, scorable=False),
            _cr("d", CheckStatus.FAIL),
        ],
    )
    # "a" (scorable, not SKIP) + "d" (scorable, not SKIP) = 2
    assert cat.total_checks == 2


# ── CategoryScore.weighted_score ─────────────────────────────────────

def test_weighted_score():
    cat = CategoryScore(
        category_id="test", category_name="Test", description="", weight=50,
        checks=[_cr("a", CheckStatus.PASS)],
    )
    # score=10.0, weight=50 → 10.0 * 50/100 = 5.0
    assert cat.weighted_score == 5.0


# ── Report.overall_score ─────────────────────────────────────────────

def test_report_overall_score_from_categories():
    cats = [
        CategoryScore(
            category_id="a", category_name="A", description="", weight=50,
            checks=[_cr("x", CheckStatus.PASS)],  # score=10
        ),
        CategoryScore(
            category_id="b", category_name="B", description="", weight=50,
            checks=[_cr("y", CheckStatus.FAIL)],  # score=0
        ),
    ]
    report = Report(repo_path="/tmp", categories=cats)
    # (10*50 + 0*50) / 100 * 10 = 50.0
    assert report.overall_score == 50.0


def test_report_overall_score_falls_back_to_dimensions():
    dims = [
        DimensionScore(dimension_id="d1", dimension_name="D1", score=8.0, weight=50),
        DimensionScore(dimension_id="d2", dimension_name="D2", score=4.0, weight=50),
    ]
    report = Report(repo_path="/tmp", dimensions=dims)
    # (8*50 + 4*50) / 100 * 10 = 60.0
    assert report.overall_score == 60.0


def test_report_overall_score_empty():
    report = Report(repo_path="/tmp")
    assert report.overall_score == 0.0


# ── Report.recommendations ───────────────────────────────────────────

def test_report_recommendations_from_categories():
    cats = [
        CategoryScore(
            category_id="a", category_name="A", description="", weight=50,
            checks=[
                CheckResult(name="x", status=CheckStatus.FAIL, message="bad",
                            recommendation="Fix x"),
            ],
        ),
    ]
    report = Report(repo_path="/tmp", categories=cats)
    assert "Fix x" in report.recommendations


def test_report_recommendations_fallback_to_dimensions():
    dims = [
        DimensionScore(
            dimension_id="d1", dimension_name="D1", score=0, weight=50,
            checks=[
                CheckResult(name="y", status=CheckStatus.WARN, message="meh",
                            recommendation="Fix y"),
            ],
        ),
    ]
    report = Report(repo_path="/tmp", dimensions=dims)
    assert "Fix y" in report.recommendations

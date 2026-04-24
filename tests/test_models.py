"""Tests for ai_readiness.core.models — CheckStatus, Rating, CheckResult, DimensionScore, Report."""
from __future__ import annotations

import pytest

from ai_readiness.core.models import CheckResult, CheckStatus, DimensionScore, Rating, Report


# ── CheckStatus ──────────────────────────────────────────────────────

class TestCheckStatus:
    def test_enum_values(self):
        assert CheckStatus.PASS.value == "pass"
        assert CheckStatus.FAIL.value == "fail"
        assert CheckStatus.WARN.value == "warn"
        assert CheckStatus.SKIP.value == "skip"

    def test_all_members(self):
        assert set(CheckStatus) == {CheckStatus.PASS, CheckStatus.FAIL, CheckStatus.WARN, CheckStatus.SKIP}


# ── Rating ───────────────────────────────────────────────────────────

class TestRating:
    @pytest.mark.parametrize("score, expected", [
        (0, Rating.POOR),
        (10, Rating.POOR),
        (39, Rating.POOR),
        (39.9, Rating.POOR),
        (40, Rating.FAIR),
        (50, Rating.FAIR),
        (59, Rating.FAIR),
        (59.9, Rating.FAIR),
        (60, Rating.GOOD),
        (70, Rating.GOOD),
        (79, Rating.GOOD),
        (79.9, Rating.GOOD),
        (80, Rating.EXCELLENT),
        (90, Rating.EXCELLENT),
        (100, Rating.EXCELLENT),
    ])
    def test_from_score(self, score: float, expected: Rating):
        assert Rating.from_score(score) is expected

    def test_emoji_mapping(self):
        assert Rating.POOR.emoji == "🔴"
        assert Rating.FAIR.emoji == "🟡"
        assert Rating.GOOD.emoji == "🟢"
        assert Rating.EXCELLENT.emoji == "🌟"

    def test_enum_values(self):
        assert Rating.POOR.value == "Poor"
        assert Rating.FAIR.value == "Fair"
        assert Rating.GOOD.value == "Good"
        assert Rating.EXCELLENT.value == "Excellent"


# ── CheckResult ──────────────────────────────────────────────────────

class TestCheckResult:
    def test_creation_minimal(self):
        r = CheckResult(name="test", status=CheckStatus.PASS, message="ok")
        assert r.name == "test"
        assert r.status == CheckStatus.PASS
        assert r.message == "ok"
        assert r.recommendation is None
        assert r.details is None

    def test_creation_full(self):
        r = CheckResult(
            name="readme",
            status=CheckStatus.WARN,
            message="thin",
            recommendation="expand it",
            details="only 100 chars",
        )
        assert r.recommendation == "expand it"
        assert r.details == "only 100 chars"


# ── DimensionScore ───────────────────────────────────────────────────

class TestDimensionScore:
    def _make(self, checks: list[CheckResult], score: float = 5.0, weight: float = 20.0) -> DimensionScore:
        return DimensionScore(
            dimension_id="test",
            dimension_name="Test Dimension",
            score=score,
            weight=weight,
            checks=checks,
        )

    def test_passed_checks(self):
        checks = [
            CheckResult("a", CheckStatus.PASS, "ok"),
            CheckResult("b", CheckStatus.FAIL, "nope"),
            CheckResult("c", CheckStatus.PASS, "ok"),
            CheckResult("d", CheckStatus.SKIP, "skipped"),
        ]
        ds = self._make(checks)
        assert ds.passed_checks == 2

    def test_total_checks_excludes_skip(self):
        checks = [
            CheckResult("a", CheckStatus.PASS, "ok"),
            CheckResult("b", CheckStatus.FAIL, "nope"),
            CheckResult("c", CheckStatus.SKIP, "skipped"),
        ]
        ds = self._make(checks)
        assert ds.total_checks == 2

    def test_weighted_score(self):
        ds = self._make([], score=8.0, weight=25.0)
        assert ds.weighted_score == pytest.approx(2.0)  # 8 * 25/100

    def test_weighted_score_zero_weight(self):
        ds = self._make([], score=10.0, weight=0.0)
        assert ds.weighted_score == pytest.approx(0.0)

    def test_empty_checks(self):
        ds = self._make([])
        assert ds.passed_checks == 0
        assert ds.total_checks == 0


# ── Report ───────────────────────────────────────────────────────────

class TestReport:
    def _dim(self, score: float, weight: float, checks: list[CheckResult] | None = None) -> DimensionScore:
        return DimensionScore(
            dimension_id="d",
            dimension_name="D",
            score=score,
            weight=weight,
            checks=checks or [],
        )

    def test_overall_score_single_dimension(self):
        r = Report(repo_path=".", dimensions=[self._dim(10.0, 100.0)])
        assert r.overall_score == pytest.approx(100.0)

    def test_overall_score_weighted_average(self):
        # Two dimensions: score=10 weight=50, score=0 weight=50
        # weighted_sum = 10*50 + 0*50 = 500
        # total_weight = 100
        # overall = 500 / 100 * 10 = 50
        r = Report(repo_path=".", dimensions=[self._dim(10.0, 50.0), self._dim(0.0, 50.0)])
        assert r.overall_score == pytest.approx(50.0)

    def test_overall_score_empty_dimensions(self):
        r = Report(repo_path=".")
        assert r.overall_score == 0.0

    def test_overall_score_zero_weight(self):
        r = Report(repo_path=".", dimensions=[self._dim(5.0, 0.0)])
        assert r.overall_score == 0.0

    def test_rating_poor(self):
        r = Report(repo_path=".", dimensions=[self._dim(2.0, 100.0)])
        assert r.rating is Rating.POOR

    def test_rating_excellent(self):
        r = Report(repo_path=".", dimensions=[self._dim(10.0, 100.0)])
        assert r.rating is Rating.EXCELLENT

    def test_recommendations_collected(self):
        checks = [
            CheckResult("a", CheckStatus.FAIL, "bad", recommendation="fix a"),
            CheckResult("b", CheckStatus.PASS, "good"),
            CheckResult("c", CheckStatus.WARN, "meh", recommendation="improve c"),
        ]
        r = Report(repo_path=".", dimensions=[self._dim(5.0, 100.0, checks)])
        assert r.recommendations == ["fix a", "improve c"]

    def test_recommendations_empty_when_all_pass(self):
        checks = [CheckResult("a", CheckStatus.PASS, "ok")]
        r = Report(repo_path=".", dimensions=[self._dim(10.0, 100.0, checks)])
        assert r.recommendations == []

    def test_recommendations_skip_none(self):
        checks = [CheckResult("a", CheckStatus.FAIL, "bad", recommendation=None)]
        r = Report(repo_path=".", dimensions=[self._dim(5.0, 100.0, checks)])
        assert r.recommendations == []

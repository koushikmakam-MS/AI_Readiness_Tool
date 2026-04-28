"""Data models for AI Readiness assessment results."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class CheckStatus(Enum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    SKIP = "skip"


class Rating(Enum):
    POOR = "Poor"
    FAIR = "Fair"
    GOOD = "Good"
    EXCELLENT = "Excellent"

    @classmethod
    def from_score(cls, score: float) -> Rating:
        if score >= 80:
            return cls.EXCELLENT
        elif score >= 60:
            return cls.GOOD
        elif score >= 40:
            return cls.FAIR
        return cls.POOR

    @property
    def emoji(self) -> str:
        return {
            Rating.POOR: "🔴",
            Rating.FAIR: "🟡",
            Rating.GOOD: "🟢",
            Rating.EXCELLENT: "🌟",
        }[self]


@dataclass
class CheckResult:
    """Result of a single check within a dimension."""

    name: str
    status: CheckStatus
    message: str
    recommendation: Optional[str] = None
    details: Optional[str] = None
    raw_score: Optional[float] = None  # 0-10 numeric score from LLM (bypasses PASS/FAIL bucketing)
    check_id: Optional[str] = None  # Stable ID for category mapping
    scorable: bool = True  # False for info-only / derived checks (won't count toward scoring)


@dataclass
class DimensionScore:
    """Score for a single assessment dimension."""

    dimension_id: str
    dimension_name: str
    score: float  # 0-10
    weight: float  # percentage weight
    checks: list[CheckResult] = field(default_factory=list)
    llm_insights: Optional[str] = None

    @property
    def passed_checks(self) -> int:
        return sum(1 for c in self.checks if c.status == CheckStatus.PASS and c.scorable)

    @property
    def total_checks(self) -> int:
        return sum(1 for c in self.checks if c.status != CheckStatus.SKIP and c.scorable)

    @property
    def weighted_score(self) -> float:
        return self.score * (self.weight / 100.0)


@dataclass
class CategoryScore:
    """Score for a top-level assessment category (AI Onboarding / AI Coding / Repo Health)."""

    category_id: str
    category_name: str
    description: str
    weight: float  # percentage weight (sum of all categories = 100)
    checks: list[CheckResult] = field(default_factory=list)
    llm_insights: Optional[str] = None

    @property
    def score(self) -> float:
        """Compute score from atomic checks (0-10 scale)."""
        scorable = [c for c in self.checks if c.status != CheckStatus.SKIP and c.scorable]
        if not scorable:
            return 0.0

        raw_checks = [c for c in scorable if c.raw_score is not None]
        status_checks = [c for c in scorable if c.raw_score is None]

        total_score = 0.0
        count = 0

        # Raw-scored checks (from LLM) use their actual 0-10 value
        for c in raw_checks:
            total_score += c.raw_score
            count += 1

        # Status-based checks use PASS=10, WARN=5, FAIL=0
        for c in status_checks:
            if c.status == CheckStatus.PASS:
                total_score += 10.0
            elif c.status == CheckStatus.WARN:
                total_score += 5.0
            count += 1

        return round(total_score / count, 1) if count > 0 else 0.0

    @property
    def passed_checks(self) -> int:
        return sum(1 for c in self.checks if c.status == CheckStatus.PASS and c.scorable)

    @property
    def total_checks(self) -> int:
        return sum(1 for c in self.checks if c.status != CheckStatus.SKIP and c.scorable)

    @property
    def weighted_score(self) -> float:
        return self.score * (self.weight / 100.0)


@dataclass
class Report:
    """Complete AI Readiness assessment report."""

    repo_path: str
    dimensions: list[DimensionScore] = field(default_factory=list)
    categories: list[CategoryScore] = field(default_factory=list)
    languages_detected: list[str] = field(default_factory=list)
    llm_summary: Optional[str] = None
    personas_report: Optional[Any] = None  # ai_readiness.personas.runner.RunReport

    @property
    def overall_score(self) -> float:
        """Weighted average score normalized to 0-100."""
        # Use categories if available, else fall back to dimensions
        if self.categories:
            total_weight = sum(c.weight for c in self.categories)
            if total_weight == 0:
                return 0.0
            weighted_sum = sum(c.score * c.weight for c in self.categories)
            return weighted_sum / total_weight * 10  # normalize to 0-100

        if not self.dimensions:
            return 0.0
        total_weight = sum(d.weight for d in self.dimensions)
        if total_weight == 0:
            return 0.0
        weighted_sum = sum(d.score * d.weight for d in self.dimensions)
        return weighted_sum / total_weight * 10  # normalize to 0-100

    @property
    def rating(self) -> Rating:
        return Rating.from_score(self.overall_score)

    @property
    def recommendations(self) -> list[str]:
        """Collect all recommendations from failed/warned checks."""
        recs = []
        # From categories first
        for cat in self.categories:
            for check in cat.checks:
                if check.status in (CheckStatus.FAIL, CheckStatus.WARN) and check.recommendation:
                    recs.append(check.recommendation)
        # Fallback to dimensions
        if not recs:
            for dim in self.dimensions:
                for check in dim.checks:
                    if check.status in (CheckStatus.FAIL, CheckStatus.WARN) and check.recommendation:
                        recs.append(check.recommendation)
        return recs

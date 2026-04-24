"""Tests for ai_readiness.core.category_mapper."""
from __future__ import annotations

import pytest

from ai_readiness.core.category_mapper import build_categories, CATEGORIES
from ai_readiness.core.models import (
    CategoryScore,
    CheckResult,
    CheckStatus,
    DimensionScore,
    Report,
)


def _make_dim(dim_id: str, checks: list[CheckResult], name: str = "") -> DimensionScore:
    return DimensionScore(
        dimension_id=dim_id,
        dimension_name=name or dim_id,
        score=5.0,
        weight=10.0,
        checks=checks,
    )


def _cr(name: str, status: CheckStatus = CheckStatus.PASS, **kw) -> CheckResult:
    return CheckResult(name=name, status=status, message="ok", **kw)


# ── Category weights ─────────────────────────────────────────────────

def test_category_weights_sum_to_100():
    total = sum(c["weight"] for c in CATEGORIES.values())
    assert total == 100


def test_category_weights_individual():
    assert CATEGORIES["ai_onboarding"]["weight"] == 25
    assert CATEGORIES["ai_coding"]["weight"] == 50
    assert CATEGORIES["repo_health"]["weight"] == 25


# ── AI Config checks default scorable ───────────────────────────────

def test_ai_config_individual_checks_are_info_only():
    """Individual AI config tool checks should be info-only (scorable=False)."""
    checks = [
        _cr("Copilot instructions"),
        _cr("Copilot setup steps"),
        _cr("Cursor config"),
        _cr("AGENTS.md"),
        _cr("CLAUDE.md"),
        _cr("Aider config"),
        _cr("Has any AI config"),
    ]
    report = Report(repo_path="/tmp", dimensions=[_make_dim("ai_config", checks)])
    cats = build_categories(report)
    cat_map = {c.category_id: c for c in cats}
    onboarding = cat_map["ai_onboarding"]

    check_map = {c.name: c for c in onboarding.checks}
    # Individual tool checks are info-only
    assert check_map["Copilot instructions"].scorable is False
    assert check_map["Copilot setup steps"].scorable is False
    assert check_map["Cursor config"].scorable is False
    assert check_map["AGENTS.md"].scorable is False
    assert check_map["CLAUDE.md"].scorable is False
    assert check_map["Aider config"].scorable is False
    # "Has any AI config" is scored
    assert check_map["Has any AI config"].scorable is True


# ── Setup checks ─────────────────────────────────────────────────────

def test_setup_scored_and_info_only():
    checks = [
        _cr("Single-command build"),
        _cr("Container support"),
        _cr("Helper scripts"),
        _cr("Environment template"),
    ]
    report = Report(repo_path="/tmp", dimensions=[_make_dim("setup_onboarding", checks)])
    cats = build_categories(report)
    cat_map = {c.category_id: c for c in cats}
    onboarding = cat_map["ai_onboarding"]
    check_map = {c.name: c for c in onboarding.checks}

    assert check_map["Single-command build"].scorable is True
    assert check_map["Helper scripts"].scorable is True
    assert check_map["Container support"].scorable is False
    assert check_map["Environment template"].scorable is False


# ── LLM code review → ai_coding ─────────────────────────────────────

def test_llm_code_review_all_go_to_ai_coding():
    checks = [
        _cr("Code Readability & Clarity", raw_score=7.0),
        _cr("Error Handling & Robustness", raw_score=5.0),
        _cr("Design Patterns & Architecture", raw_score=6.0),
        _cr("Code Smells (absence of)", raw_score=8.0),
        _cr("AI Agent Friendliness", raw_score=7.0),
        _cr("Maintainability & Extensibility", raw_score=6.0),
        _cr("Review Summary"),
    ]
    report = Report(repo_path="/tmp", dimensions=[_make_dim("llm_code_review", checks)])
    cats = build_categories(report)
    cat_map = {c.category_id: c for c in cats}
    ai_coding = cat_map["ai_coding"]
    names = {c.name for c in ai_coding.checks}
    for check in checks:
        assert check.name in names, f"{check.name} should be in ai_coding"


# ── Documentation splits ─────────────────────────────────────────────

def test_documentation_checks_split_correctly():
    checks = [
        _cr("README exists"),
        _cr("README key sections"),
        _cr("Architecture docs"),
        _cr("CONTRIBUTING guide"),
        _cr("CODE_OF_CONDUCT"),
        _cr("CHANGELOG"),
    ]
    report = Report(repo_path="/tmp", dimensions=[_make_dim("documentation", checks)])
    cats = build_categories(report)
    cat_map = {c.category_id: c for c in cats}

    onboarding_names = {c.name for c in cat_map["ai_onboarding"].checks}
    repo_health_names = {c.name for c in cat_map["repo_health"].checks}

    assert "README exists" in onboarding_names
    assert "README key sections" in onboarding_names
    assert "Architecture docs" in onboarding_names
    assert "CONTRIBUTING guide" in onboarding_names
    assert "CODE_OF_CONDUCT" in repo_health_names
    assert "CHANGELOG" in repo_health_names


# ── target_agents: copilot ───────────────────────────────────────────

def test_target_agents_copilot_scores_copilot_checks():
    checks = [
        _cr("Copilot instructions"),
        _cr("Copilot setup steps"),
        _cr("Cursor config"),
        _cr("CLAUDE.md"),
        _cr("Has any AI config"),
    ]
    report = Report(repo_path="/tmp", dimensions=[_make_dim("ai_config", checks)])
    cats = build_categories(report, target_agents=["copilot"])
    cat_map = {c.category_id: c for c in cats}
    check_map = {c.name: c for c in cat_map["ai_onboarding"].checks}

    # Copilot checks become scored
    assert check_map["Copilot instructions"].scorable is True
    assert check_map["Copilot setup steps"].scorable is True
    # Non-targeted still info-only
    assert check_map["Cursor config"].scorable is False
    assert check_map["CLAUDE.md"].scorable is False
    # "Has any AI config" becomes info-only when target_agents is set
    assert check_map["Has any AI config"].scorable is False


# ── target_agents: copilot + cursor ──────────────────────────────────

def test_target_agents_copilot_and_cursor():
    checks = [
        _cr("Copilot instructions"),
        _cr("Copilot setup steps"),
        _cr("Cursor config"),
        _cr("CLAUDE.md"),
        _cr("Has any AI config"),
    ]
    report = Report(repo_path="/tmp", dimensions=[_make_dim("ai_config", checks)])
    cats = build_categories(report, target_agents=["copilot", "cursor"])
    cat_map = {c.category_id: c for c in cats}
    check_map = {c.name: c for c in cat_map["ai_onboarding"].checks}

    assert check_map["Copilot instructions"].scorable is True
    assert check_map["Copilot setup steps"].scorable is True
    assert check_map["Cursor config"].scorable is True
    assert check_map["CLAUDE.md"].scorable is False
    assert check_map["Has any AI config"].scorable is False


# ── Empty dimensions ─────────────────────────────────────────────────

def test_empty_dimensions_all_scores_zero():
    report = Report(repo_path="/tmp", dimensions=[])
    cats = build_categories(report)
    for cat in cats:
        assert cat.score == 0.0

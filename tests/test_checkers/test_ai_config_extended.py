"""Extended tests for AIConfigChecker — target_agents behaviour."""
from __future__ import annotations

import pytest

from ai_readiness.checkers.ai_config import AIConfigChecker, AGENT_REGISTRY
from ai_readiness.core.models import CheckStatus
from tests.conftest import create_file


def _run(tmp_path, **kwargs):
    checker = AIConfigChecker(repo_path=tmp_path, **kwargs)
    return {c.name: c for c in checker.run_checks()}


# ── Without target_agents (default) ─────────────────────────────────

def test_no_target_agents_all_scorable(tmp_path):
    results = _run(tmp_path)
    for check in results.values():
        assert check.scorable is True


# ── target_agents=["copilot"] ────────────────────────────────────────

def test_copilot_target_copilot_scored(tmp_path):
    create_file(tmp_path, ".github/copilot-instructions.md", "x")
    create_file(tmp_path, ".github/copilot-setup-steps.yml", "x")
    results = _run(tmp_path, target_agents=["copilot"])
    assert results["Copilot instructions"].scorable is True
    assert results["Copilot setup steps"].scorable is True


def test_copilot_target_others_not_scored(tmp_path):
    results = _run(tmp_path, target_agents=["copilot"])
    assert results["Cursor config"].scorable is False
    assert results["CLAUDE.md"].scorable is False
    assert results["AGENTS.md"].scorable is False
    assert results["Aider config"].scorable is False


# ── target_agents=["copilot", "cursor"] ─────────────────────────────

def test_copilot_and_cursor_both_scored(tmp_path):
    results = _run(tmp_path, target_agents=["copilot", "cursor"])
    assert results["Copilot instructions"].scorable is True
    assert results["Copilot setup steps"].scorable is True
    assert results["Cursor config"].scorable is True
    # Others not scored
    assert results["CLAUDE.md"].scorable is False
    assert results["Aider config"].scorable is False


# ── target_agents=["claude"] ────────────────────────────────────────

def test_claude_target_only_claude_scored(tmp_path):
    results = _run(tmp_path, target_agents=["claude"])
    assert results["CLAUDE.md"].scorable is True
    assert results["Copilot instructions"].scorable is False
    assert results["Cursor config"].scorable is False


# ── "Has any AI config" always present and scorable ──────────────────

def test_has_any_ai_config_always_present(tmp_path):
    results = _run(tmp_path)
    assert "Has any AI config" in results


def test_has_any_ai_config_scorable_without_target(tmp_path):
    results = _run(tmp_path)
    assert results["Has any AI config"].scorable is True


def test_has_any_ai_config_scorable_with_target(tmp_path):
    """Even with target_agents, 'Has any AI config' is still returned and scorable=True."""
    results = _run(tmp_path, target_agents=["copilot"])
    assert "Has any AI config" in results
    # Note: the checker itself doesn't change "Has any AI config" scorable;
    # it's the category_mapper that changes it. Here at checker level it stays True.
    assert results["Has any AI config"].scorable is True


# ── AGENT_REGISTRY correctness ───────────────────────────────────────

def test_agent_registry_has_expected_keys():
    expected = {"copilot", "cursor", "claude", "aider", "agents_md"}
    assert set(AGENT_REGISTRY.keys()) == expected


def test_agent_registry_copilot_checks():
    assert "copilot_instructions" in AGENT_REGISTRY["copilot"]["checks"]
    assert "copilot_setup_steps" in AGENT_REGISTRY["copilot"]["checks"]


def test_agent_registry_cursor_checks():
    assert "cursor_config" in AGENT_REGISTRY["cursor"]["checks"]


def test_agent_registry_claude_checks():
    assert "claude_md" in AGENT_REGISTRY["claude"]["checks"]

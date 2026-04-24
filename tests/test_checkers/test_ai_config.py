"""Tests for ai_readiness.checkers.ai_config.AIConfigChecker."""
from __future__ import annotations

import pytest

from ai_readiness.checkers.ai_config import AIConfigChecker
from ai_readiness.core.models import CheckStatus
from tests.conftest import create_file


class TestAIConfigChecker:
    def _run(self, tmp_path):
        checker = AIConfigChecker(repo_path=tmp_path)
        return {c.name: c for c in checker.run_checks()}

    # ── Individual AI config files ───────────────────────────────────

    def test_copilot_instructions_passes(self, tmp_path):
        create_file(tmp_path, ".github/copilot-instructions.md", "Use TypeScript.\n")
        results = self._run(tmp_path)
        assert results["Copilot instructions"].status is CheckStatus.PASS

    def test_copilot_instructions_missing_fails(self, tmp_path):
        results = self._run(tmp_path)
        assert results["Copilot instructions"].status is CheckStatus.FAIL

    def test_copilot_setup_steps_passes(self, tmp_path):
        create_file(tmp_path, ".github/copilot-setup-steps.yml", "steps:\n")
        results = self._run(tmp_path)
        assert results["Copilot setup steps"].status is CheckStatus.PASS

    def test_cursorrules_passes(self, tmp_path):
        create_file(tmp_path, ".cursorrules", "rules:\n")
        results = self._run(tmp_path)
        assert results["Cursor config"].status is CheckStatus.PASS

    def test_cursor_dir_passes(self, tmp_path):
        create_file(tmp_path, ".cursor/rules.json", "{}")
        results = self._run(tmp_path)
        assert results["Cursor config"].status is CheckStatus.PASS

    def test_cursor_missing_fails(self, tmp_path):
        results = self._run(tmp_path)
        assert results["Cursor config"].status is CheckStatus.FAIL

    def test_agents_md_passes(self, tmp_path):
        create_file(tmp_path, "AGENTS.md", "## Agents\n")
        results = self._run(tmp_path)
        assert results["AGENTS.md"].status is CheckStatus.PASS

    def test_claude_md_passes(self, tmp_path):
        create_file(tmp_path, "CLAUDE.md", "## Claude\n")
        results = self._run(tmp_path)
        assert results["CLAUDE.md"].status is CheckStatus.PASS

    def test_aider_config_passes(self, tmp_path):
        create_file(tmp_path, ".aider.conf.yml", "model: gpt-4\n")
        results = self._run(tmp_path)
        assert results["Aider config"].status is CheckStatus.PASS

    def test_aiderignore_passes(self, tmp_path):
        create_file(tmp_path, ".aiderignore", "*.log\n")
        results = self._run(tmp_path)
        assert results["Aider config"].status is CheckStatus.PASS

    # ── Has-any-AI-config aggregator ─────────────────────────────────

    def test_empty_repo_has_no_ai_config(self, tmp_path):
        results = self._run(tmp_path)
        assert results["Has any AI config"].status is CheckStatus.FAIL

    def test_single_ai_file_triggers_has_any(self, tmp_path):
        create_file(tmp_path, "CLAUDE.md", "instructions")
        results = self._run(tmp_path)
        assert results["Has any AI config"].status is CheckStatus.PASS

    def test_cursor_dir_triggers_has_any(self, tmp_path):
        create_file(tmp_path, ".cursor/settings.json", "{}")
        results = self._run(tmp_path)
        assert results["Has any AI config"].status is CheckStatus.PASS

    # ── evaluate() ───────────────────────────────────────────────────

    def test_evaluate_empty_repo(self, tmp_path):
        checker = AIConfigChecker(repo_path=tmp_path)
        ds = checker.evaluate()
        assert ds.dimension_id == "ai_config"
        assert ds.score == 0.0

    def test_evaluate_all_configs(self, tmp_path):
        create_file(tmp_path, ".github/copilot-instructions.md", "x")
        create_file(tmp_path, ".github/copilot-setup-steps.yml", "x")
        create_file(tmp_path, ".cursorrules", "x")
        create_file(tmp_path, "AGENTS.md", "x")
        create_file(tmp_path, "CLAUDE.md", "x")
        create_file(tmp_path, ".aider.conf.yml", "x")

        checker = AIConfigChecker(repo_path=tmp_path)
        ds = checker.evaluate()
        assert ds.score == 10.0

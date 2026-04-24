"""Tests for ai_readiness.checkers.code_quality.CodeQualityChecker."""
from __future__ import annotations

import pytest

from ai_readiness.checkers.code_quality import CodeQualityChecker
from ai_readiness.core.models import CheckStatus
from tests.conftest import create_file


class TestCodeQualityChecker:
    def _run(self, tmp_path, languages=None):
        checker = CodeQualityChecker(repo_path=tmp_path, languages=languages)
        return {c.name: c for c in checker.run_checks()}

    # ── .editorconfig ────────────────────────────────────────────────

    def test_editorconfig_present_passes(self, tmp_path):
        create_file(tmp_path, ".editorconfig", "root = true\n")
        results = self._run(tmp_path)
        assert results[".editorconfig"].status is CheckStatus.PASS

    def test_editorconfig_missing_fails(self, tmp_path):
        results = self._run(tmp_path)
        assert results[".editorconfig"].status is CheckStatus.FAIL

    # ── Type checking ────────────────────────────────────────────────

    def test_tsconfig_passes(self, tmp_path):
        create_file(tmp_path, "tsconfig.json", '{"compilerOptions": {}}')
        results = self._run(tmp_path)
        assert results["Type checking enabled"].status is CheckStatus.PASS

    def test_sln_passes(self, tmp_path):
        create_file(tmp_path, "MyApp.sln", "Microsoft Visual Studio Solution")
        results = self._run(tmp_path)
        assert results["Type checking enabled"].status is CheckStatus.PASS

    def test_csproj_passes(self, tmp_path):
        create_file(tmp_path, "MyApp.csproj", "<Project></Project>")
        results = self._run(tmp_path)
        assert results["Type checking enabled"].status is CheckStatus.PASS

    def test_cargo_toml_passes(self, tmp_path):
        create_file(tmp_path, "Cargo.toml", "[package]\nname = 'app'\n")
        results = self._run(tmp_path)
        assert results["Type checking enabled"].status is CheckStatus.PASS

    def test_go_mod_passes(self, tmp_path):
        create_file(tmp_path, "go.mod", "module example.com/app\n")
        results = self._run(tmp_path)
        assert results["Type checking enabled"].status is CheckStatus.PASS

    def test_mypy_in_pyproject_passes(self, tmp_path):
        create_file(tmp_path, "pyproject.toml", "[tool.mypy]\nstrict = true\n")
        results = self._run(tmp_path)
        assert results["Type checking enabled"].status is CheckStatus.PASS

    def test_no_type_checking_fails(self, tmp_path):
        create_file(tmp_path, "src/main.py", "pass")
        results = self._run(tmp_path)
        assert results["Type checking enabled"].status is CheckStatus.FAIL

    # ── Linter ───────────────────────────────────────────────────────

    def test_eslintrc_passes(self, tmp_path):
        create_file(tmp_path, ".eslintrc.json", '{"rules": {}}')
        results = self._run(tmp_path)
        assert results["Linter configured"].status is CheckStatus.PASS

    def test_ruff_in_pyproject_passes(self, tmp_path):
        create_file(tmp_path, "pyproject.toml", "[tool.ruff]\nline-length = 120\n")
        results = self._run(tmp_path)
        assert results["Linter configured"].status is CheckStatus.PASS

    def test_no_linter_fails(self, tmp_path):
        create_file(tmp_path, "src/main.py", "pass")
        results = self._run(tmp_path)
        assert results["Linter configured"].status is CheckStatus.FAIL

    # ── Formatter ────────────────────────────────────────────────────

    def test_prettierrc_passes(self, tmp_path):
        create_file(tmp_path, ".prettierrc", '{"semi": true}')
        results = self._run(tmp_path)
        assert results["Formatter configured"].status is CheckStatus.PASS

    def test_editorconfig_as_formatter_passes(self, tmp_path):
        create_file(tmp_path, ".editorconfig", "root = true\n")
        results = self._run(tmp_path)
        assert results["Formatter configured"].status is CheckStatus.PASS

    def test_no_formatter_fails(self, tmp_path):
        create_file(tmp_path, "src/main.py", "pass")
        results = self._run(tmp_path)
        assert results["Formatter configured"].status is CheckStatus.FAIL

    # ── File sizes ───────────────────────────────────────────────────

    def test_no_source_files_skip(self, tmp_path):
        results = self._run(tmp_path)
        assert results["Reasonable file sizes"].status is CheckStatus.SKIP

    def test_small_files_pass(self, tmp_path):
        for i in range(5):
            create_file(tmp_path, f"src/mod_{i}.py", "x = 1\n" * 50)
        results = self._run(tmp_path)
        assert results["Reasonable file sizes"].status is CheckStatus.PASS

    # ── evaluate() ───────────────────────────────────────────────────

    def test_evaluate_empty_repo(self, tmp_path):
        checker = CodeQualityChecker(repo_path=tmp_path)
        ds = checker.evaluate()
        assert ds.dimension_id == "code_quality"
        assert 0.0 <= ds.score <= 10.0

"""Tests for ai_readiness.checkers.testing.TestingChecker."""
from __future__ import annotations

import pytest

from ai_readiness.checkers.testing import TestingChecker
from ai_readiness.core.models import CheckStatus
from tests.conftest import create_file


class TestTestingChecker:
    """TestingChecker — language-agnostic test & CI/CD detection."""

    def _run(self, tmp_path):
        checker = TestingChecker(repo_path=tmp_path)
        return {c.name: c for c in checker.run_checks()}

    # ── Test files ───────────────────────────────────────────────────

    def test_tests_dir_passes(self, tmp_path):
        create_file(tmp_path, "tests/test_foo.py", "def test_foo(): pass")
        results = self._run(tmp_path)
        assert results["Test files exist"].status is CheckStatus.PASS

    def test_spec_dir_passes(self, tmp_path):
        create_file(tmp_path, "spec/widget_spec.rb", "")
        results = self._run(tmp_path)
        assert results["Test files exist"].status is CheckStatus.PASS

    def test_src_unittests_passes(self, tmp_path):
        create_file(tmp_path, "src/UnitTests/foo_test.cs", "")
        results = self._run(tmp_path)
        assert results["Test files exist"].status is CheckStatus.PASS

    def test_no_tests_fails(self, tmp_path):
        create_file(tmp_path, "src/app.py", "print('hello')")
        results = self._run(tmp_path)
        assert results["Test files exist"].status is CheckStatus.FAIL

    def test_deep_test_file_found(self, tmp_path):
        create_file(tmp_path, "src/lib/deep/test_helper.py", "")
        results = self._run(tmp_path)
        assert results["Test files exist"].status is CheckStatus.PASS

    # ── Test runner config ───────────────────────────────────────────

    def test_pytest_in_pyproject_passes(self, tmp_path):
        create_file(tmp_path, "pyproject.toml", "[tool.pytest]\n")
        results = self._run(tmp_path)
        assert results["Test runner config"].status is CheckStatus.PASS

    def test_jest_in_package_json_passes(self, tmp_path):
        create_file(tmp_path, "package.json", '{"jest": {}}')
        results = self._run(tmp_path)
        assert results["Test runner config"].status is CheckStatus.PASS

    def test_no_runner_config_fails(self, tmp_path):
        create_file(tmp_path, "src/main.py", "pass")
        results = self._run(tmp_path)
        assert results["Test runner config"].status is CheckStatus.FAIL

    # ── CI/CD pipeline ───────────────────────────────────────────────

    def test_github_workflows_passes(self, tmp_path):
        create_file(tmp_path, ".github/workflows/ci.yml", "on: push\n")
        results = self._run(tmp_path)
        assert results["CI/CD pipeline"].status is CheckStatus.PASS

    def test_pipelines_dir_passes(self, tmp_path):
        create_file(tmp_path, ".pipelines/build.yml", "steps:\n")
        results = self._run(tmp_path)
        assert results["CI/CD pipeline"].status is CheckStatus.PASS

    def test_azure_pipelines_root_passes(self, tmp_path):
        create_file(tmp_path, "azure-pipelines.yml", "trigger:\n  - main\n")
        results = self._run(tmp_path)
        assert results["CI/CD pipeline"].status is CheckStatus.PASS

    def test_gitlab_ci_passes(self, tmp_path):
        create_file(tmp_path, ".gitlab-ci.yml", "stages:\n  - test\n")
        results = self._run(tmp_path)
        assert results["CI/CD pipeline"].status is CheckStatus.PASS

    def test_no_ci_fails(self, tmp_path):
        create_file(tmp_path, "src/main.py", "pass")
        results = self._run(tmp_path)
        assert results["CI/CD pipeline"].status is CheckStatus.FAIL

    def test_build_dir_yaml_passes(self, tmp_path):
        create_file(tmp_path, "build/pipeline.yml", "steps:\n")
        results = self._run(tmp_path)
        assert results["CI/CD pipeline"].status is CheckStatus.PASS

    # ── Coverage config ──────────────────────────────────────────────

    def test_coveragerc_passes(self, tmp_path):
        create_file(tmp_path, ".coveragerc", "[run]\nsource=.\n")
        results = self._run(tmp_path)
        assert results["Coverage config"].status is CheckStatus.PASS

    def test_coverage_in_pyproject_passes(self, tmp_path):
        create_file(tmp_path, "pyproject.toml", "[tool.coverage.run]\nsource = ['.']\n")
        results = self._run(tmp_path)
        assert results["Coverage config"].status is CheckStatus.PASS

    def test_no_coverage_fails(self, tmp_path):
        create_file(tmp_path, "src/main.py", "pass")
        results = self._run(tmp_path)
        assert results["Coverage config"].status is CheckStatus.FAIL

    # ── evaluate() integration ───────────────────────────────────────

    def test_evaluate_empty_repo(self, tmp_path):
        checker = TestingChecker(repo_path=tmp_path)
        ds = checker.evaluate()
        assert ds.dimension_id == "testing"
        assert 0.0 <= ds.score <= 10.0

    def test_evaluate_full_repo(self, tmp_path):
        create_file(tmp_path, "tests/test_a.py", "pass")
        create_file(tmp_path, "pyproject.toml", "[tool.pytest]\n")
        create_file(tmp_path, ".github/workflows/ci.yml", "on: push\n")
        create_file(tmp_path, ".coveragerc", "[run]\n")

        checker = TestingChecker(repo_path=tmp_path)
        ds = checker.evaluate()
        assert ds.score == 10.0

"""Tests for ai_readiness.checkers.documentation.DocumentationChecker."""
from __future__ import annotations

import pytest

from ai_readiness.checkers.documentation import DocumentationChecker
from ai_readiness.core.models import CheckStatus
from tests.conftest import create_file


class TestDocumentationChecker:
    """DocumentationChecker assessed via tmp_path fixtures."""

    def _run(self, tmp_path):
        checker = DocumentationChecker(repo_path=tmp_path)
        return {c.name: c for c in checker.run_checks()}

    # ── README existence ─────────────────────────────────────────────

    def test_no_readme_fails(self, tmp_path):
        results = self._run(tmp_path)
        assert results["README exists"].status is CheckStatus.FAIL

    def test_small_readme_warns(self, tmp_path):
        create_file(tmp_path, "README.md", "x" * 100)
        results = self._run(tmp_path)
        assert results["README exists"].status is CheckStatus.WARN

    def test_large_readme_passes(self, tmp_path):
        create_file(tmp_path, "README.md", "x" * 600)
        results = self._run(tmp_path)
        assert results["README exists"].status is CheckStatus.PASS

    def test_readme_rst_accepted(self, tmp_path):
        create_file(tmp_path, "README.rst", "x" * 600)
        results = self._run(tmp_path)
        assert results["README exists"].status is CheckStatus.PASS

    # ── README sections ──────────────────────────────────────────────

    def test_no_readme_sections_skip(self, tmp_path):
        results = self._run(tmp_path)
        assert results["README key sections"].status is CheckStatus.SKIP

    def test_readme_with_all_sections_passes(self, tmp_path):
        content = (
            "# Project\n\n"
            "## Installation\nRun pip install.\n\n"
            "## Usage\nImport and call.\n\n"
            "## Contributing\nSee CONTRIBUTING.md.\n"
        )
        create_file(tmp_path, "README.md", content)
        results = self._run(tmp_path)
        assert results["README key sections"].status is CheckStatus.PASS

    def test_readme_missing_some_sections_warns(self, tmp_path):
        content = "# Project\n\n## Installation\nRun pip install.\n"
        create_file(tmp_path, "README.md", content)
        results = self._run(tmp_path)
        assert results["README key sections"].status is CheckStatus.WARN

    def test_readme_no_sections_fails(self, tmp_path):
        create_file(tmp_path, "README.md", "# Hello\nJust text, no key sections.\n")
        results = self._run(tmp_path)
        assert results["README key sections"].status is CheckStatus.FAIL

    # ── CONTRIBUTING ─────────────────────────────────────────────────

    def test_contributing_present_passes(self, tmp_path):
        create_file(tmp_path, "CONTRIBUTING.md", "## How to contribute")
        results = self._run(tmp_path)
        assert results["CONTRIBUTING guide"].status is CheckStatus.PASS

    def test_contributing_absent_fails(self, tmp_path):
        results = self._run(tmp_path)
        assert results["CONTRIBUTING guide"].status is CheckStatus.FAIL

    # ── Architecture / design docs ───────────────────────────────────

    def test_architecture_md_passes(self, tmp_path):
        create_file(tmp_path, "ARCHITECTURE.md", "overview")
        results = self._run(tmp_path)
        assert results["Architecture / design docs"].status is CheckStatus.PASS

    def test_docs_dir_passes(self, tmp_path):
        create_file(tmp_path, "docs/design.md", "stuff")
        results = self._run(tmp_path)
        assert results["Architecture / design docs"].status is CheckStatus.PASS

    def test_no_docs_fails(self, tmp_path):
        results = self._run(tmp_path)
        assert results["Architecture / design docs"].status is CheckStatus.FAIL

    # ── CODE_OF_CONDUCT ──────────────────────────────────────────────

    def test_code_of_conduct_passes(self, tmp_path):
        create_file(tmp_path, "CODE_OF_CONDUCT.md", "be nice")
        results = self._run(tmp_path)
        assert results["CODE_OF_CONDUCT"].status is CheckStatus.PASS

    def test_no_code_of_conduct_fails(self, tmp_path):
        results = self._run(tmp_path)
        assert results["CODE_OF_CONDUCT"].status is CheckStatus.FAIL

    # ── CHANGELOG ────────────────────────────────────────────────────

    def test_changelog_passes(self, tmp_path):
        create_file(tmp_path, "CHANGELOG.md", "## 1.0\nInitial release.")
        results = self._run(tmp_path)
        assert results["CHANGELOG"].status is CheckStatus.PASS

    def test_no_changelog_fails(self, tmp_path):
        results = self._run(tmp_path)
        assert results["CHANGELOG"].status is CheckStatus.FAIL

    # ── Full repo scenario ───────────────────────────────────────────

    def test_full_repo_all_pass(self, tmp_path):
        readme = (
            "# My Project\n\n"
            "## Getting Started\nInstall it.\n\n"
            "## Usage\nUse it.\n\n"
            "## Contributing\nHelp us.\n"
        )
        create_file(tmp_path, "README.md", readme + "x" * 500)
        create_file(tmp_path, "CONTRIBUTING.md", "## Contributing\n")
        create_file(tmp_path, "ARCHITECTURE.md", "## Overview\n")
        create_file(tmp_path, "CODE_OF_CONDUCT.md", "Be nice\n")
        create_file(tmp_path, "CHANGELOG.md", "## 1.0\nRelease\n")

        results = self._run(tmp_path)
        for name, check in results.items():
            assert check.status in (CheckStatus.PASS, CheckStatus.SKIP), (
                f"{name} unexpectedly {check.status.value}: {check.message}"
            )

    # ── evaluate() integration ───────────────────────────────────────

    def test_evaluate_returns_dimension_score(self, tmp_path):
        checker = DocumentationChecker(repo_path=tmp_path)
        ds = checker.evaluate()
        assert ds.dimension_id == "documentation"
        assert ds.dimension_name == "Documentation"
        assert 0.0 <= ds.score <= 10.0

"""Checker for project documentation quality and completeness."""
from __future__ import annotations

import re
from typing import Optional

from pathlib import Path

from ai_readiness.checkers.base import BaseChecker
from ai_readiness.core.models import CheckResult, CheckStatus


class DocumentationChecker(BaseChecker):
    """Assess the quality and presence of project documentation."""

    dimension_id: str = "documentation"
    dimension_name: str = "Documentation"
    default_weight: float = 20.0

    def run_checks(self) -> list[CheckResult]:
        results: list[CheckResult] = []
        results.append(self._check_readme_exists())
        results.append(self._check_readme_sections())
        results.append(self._check_contributing())
        results.append(self._check_architecture_docs())
        results.append(self._check_code_of_conduct())
        results.append(self._check_changelog())
        return results

    # ------------------------------------------------------------------

    def _check_readme_exists(self) -> CheckResult:
        readme = self.file_exists("README.md", "README.rst", "README.txt", "README")
        if readme is None:
            return CheckResult(
                name="README exists",
                status=CheckStatus.FAIL,
                message="No README file found.",
                recommendation="Add a README.md with project overview, setup instructions, and usage examples.",
            )
        content = self.read_file_safe(readme) or ""
        if len(content) < 500:
            return CheckResult(
                name="README exists",
                status=CheckStatus.WARN,
                message=f"README found but is thin ({len(content)} chars).",
                recommendation="Expand the README to at least 500 characters with meaningful project information.",
            )
        return CheckResult(
            name="README exists",
            status=CheckStatus.PASS,
            message=f"README found with substantial content ({len(content)} chars).",
        )

    def _check_readme_sections(self) -> CheckResult:
        readme = self.file_exists("README.md", "README.rst", "README.txt", "README")
        if readme is None:
            return CheckResult(
                name="README key sections",
                status=CheckStatus.SKIP,
                message="No README to analyse.",
            )
        content = self.read_file_safe(readme) or ""
        expected = {
            "install/setup": re.compile(r"(?i)#+ .*(?:install|setup|getting.started)"),
            "usage": re.compile(r"(?i)#+ .*usage"),
            "contributing": re.compile(r"(?i)#+ .*contribut"),
        }
        found = {k for k, pat in expected.items() if pat.search(content)}
        missing = set(expected) - found
        if not missing:
            return CheckResult(
                name="README key sections",
                status=CheckStatus.PASS,
                message="README contains install/setup, usage, and contributing sections.",
            )
        if found:
            return CheckResult(
                name="README key sections",
                status=CheckStatus.WARN,
                message=f"README is missing sections: {', '.join(sorted(missing))}.",
                recommendation=f"Add the following sections to the README: {', '.join(sorted(missing))}.",
            )
        return CheckResult(
            name="README key sections",
            status=CheckStatus.FAIL,
            message="README lacks key sections (install/setup, usage, contributing).",
            recommendation="Add headings for installation/setup, usage, and contributing to the README.",
        )

    def _check_contributing(self) -> CheckResult:
        if self.files_exist_any("CONTRIBUTING.md", "CONTRIBUTING.rst", "CONTRIBUTING.txt"):
            return CheckResult(
                name="CONTRIBUTING guide",
                status=CheckStatus.PASS,
                message="CONTRIBUTING file found.",
            )
        return CheckResult(
            name="CONTRIBUTING guide",
            status=CheckStatus.FAIL,
            message="No CONTRIBUTING file found.",
            recommendation="Add a CONTRIBUTING.md describing how to contribute, run tests, and submit PRs.",
        )

    def _check_architecture_docs(self) -> CheckResult:
        if self.files_exist_any("ARCHITECTURE.md", "DESIGN.md"):
            return CheckResult(
                name="Architecture / design docs",
                status=CheckStatus.PASS,
                message="Architecture or design document found.",
            )
        docs_dir = self.repo_path / "docs"
        if docs_dir.is_dir() and any(docs_dir.iterdir()):
            return CheckResult(
                name="Architecture / design docs",
                status=CheckStatus.PASS,
                message="docs/ directory with content found.",
            )
        return CheckResult(
            name="Architecture / design docs",
            status=CheckStatus.FAIL,
            message="No architecture or design documentation found.",
            recommendation="Add an ARCHITECTURE.md, DESIGN.md, or a docs/ directory with design documentation.",
        )

    def _check_code_of_conduct(self) -> CheckResult:
        if self.files_exist_any("CODE_OF_CONDUCT.md", "CODE_OF_CONDUCT.txt"):
            return CheckResult(
                name="CODE_OF_CONDUCT",
                status=CheckStatus.PASS,
                message="Code of conduct found.",
            )
        return CheckResult(
            name="CODE_OF_CONDUCT",
            status=CheckStatus.FAIL,
            message="No CODE_OF_CONDUCT file found.",
            recommendation="Add a CODE_OF_CONDUCT.md to set community expectations.",
        )

    def _check_changelog(self) -> CheckResult:
        if self.files_exist_any("CHANGELOG.md", "CHANGES.md", "CHANGELOG.rst", "CHANGES.rst"):
            return CheckResult(
                name="CHANGELOG",
                status=CheckStatus.PASS,
                message="Changelog found.",
            )
        return CheckResult(
            name="CHANGELOG",
            status=CheckStatus.FAIL,
            message="No CHANGELOG or CHANGES file found.",
            recommendation="Add a CHANGELOG.md to track notable changes across releases.",
        )

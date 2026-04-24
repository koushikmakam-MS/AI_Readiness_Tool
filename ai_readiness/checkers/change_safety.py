"""Checker for change safety guardrails and contribution workflows."""
from __future__ import annotations

from ai_readiness.checkers.base import BaseChecker
from ai_readiness.core.models import CheckResult, CheckStatus


class ChangeSafetyChecker(BaseChecker):
    """Assess guardrails that protect the codebase during changes."""

    dimension_id: str = "change_safety"
    dimension_name: str = "Change Safety & Guardrails"
    default_weight: float = 7.0

    def run_checks(self) -> list[CheckResult]:
        results: list[CheckResult] = []
        results.append(self._check_pr_template())
        results.append(self._check_issue_templates())
        results.append(self._check_pre_commit_hooks())
        results.append(self._check_security_md())
        results.append(self._check_gitignore_comprehensive())
        return results

    # ------------------------------------------------------------------

    def _check_pr_template(self) -> CheckResult:
        if self.files_exist_any(
            ".github/pull_request_template.md",
            ".github/PULL_REQUEST_TEMPLATE.md",
        ):
            return CheckResult(
                name="PR template",
                status=CheckStatus.PASS,
                message="Pull request template found.",
            )
        pr_dir = self.repo_path / ".github" / "PULL_REQUEST_TEMPLATE"
        if pr_dir.is_dir() and any(pr_dir.iterdir()):
            return CheckResult(
                name="PR template",
                status=CheckStatus.PASS,
                message="Pull request template directory found.",
            )
        return CheckResult(
            name="PR template",
            status=CheckStatus.FAIL,
            message="No pull request template found.",
            recommendation="Add .github/pull_request_template.md to guide contributors when opening PRs.",
        )

    def _check_issue_templates(self) -> CheckResult:
        if self.files_exist_any(
            ".github/issue_template.md",
            ".github/ISSUE_TEMPLATE.md",
        ):
            return CheckResult(
                name="Issue templates",
                status=CheckStatus.PASS,
                message="Issue template found.",
            )
        issue_dir = self.repo_path / ".github" / "ISSUE_TEMPLATE"
        if issue_dir.is_dir() and any(issue_dir.iterdir()):
            return CheckResult(
                name="Issue templates",
                status=CheckStatus.PASS,
                message="Issue template directory found.",
            )
        return CheckResult(
            name="Issue templates",
            status=CheckStatus.FAIL,
            message="No issue templates found.",
            recommendation="Add .github/ISSUE_TEMPLATE/ with bug report and feature request templates.",
        )

    def _check_pre_commit_hooks(self) -> CheckResult:
        if self.files_exist_any(".pre-commit-config.yaml"):
            return CheckResult(
                name="Pre-commit hooks",
                status=CheckStatus.PASS,
                message="pre-commit configuration found.",
            )
        husky_dir = self.repo_path / ".husky"
        if husky_dir.is_dir() and any(husky_dir.iterdir()):
            return CheckResult(
                name="Pre-commit hooks",
                status=CheckStatus.PASS,
                message="Husky git hooks found.",
            )
        githooks_dir = self.repo_path / ".githooks"
        if githooks_dir.is_dir() and any(githooks_dir.iterdir()):
            return CheckResult(
                name="Pre-commit hooks",
                status=CheckStatus.PASS,
                message=".githooks/ directory found.",
            )
        return CheckResult(
            name="Pre-commit hooks",
            status=CheckStatus.FAIL,
            message="No pre-commit hook configuration found.",
            recommendation="Add .pre-commit-config.yaml or .husky/ to run automated checks before commits.",
        )

    def _check_security_md(self) -> CheckResult:
        if self.files_exist_any("SECURITY.md", "SECURITY.txt"):
            return CheckResult(
                name="SECURITY.md",
                status=CheckStatus.PASS,
                message="Security policy found.",
            )
        return CheckResult(
            name="SECURITY.md",
            status=CheckStatus.FAIL,
            message="No SECURITY.md found.",
            recommendation="Add a SECURITY.md with vulnerability reporting instructions.",
        )

    def _check_gitignore_comprehensive(self) -> CheckResult:
        gitignore = self.file_exists(".gitignore")
        if gitignore is None:
            return CheckResult(
                name=".gitignore comprehensive",
                status=CheckStatus.FAIL,
                message="No .gitignore file found.",
                recommendation="Add a .gitignore to prevent committing build artifacts and sensitive files.",
            )
        content = self.read_file_safe(gitignore) or ""
        entries = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        if len(entries) <= 5:
            return CheckResult(
                name=".gitignore comprehensive",
                status=CheckStatus.WARN,
                message=f".gitignore has only {len(entries)} entries — may be incomplete.",
                recommendation="Expand .gitignore to cover build outputs, dependencies, IDE files, and secrets.",
            )
        return CheckResult(
            name=".gitignore comprehensive",
            status=CheckStatus.PASS,
            message=f".gitignore is comprehensive ({len(entries)} entries).",
        )

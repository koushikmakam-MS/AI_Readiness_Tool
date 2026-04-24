"""Checker for dependency management practices."""
from __future__ import annotations

from ai_readiness.checkers.base import BaseChecker
from ai_readiness.core.models import CheckResult, CheckStatus


class DependencyChecker(BaseChecker):
    """Assess dependency management hygiene."""

    dimension_id: str = "dependency"
    dimension_name: str = "Dependency Management"
    default_weight: float = 8.0

    def run_checks(self) -> list[CheckResult]:
        results: list[CheckResult] = []
        results.append(self._check_dependency_manifest())
        results.append(self._check_lock_file())
        results.append(self._check_gitignore())
        return results

    # ------------------------------------------------------------------

    def _check_dependency_manifest(self) -> CheckResult:
        manifests = [
            "package.json",
            "requirements.txt",
            "Pipfile",
            "pyproject.toml",
            "go.mod",
            "Cargo.toml",
            "Gemfile",
            "composer.json",
            "pom.xml",
            "build.gradle",
            "build.gradle.kts",
        ]
        for m in manifests:
            if self.files_exist_any(m):
                return CheckResult(
                    name="Dependency manifest",
                    status=CheckStatus.PASS,
                    message=f"Dependency manifest ({m}) found.",
                )
        return CheckResult(
            name="Dependency manifest",
            status=CheckStatus.FAIL,
            message="No dependency manifest found.",
            recommendation=(
                "Add a dependency manifest (e.g. package.json, requirements.txt, pyproject.toml) "
                "so dependencies are explicitly declared."
            ),
        )

    def _check_lock_file(self) -> CheckResult:
        lock_files = [
            "package-lock.json",
            "yarn.lock",
            "pnpm-lock.yaml",
            "Pipfile.lock",
            "poetry.lock",
            "go.sum",
            "Cargo.lock",
            "Gemfile.lock",
            "composer.lock",
        ]
        for lf in lock_files:
            if self.files_exist_any(lf):
                return CheckResult(
                    name="Lock file",
                    status=CheckStatus.PASS,
                    message=f"Dependency lock file ({lf}) found.",
                )
        return CheckResult(
            name="Lock file",
            status=CheckStatus.FAIL,
            message="No dependency lock file found.",
            recommendation="Commit a lock file (e.g. package-lock.json, poetry.lock) for reproducible builds.",
        )

    def _check_gitignore(self) -> CheckResult:
        if self.files_exist_any(".gitignore"):
            return CheckResult(
                name=".gitignore",
                status=CheckStatus.PASS,
                message=".gitignore file found.",
            )
        return CheckResult(
            name=".gitignore",
            status=CheckStatus.FAIL,
            message="No .gitignore file found.",
            recommendation="Add a .gitignore to prevent committing build artifacts, secrets, and dependencies.",
        )

"""Checker for testing and verification practices.

Uses a generic-first detection strategy:
  1. Scan for directories/files with 'test' or 'spec' in their name (any language)
  2. Scan for CI/CD directories and pipeline files (any provider)
  3. Scan for coverage keywords in config files (any framework)

No language-specific hardcoding — works with any stack.
"""
from __future__ import annotations

import re
from pathlib import Path

from ai_readiness.checkers.base import BaseChecker
from ai_readiness.core.models import CheckResult, CheckStatus

# Directories to skip during generic scanning
_SKIP_PARTS = frozenset({
    "node_modules", ".git", "vendor", "dist", "__pycache__",
    ".venv", "venv", "env", ".tox", ".mypy_cache", ".pytest_cache",
    "packages", ".vs", ".vscode", "out", "obj", "bin", "target",
})

# Keywords that signal "this is a test" when found in file/directory names
_TEST_KEYWORDS = re.compile(r"(?i)(test|spec|__tests__)")

# Known CI/CD directory names (generic)
_CI_DIRS = [
    ".github/workflows", ".pipelines", ".circleci",
    ".buildkite", ".teamcity", ".azure-pipelines",
]

# Known CI/CD file names/patterns at repo root
_CI_ROOT_FILES = [
    "Jenkinsfile", ".travis.yml", ".gitlab-ci.yml",
    "appveyor.yml", "bitbucket-pipelines.yml",
    "cloudbuild.yaml", "cloudbuild.json",
    "Taskfile.yml", "taskcluster",
]


def _is_skippable(path: Path, repo_root: Path) -> bool:
    """Check if path is inside a directory we should skip."""
    try:
        parts = path.relative_to(repo_root).parts
    except ValueError:
        return True
    return bool(_SKIP_PARTS & set(parts))


class TestingChecker(BaseChecker):
    """Assess testing and CI/CD infrastructure — language agnostic."""

    dimension_id: str = "testing"
    dimension_name: str = "Testing & Verification"
    default_weight: float = 20.0

    def run_checks(self) -> list[CheckResult]:
        return [
            self._check_test_files(),
            self._check_test_runner_config(),
            self._check_ci_cd(),
            self._check_coverage_config(),
        ]

    # ------------------------------------------------------------------
    # 1. Test files — generic scan
    # ------------------------------------------------------------------

    def _check_test_files(self) -> CheckResult:
        # Strategy: walk top-level dirs looking for any directory or file
        # whose name contains "test" or "spec" (case-insensitive).
        # This catches *every* language convention without hardcoding.

        found_dirs: list[str] = []
        found_files: list[str] = []

        for item in self.repo_path.iterdir():
            if _is_skippable(item, self.repo_path):
                continue
            if _TEST_KEYWORDS.search(item.name):
                if item.is_dir():
                    found_dirs.append(item.name)
                elif item.is_file():
                    found_files.append(item.name)

        # Also check one level inside src/ (common: src/test, src/UnitTests, etc.)
        src_dir = self.repo_path / "src"
        if src_dir.is_dir():
            for item in src_dir.iterdir():
                if _TEST_KEYWORDS.search(item.name):
                    rel = f"src/{item.name}"
                    if item.is_dir():
                        found_dirs.append(rel)
                    elif item.is_file():
                        found_files.append(rel)

        if found_dirs:
            return CheckResult(
                name="Test files exist",
                status=CheckStatus.PASS,
                message=f"Found test directories: {', '.join(sorted(found_dirs)[:5])}",
            )

        if found_files:
            return CheckResult(
                name="Test files exist",
                status=CheckStatus.PASS,
                message=f"Found test files: {', '.join(sorted(found_files)[:5])}",
            )

        # Deep scan — walk first 3000 files looking for *test* or *spec*
        count = 0
        for item in self.repo_path.rglob("*"):
            if item.is_file() and not _is_skippable(item, self.repo_path):
                if _TEST_KEYWORDS.search(item.name):
                    return CheckResult(
                        name="Test files exist",
                        status=CheckStatus.PASS,
                        message=f"Found test file: {item.relative_to(self.repo_path)}",
                    )
                count += 1
                if count >= 3000:
                    break

        return CheckResult(
            name="Test files exist",
            status=CheckStatus.FAIL,
            message="No test files or test directories found.",
            recommendation=(
                "Add test files following your language's conventions. "
                "Place them in a tests/, test/, or spec/ directory."
            ),
        )

    # ------------------------------------------------------------------
    # 2. Test runner config — scan project manifests for test keywords
    # ------------------------------------------------------------------

    def _check_test_runner_config(self) -> CheckResult:
        # Strategy: look for ANY file at repo root whose name hints at
        # a test runner or test config, then check inside project manifests
        # for test-related keywords.

        # Generic: any root-level file with "test" in the name and a config extension
        config_exts = {".json", ".yml", ".yaml", ".xml", ".toml", ".ini", ".cfg", ".js", ".ts", ".mjs", ".cjs"}
        for item in self.repo_path.iterdir():
            if item.is_file() and item.suffix.lower() in config_exts:
                name_lower = item.name.lower()
                if _TEST_KEYWORDS.search(name_lower) and not name_lower.startswith("test_"):
                    return CheckResult(
                        name="Test runner config",
                        status=CheckStatus.PASS,
                        message=f"Test runner configuration found: {item.name}",
                    )

        # Check inside project manifest files for test framework references
        test_framework_keywords = re.compile(
            r"(?i)(pytest|jest|vitest|mocha|jasmine|karma|junit|nunit|xunit|mstest|"
            r"rspec|minitest|phpunit|pester|catch2|gtest|googletest|boost[._]test|"
            r"testng|spock|scalatest|exunit|mix.*test|cargo.*test|go.*test|"
            r"testing\.T|test_framework|test.runner|coverlet)"
        )

        manifest_files = [
            "pyproject.toml", "setup.cfg", "setup.py", "tox.ini",
            "package.json", "Cargo.toml", "Gemfile", "composer.json",
            "build.gradle", "build.gradle.kts", "pom.xml", "mix.exs",
            "go.mod",
        ]
        for name in manifest_files:
            path = self.repo_path / name
            if path.is_file():
                content = self.read_file_safe(path) or ""
                if test_framework_keywords.search(content):
                    return CheckResult(
                        name="Test runner config",
                        status=CheckStatus.PASS,
                        message=f"Test framework reference found in {name}.",
                    )

        # Check solution / project files for test references (generic glob)
        for pattern in ("*.sln", "*.csproj", "*.fsproj", "*.vbproj"):
            for proj_file in self.repo_path.glob(pattern):
                content = self.read_file_safe(proj_file) or ""
                if test_framework_keywords.search(content):
                    return CheckResult(
                        name="Test runner config",
                        status=CheckStatus.PASS,
                        message=f"Test framework reference found in {proj_file.name}.",
                    )

        return CheckResult(
            name="Test runner config",
            status=CheckStatus.FAIL,
            message="No test runner configuration found.",
            recommendation=(
                "Add a test runner config appropriate for your stack. "
                "This helps AI agents discover how to run tests."
            ),
        )

    # ------------------------------------------------------------------
    # 3. CI/CD — generic pipeline detection
    # ------------------------------------------------------------------

    def _check_ci_cd(self) -> CheckResult:
        # Check known CI/CD directories
        for ci_dir in _CI_DIRS:
            dir_path = self.repo_path / ci_dir
            if dir_path.is_dir() and any(dir_path.iterdir()):
                return CheckResult(
                    name="CI/CD pipeline",
                    status=CheckStatus.PASS,
                    message=f"CI/CD directory found: {ci_dir}/",
                )

        # Check known CI/CD root files
        for ci_file in _CI_ROOT_FILES:
            if (self.repo_path / ci_file).exists():
                return CheckResult(
                    name="CI/CD pipeline",
                    status=CheckStatus.PASS,
                    message=f"CI/CD configuration found: {ci_file}",
                )

        # Generic: any root YAML/YML with 'pipeline', 'ci', 'cd', or 'build' in name
        ci_name_pattern = re.compile(r"(?i)(pipeline|ci[^a-z]|cd[^a-z]|build|deploy)")
        for item in self.repo_path.iterdir():
            if item.is_file() and item.suffix.lower() in (".yml", ".yaml"):
                if ci_name_pattern.search(item.stem):
                    return CheckResult(
                        name="CI/CD pipeline",
                        status=CheckStatus.PASS,
                        message=f"CI/CD configuration found: {item.name}",
                    )

        # Check build/ directory for pipeline configs
        build_dir = self.repo_path / "build"
        if build_dir.is_dir():
            for item in build_dir.rglob("*"):
                if item.is_file() and item.suffix.lower() in (".yml", ".yaml"):
                    return CheckResult(
                        name="CI/CD pipeline",
                        status=CheckStatus.PASS,
                        message=f"Build pipeline config found: build/{item.relative_to(build_dir)}",
                    )

        return CheckResult(
            name="CI/CD pipeline",
            status=CheckStatus.FAIL,
            message="No CI/CD pipeline configuration found.",
            recommendation=(
                "Add a CI/CD pipeline (e.g. .github/workflows/ci.yml, azure-pipelines.yml, "
                ".gitlab-ci.yml) to automate testing and deployment."
            ),
        )

    # ------------------------------------------------------------------
    # 4. Coverage — scan for coverage keywords in configs
    # ------------------------------------------------------------------

    def _check_coverage_config(self) -> CheckResult:
        # Generic: any root-level file with "coverage" in the name
        for item in self.repo_path.iterdir():
            if item.is_file() and "coverage" in item.name.lower():
                return CheckResult(
                    name="Coverage config",
                    status=CheckStatus.PASS,
                    message=f"Coverage configuration found: {item.name}",
                )

        # Check known coverage config files
        coverage_files = [
            ".coveragerc", "codecov.yml", ".codecov.yml",
            ".nycrc", ".nycrc.json", ".istanbul.yml",
            "jest.coverage.config.js", "lcov.info",
        ]
        for f in coverage_files:
            if (self.repo_path / f).exists():
                return CheckResult(
                    name="Coverage config",
                    status=CheckStatus.PASS,
                    message=f"Coverage configuration ({f}) found.",
                )

        # Scan project manifests for coverage keywords
        coverage_keywords = re.compile(
            r"(?i)(coverlet|coverage|codecov|coveralls|lcov|nyc|istanbul|jacoco|cobertura|"
            r"simplecov|collect.coverage|code.coverage|ReportGenerator)"
        )
        for item in self.repo_path.iterdir():
            if item.is_file() and item.suffix.lower() in (".toml", ".json", ".cfg", ".ini", ".xml", ".yml", ".yaml"):
                content = self.read_file_safe(item, max_bytes=10_000) or ""
                if coverage_keywords.search(content):
                    return CheckResult(
                        name="Coverage config",
                        status=CheckStatus.PASS,
                        message=f"Coverage configuration reference found in {item.name}.",
                    )

        return CheckResult(
            name="Coverage config",
            status=CheckStatus.FAIL,
            message="No code coverage configuration found.",
            recommendation=(
                "Add coverage tooling for your stack and configure it to report results. "
                "This helps track test effectiveness."
            ),
        )

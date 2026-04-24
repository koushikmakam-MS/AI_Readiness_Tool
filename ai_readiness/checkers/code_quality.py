"""Checker for code quality tooling and structure.

Uses generic detection strategies:
  - Linter/formatter: scan for any root config file with lint/format keywords
  - Type checking: scan for type config files or typed markers
  - File sizes: scan source files with a generous extension set + line-count cap
"""
from __future__ import annotations

import re
from pathlib import Path

from ai_readiness.checkers.base import BaseChecker
from ai_readiness.core.models import CheckResult, CheckStatus

_SKIP_DIRS = frozenset({
    "node_modules", ".git", "vendor", "dist", "build", "__pycache__",
    ".tox", ".mypy_cache", ".pytest_cache", "venv", ".venv", "env",
    ".env", "site-packages", "egg-info", "obj", "bin", "out",
    ".vs", ".vscode", "packages", "target", "TestResults", ".next",
})

# Broad set — covers most programming languages
_SOURCE_EXTENSIONS = frozenset({
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rb",
    ".rs", ".cs", ".cpp", ".c", ".h", ".hpp", ".swift", ".kt",
    ".scala", ".php", ".vue", ".svelte", ".ps1", ".psm1",
    ".ex", ".exs", ".erl", ".hs", ".clj", ".lua", ".r",
    ".dart", ".m", ".mm", ".pl", ".pm", ".sh", ".bash",
    ".groovy", ".vb", ".fs", ".fsx",
})


class CodeQualityChecker(BaseChecker):
    """Assess code quality tooling, formatting, and structural health — language agnostic."""

    dimension_id: str = "code_quality"
    dimension_name: str = "Code Quality & Structure"
    default_weight: float = 15.0

    def run_checks(self) -> list[CheckResult]:
        return [
            self._check_linter(),
            self._check_formatter(),
            self._check_type_checking(),
            self._check_editorconfig(),
            self._check_file_sizes(),
        ]

    # ------------------------------------------------------------------

    def _check_linter(self) -> CheckResult:
        # Generic: any root-level file whose name contains lint-related keywords
        lint_pattern = re.compile(
            r"(?i)(eslint|flake8|pylint|rubocop|swiftlint|golangci|stylelint|"
            r"biome|oxlint|deno.*lint|clippy|checkstyle|pmd|spotbugs|"
            r"lint|analyse|analyze|stylecop|fxcop|sonar)"
        )
        config_exts = {
            ".json", ".yml", ".yaml", ".xml", ".toml", ".ini", ".cfg",
            ".js", ".ts", ".mjs", ".cjs", ".rc",
        }

        for item in self.repo_path.iterdir():
            if item.is_file():
                name_lower = item.name.lower()
                # Check by filename
                if lint_pattern.search(name_lower):
                    return CheckResult(
                        name="Linter configured",
                        status=CheckStatus.PASS,
                        message=f"Linter configuration found: {item.name}",
                    )
                # Check dotfiles that are linter configs (e.g., .flake8, .pylintrc)
                if name_lower.startswith(".") and item.suffix.lower() in config_exts:
                    if lint_pattern.search(name_lower):
                        return CheckResult(
                            name="Linter configured",
                            status=CheckStatus.PASS,
                            message=f"Linter configuration found: {item.name}",
                        )

        # Check inside project manifests for linter config sections
        lint_in_manifest = re.compile(
            r"(?i)(\[tool\.(ruff|flake8|pylint|mypy)\]|"
            r'"(eslint|lint|prettier)".*:|'
            r"<(CodeAnalysis|FxCop|StyleCop))"
        )
        for name in ("pyproject.toml", "package.json", "Cargo.toml", "composer.json"):
            path = self.repo_path / name
            if path.is_file():
                content = self.read_file_safe(path, max_bytes=10_000) or ""
                if lint_in_manifest.search(content):
                    return CheckResult(
                        name="Linter configured",
                        status=CheckStatus.PASS,
                        message=f"Linter configuration found in {name}.",
                    )

        # Check solution/project props for analyzers
        for pattern in ("Directory.Build.props", "*.props"):
            for props in self.repo_path.glob(pattern):
                content = self.read_file_safe(props, max_bytes=10_000) or ""
                if re.search(r"(?i)(Analyzer|CodeAnalysis|StyleCop|FxCop)", content):
                    return CheckResult(
                        name="Linter configured",
                        status=CheckStatus.PASS,
                        message=f"Code analysis configured in {props.name}.",
                    )

        return CheckResult(
            name="Linter configured",
            status=CheckStatus.FAIL,
            message="No linter configuration found.",
            recommendation=(
                "Add a linter appropriate for your stack to enforce consistent code standards. "
                "This helps AI agents produce code that matches your style."
            ),
        )

    def _check_formatter(self) -> CheckResult:
        # Generic: any root-level file related to formatting
        format_pattern = re.compile(
            r"(?i)(prettier|black|autopep8|yapf|rustfmt|gofmt|clang.format|"
            r"scalafmt|ktlint|swift.format|dart.format|format|indent)"
        )

        for item in self.repo_path.iterdir():
            if item.is_file() and format_pattern.search(item.name.lower()):
                return CheckResult(
                    name="Formatter configured",
                    status=CheckStatus.PASS,
                    message=f"Formatter configuration found: {item.name}",
                )

        # .editorconfig counts as a formatter
        if (self.repo_path / ".editorconfig").exists():
            return CheckResult(
                name="Formatter configured",
                status=CheckStatus.PASS,
                message="Formatter configuration found: .editorconfig",
            )

        # Check manifests
        for name in ("pyproject.toml",):
            path = self.repo_path / name
            if path.is_file():
                content = self.read_file_safe(path, max_bytes=10_000) or ""
                if re.search(r"(?i)\[tool\.(black|ruff\.format|yapf|autopep8)\]", content):
                    return CheckResult(
                        name="Formatter configured",
                        status=CheckStatus.PASS,
                        message=f"Formatter configuration found in {name}.",
                    )

        return CheckResult(
            name="Formatter configured",
            status=CheckStatus.FAIL,
            message="No code formatter configuration found.",
            recommendation=(
                "Add a formatter config (e.g. .editorconfig, .prettierrc, or tool-specific settings). "
                "Consistent formatting helps AI agents produce matching code."
            ),
        )

    def _check_type_checking(self) -> CheckResult:
        # Generic: look for type-checking config files
        type_pattern = re.compile(
            r"(?i)(tsconfig|mypy|pyright|pyrightconfig|type.check|"
            r"flow.config|\.flowconfig|strict.*type)"
        )

        for item in self.repo_path.iterdir():
            if item.is_file() and type_pattern.search(item.name.lower()):
                return CheckResult(
                    name="Type checking enabled",
                    status=CheckStatus.PASS,
                    message=f"Type checking configuration found: {item.name}",
                )

        # Strongly typed languages (compiler IS the type checker)
        strong_typed_manifests = {
            "*.sln": "C#/.NET",
            "*.csproj": "C#/.NET",
            "*.fsproj": "F#/.NET",
            "Cargo.toml": "Rust",
            "go.mod": "Go",
            "Package.swift": "Swift",
            "pom.xml": "Java",
            "build.gradle": "Java/Kotlin",
            "build.gradle.kts": "Kotlin",
        }
        for pattern, lang in strong_typed_manifests.items():
            matches = list(self.repo_path.glob(pattern))
            if matches:
                return CheckResult(
                    name="Type checking enabled",
                    status=CheckStatus.PASS,
                    message=f"Compiled/type-safe language detected ({lang}) — compiler enforces types.",
                )

        # Check pyproject.toml for mypy/pyright
        pyproject = self.repo_path / "pyproject.toml"
        if pyproject.is_file():
            content = self.read_file_safe(pyproject) or ""
            if re.search(r"(?i)\[tool\.(mypy|pyright|pytype)\]", content):
                return CheckResult(
                    name="Type checking enabled",
                    status=CheckStatus.PASS,
                    message="Type checking configured in pyproject.toml.",
                )

        return CheckResult(
            name="Type checking enabled",
            status=CheckStatus.FAIL,
            message="No type checking configuration found.",
            recommendation=(
                "Add type checking for your stack (e.g. tsconfig.json, mypy, pyright). "
                "Type information significantly helps AI agents understand your code."
            ),
        )

    def _check_editorconfig(self) -> CheckResult:
        if (self.repo_path / ".editorconfig").exists():
            return CheckResult(
                name=".editorconfig",
                status=CheckStatus.PASS,
                message=".editorconfig found.",
            )
        return CheckResult(
            name=".editorconfig",
            status=CheckStatus.FAIL,
            message="No .editorconfig file found.",
            recommendation="Add an .editorconfig to enforce consistent indentation and line endings across editors.",
        )

    def _check_file_sizes(self) -> CheckResult:
        """Sample up to 500 source files and check for oversized ones."""
        total = 0
        large = 0
        max_sample = 500

        for f in self.repo_path.rglob("*"):
            if not f.is_file():
                continue
            # Skip non-source and vendor dirs
            try:
                rel_parts = f.relative_to(self.repo_path).parts
            except ValueError:
                continue
            if _SKIP_DIRS & set(rel_parts):
                continue
            if f.suffix.lower() not in _SOURCE_EXTENSIONS:
                continue

            total += 1
            try:
                line_count = sum(1 for _ in f.open(encoding="utf-8", errors="replace"))
            except OSError:
                continue
            if line_count > 500:
                large += 1

            if total >= max_sample:
                break

        if total == 0:
            return CheckResult(
                name="Reasonable file sizes",
                status=CheckStatus.SKIP,
                message="No source files found to analyse.",
            )

        ratio = large / total
        sampled_note = f" (sampled {total} files)" if total >= max_sample else f" ({total} files)"
        if ratio > 0.20:
            return CheckResult(
                name="Reasonable file sizes",
                status=CheckStatus.WARN,
                message=f"{large}/{total} source files ({ratio:.0%}) exceed 500 lines{sampled_note}.",
                recommendation="Consider splitting large files into smaller, focused modules for better maintainability.",
            )
        return CheckResult(
            name="Reasonable file sizes",
            status=CheckStatus.PASS,
            message=f"File sizes are reasonable ({large}/{total} over 500 lines){sampled_note}.",
        )

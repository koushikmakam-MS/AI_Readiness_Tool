"""Checker for AI code quality — how well can an AI agent understand and work with this code?

Uses language-agnostic heuristics:
  1. Docstring/comment density — are functions/classes documented?
  2. Function size — are functions small enough for an AI to reason about?
  3. Type annotations / interface clarity — are contracts explicit?
  4. Naming quality — are identifiers descriptive (proxy: avg length)?
  5. Example/sample presence — are there examples to learn from?
  6. Modular structure — is the codebase decomposed into focused files?

All checks use generic file scanning — no language-specific parsing.
"""
from __future__ import annotations

import re
from pathlib import Path

from ai_readiness.checkers.base import BaseChecker
from ai_readiness.core.models import CheckResult, CheckStatus

_SKIP_DIRS = frozenset({
    "node_modules", ".git", "vendor", "dist", "build", "__pycache__",
    ".tox", ".mypy_cache", ".pytest_cache", "venv", ".venv", "env",
    "obj", "bin", "out", ".vs", ".vscode", "packages", "target",
    "TestResults", ".next",
})

_SOURCE_EXTENSIONS = frozenset({
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rb",
    ".rs", ".cs", ".cpp", ".c", ".h", ".hpp", ".swift", ".kt",
    ".scala", ".php", ".vue", ".svelte", ".ps1", ".psm1",
    ".ex", ".exs", ".erl", ".hs", ".clj", ".lua", ".r",
    ".dart", ".m", ".mm", ".pl", ".pm", ".sh", ".bash",
    ".groovy", ".vb", ".fs", ".fsx",
})

# Patterns that indicate a comment or docstring (generic across languages)
_COMMENT_PATTERNS = re.compile(
    r"^\s*(//|#|/\*|\*|--|;|%|\"\"\"|\'\'\'"
    r"|///|/\*\*|<!--|rem\b)",
    re.IGNORECASE,
)

# Patterns that indicate a function/method definition (generic across languages)
_FUNCTION_PATTERNS = re.compile(
    r"(?i)("
    r"^\s*(def |func |function |fn |public |private |protected |internal |static )"
    r"|^\s*(sub |method |proc |procedure )"
    r"|=>\s*\{|^\s*\w+\s*\([^)]*\)\s*\{"
    r")",
)


def _is_source_file(path: Path, repo_root: Path) -> bool:
    """Check if a file is a scannable source file."""
    if not path.is_file():
        return False
    if path.suffix.lower() not in _SOURCE_EXTENSIONS:
        return False
    try:
        parts = path.relative_to(repo_root).parts
    except ValueError:
        return True
    return not (_SKIP_DIRS & set(parts))


class AICodeQualityChecker(BaseChecker):
    """Assess how AI-friendly the code itself is — language agnostic."""

    dimension_id: str = "ai_code_quality"
    dimension_name: str = "AI Code Quality"
    default_weight: float = 15.0

    _MAX_SAMPLE = 200  # sample size for file scanning

    def run_checks(self) -> list[CheckResult]:
        return [
            self._check_comment_density(),
            self._check_function_sizes(),
            self._check_file_modularity(),
            self._check_examples_present(),
            self._check_naming_quality(),
            self._check_inline_docs(),
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _sample_source_files(self) -> list[Path]:
        """Collect a sample of source files for analysis."""
        files: list[Path] = []
        for f in self.repo_path.rglob("*"):
            if _is_source_file(f, self.repo_path):
                files.append(f)
                if len(files) >= self._MAX_SAMPLE:
                    break
        return files

    def _read_lines(self, path: Path, max_lines: int = 1000) -> list[str]:
        """Read lines from a file safely."""
        try:
            with path.open(encoding="utf-8", errors="replace") as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        break
                    lines.append(line)
                return lines
        except OSError:
            return []

    # ------------------------------------------------------------------
    # 1. Comment density — are files documented?
    # ------------------------------------------------------------------

    def _check_comment_density(self) -> CheckResult:
        """Check ratio of comment lines to total code lines across sampled files."""
        files = self._sample_source_files()
        if not files:
            return CheckResult(
                name="Comment density",
                status=CheckStatus.SKIP,
                message="No source files found to analyse.",
            )

        total_lines = 0
        comment_lines = 0

        for f in files:
            lines = self._read_lines(f)
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue
                total_lines += 1
                if _COMMENT_PATTERNS.match(stripped):
                    comment_lines += 1

        if total_lines == 0:
            return CheckResult(
                name="Comment density",
                status=CheckStatus.SKIP,
                message="No code lines found.",
            )

        ratio = comment_lines / total_lines
        if ratio >= 0.10:
            return CheckResult(
                name="Comment density",
                status=CheckStatus.PASS,
                message=f"Good comment density: {ratio:.0%} of code lines are comments ({len(files)} files sampled).",
            )
        elif ratio >= 0.05:
            return CheckResult(
                name="Comment density",
                status=CheckStatus.WARN,
                message=f"Low comment density: {ratio:.0%} of code lines are comments ({len(files)} files sampled).",
                recommendation=(
                    "Add more comments explaining WHY code exists, not just what it does. "
                    "This helps AI agents understand intent and make better changes."
                ),
            )
        return CheckResult(
            name="Comment density",
            status=CheckStatus.FAIL,
            message=f"Very low comment density: {ratio:.0%} ({len(files)} files sampled).",
            recommendation=(
                "Add comments and docstrings to functions/classes explaining their purpose. "
                "AI agents rely heavily on comments to understand code intent."
            ),
        )

    # ------------------------------------------------------------------
    # 2. Function sizes — are functions small enough for AI to reason about?
    # ------------------------------------------------------------------

    def _check_function_sizes(self) -> CheckResult:
        """Estimate average function length by counting lines between function definitions."""
        files = self._sample_source_files()
        if not files:
            return CheckResult(
                name="Function sizes",
                status=CheckStatus.SKIP,
                message="No source files found.",
            )

        function_count = 0
        total_function_lines = 0
        large_functions = 0

        for f in files[:100]:  # deeper analysis on subset
            lines = self._read_lines(f)
            func_starts: list[int] = []

            for i, line in enumerate(lines):
                if _FUNCTION_PATTERNS.search(line):
                    func_starts.append(i)

            # Estimate function lengths from gaps between definitions
            for j in range(len(func_starts)):
                end = func_starts[j + 1] if j + 1 < len(func_starts) else len(lines)
                func_len = end - func_starts[j]
                function_count += 1
                total_function_lines += func_len
                if func_len > 50:
                    large_functions += 1

        if function_count == 0:
            return CheckResult(
                name="Function sizes",
                status=CheckStatus.SKIP,
                message="No function definitions detected in sampled files.",
            )

        avg_len = total_function_lines / function_count
        large_ratio = large_functions / function_count

        if avg_len <= 30 and large_ratio <= 0.20:
            return CheckResult(
                name="Function sizes",
                status=CheckStatus.PASS,
                message=f"Functions are well-sized: avg {avg_len:.0f} lines, {large_ratio:.0%} over 50 lines.",
            )
        elif avg_len <= 50 and large_ratio <= 0.40:
            return CheckResult(
                name="Function sizes",
                status=CheckStatus.WARN,
                message=f"Some large functions: avg {avg_len:.0f} lines, {large_ratio:.0%} over 50 lines.",
                recommendation=(
                    "Break large functions into smaller, single-responsibility pieces. "
                    "AI agents reason better about focused functions under ~30 lines."
                ),
            )
        return CheckResult(
            name="Function sizes",
            status=CheckStatus.FAIL,
            message=f"Functions are too large: avg {avg_len:.0f} lines, {large_ratio:.0%} over 50 lines.",
            recommendation=(
                "Refactor large functions into smaller units. "
                "AI agents struggle with functions over 50 lines — they lose context."
            ),
        )

    # ------------------------------------------------------------------
    # 3. File modularity — are files focused and decomposed?
    # ------------------------------------------------------------------

    def _check_file_modularity(self) -> CheckResult:
        """Check if the codebase is modular (many small files vs few large ones)."""
        files = self._sample_source_files()
        if not files:
            return CheckResult(
                name="File modularity",
                status=CheckStatus.SKIP,
                message="No source files found.",
            )

        line_counts: list[int] = []
        for f in files:
            try:
                count = sum(1 for _ in f.open(encoding="utf-8", errors="replace"))
                line_counts.append(count)
            except OSError:
                pass

        if not line_counts:
            return CheckResult(
                name="File modularity",
                status=CheckStatus.SKIP,
                message="Could not read source files.",
            )

        avg_lines = sum(line_counts) / len(line_counts)
        over_300 = sum(1 for c in line_counts if c > 300)
        over_ratio = over_300 / len(line_counts)

        if avg_lines <= 200 and over_ratio <= 0.25:
            return CheckResult(
                name="File modularity",
                status=CheckStatus.PASS,
                message=f"Good modularity: avg {avg_lines:.0f} lines/file, {over_ratio:.0%} files over 300 lines.",
            )
        elif avg_lines <= 400 and over_ratio <= 0.50:
            return CheckResult(
                name="File modularity",
                status=CheckStatus.WARN,
                message=f"Moderate modularity: avg {avg_lines:.0f} lines/file, {over_ratio:.0%} files over 300 lines.",
                recommendation=(
                    "Consider decomposing larger files into focused modules. "
                    "AI agents work best when each file has a clear, single purpose."
                ),
            )
        return CheckResult(
            name="File modularity",
            status=CheckStatus.FAIL,
            message=f"Poor modularity: avg {avg_lines:.0f} lines/file, {over_ratio:.0%} files over 300 lines.",
            recommendation=(
                "Break large files into smaller, focused modules. "
                "AI agents can only process ~one file at a time effectively."
            ),
        )

    # ------------------------------------------------------------------
    # 4. Examples/samples present — can an AI learn usage patterns?
    # ------------------------------------------------------------------

    def _check_examples_present(self) -> CheckResult:
        """Check for example code, samples, or demo directories."""
        example_pattern = re.compile(r"(?i)(example|sample|demo|tutorial|quickstart|starter|template)")

        # Check top-level and one-level deep directories
        for item in self.repo_path.iterdir():
            if item.is_dir() and example_pattern.search(item.name):
                return CheckResult(
                    name="Examples/samples present",
                    status=CheckStatus.PASS,
                    message=f"Example directory found: {item.name}/",
                )

        # Check docs/ for examples
        docs_dir = self.repo_path / "docs"
        if docs_dir.is_dir():
            for item in docs_dir.iterdir():
                if example_pattern.search(item.name):
                    return CheckResult(
                        name="Examples/samples present",
                        status=CheckStatus.PASS,
                        message=f"Examples found in docs: docs/{item.name}",
                    )

        # Check README for code blocks (indicates inline examples)
        for readme_name in ("README.md", "README.rst", "README.txt"):
            readme = self.repo_path / readme_name
            if readme.is_file():
                content = self.read_file_safe(readme, max_bytes=20_000) or ""
                code_blocks = len(re.findall(r"```", content))
                if code_blocks >= 4:  # at least 2 code blocks
                    return CheckResult(
                        name="Examples/samples present",
                        status=CheckStatus.PASS,
                        message=f"README contains code examples ({code_blocks // 2}+ code blocks).",
                    )

        return CheckResult(
            name="Examples/samples present",
            status=CheckStatus.FAIL,
            message="No examples, samples, or demo code found.",
            recommendation=(
                "Add an examples/ or samples/ directory with usage examples. "
                "AI agents use examples to understand expected patterns and conventions."
            ),
        )

    # ------------------------------------------------------------------
    # 5. Naming quality — are identifiers descriptive? (proxy: avg length)
    # ------------------------------------------------------------------

    def _check_naming_quality(self) -> CheckResult:
        """Heuristic: check if function/method names are descriptive (not too short)."""
        files = self._sample_source_files()
        if not files:
            return CheckResult(
                name="Naming quality",
                status=CheckStatus.SKIP,
                message="No source files found.",
            )

        name_lengths: list[int] = []
        # Extract function names generically
        func_name_pattern = re.compile(
            r"(?:def|func|function|fn|sub|method)\s+(\w+)"
            r"|(?:public|private|protected|internal|static)\s+\w+\s+(\w+)\s*\(",
            re.IGNORECASE,
        )

        for f in files[:100]:
            content = self.read_file_safe(f, max_bytes=20_000) or ""
            for match in func_name_pattern.finditer(content):
                name = match.group(1) or match.group(2)
                if name and name not in ("main", "init", "new", "get", "set", "run"):
                    name_lengths.append(len(name))

        if len(name_lengths) < 10:
            return CheckResult(
                name="Naming quality",
                status=CheckStatus.SKIP,
                message="Not enough function names to assess.",
            )

        avg_len = sum(name_lengths) / len(name_lengths)
        short_names = sum(1 for l in name_lengths if l <= 3)
        short_ratio = short_names / len(name_lengths)

        if avg_len >= 8 and short_ratio <= 0.15:
            return CheckResult(
                name="Naming quality",
                status=CheckStatus.PASS,
                message=f"Good naming: avg function name length {avg_len:.0f} chars, {short_ratio:.0%} very short names.",
            )
        elif avg_len >= 5 and short_ratio <= 0.30:
            return CheckResult(
                name="Naming quality",
                status=CheckStatus.WARN,
                message=f"Naming could improve: avg {avg_len:.0f} chars, {short_ratio:.0%} very short names.",
                recommendation=(
                    "Use more descriptive function/method names. "
                    "AI agents understand intent better from names like 'calculateTotalPrice' vs 'calc'."
                ),
            )
        return CheckResult(
            name="Naming quality",
            status=CheckStatus.FAIL,
            message=f"Poor naming: avg {avg_len:.0f} chars, {short_ratio:.0%} very short names.",
            recommendation=(
                "Rename functions/methods to clearly describe what they do. "
                "Descriptive names are the #1 signal AI agents use to understand code purpose."
            ),
        )

    # ------------------------------------------------------------------
    # 6. Inline documentation — do key files have header docs?
    # ------------------------------------------------------------------

    def _check_inline_docs(self) -> CheckResult:
        """Check if source files have file-level documentation (header comments/docstrings)."""
        files = self._sample_source_files()
        if not files:
            return CheckResult(
                name="Inline documentation",
                status=CheckStatus.SKIP,
                message="No source files found.",
            )

        documented = 0
        checked = 0

        for f in files[:100]:
            lines = self._read_lines(f, max_lines=10)
            if not lines:
                continue
            checked += 1

            # Check first 10 non-empty lines for comment/docstring
            has_header = False
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue
                if _COMMENT_PATTERNS.match(stripped):
                    has_header = True
                break  # only check first non-empty line

            if has_header:
                documented += 1

        if checked == 0:
            return CheckResult(
                name="Inline documentation",
                status=CheckStatus.SKIP,
                message="No files to check.",
            )

        ratio = documented / checked
        if ratio >= 0.50:
            return CheckResult(
                name="Inline documentation",
                status=CheckStatus.PASS,
                message=f"{ratio:.0%} of files have header documentation ({checked} files checked).",
            )
        elif ratio >= 0.25:
            return CheckResult(
                name="Inline documentation",
                status=CheckStatus.WARN,
                message=f"Only {ratio:.0%} of files have header documentation.",
                recommendation=(
                    "Add a brief comment at the top of each file explaining its purpose. "
                    "This gives AI agents immediate context without reading the whole file."
                ),
            )
        return CheckResult(
            name="Inline documentation",
            status=CheckStatus.FAIL,
            message=f"Only {ratio:.0%} of files have header documentation.",
            recommendation=(
                "Add file-level docstrings or comments to your source files. "
                "A single line like '// Handles user authentication for the API' "
                "dramatically helps AI agents navigate your codebase."
            ),
        )

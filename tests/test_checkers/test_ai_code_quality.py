"""Tests for ai_readiness.checkers.ai_code_quality.AICodeQualityChecker."""
from __future__ import annotations

import pytest

from ai_readiness.checkers.ai_code_quality import AICodeQualityChecker
from ai_readiness.core.models import CheckStatus
from tests.conftest import create_file


def _well_commented_file(lines: int = 50) -> str:
    """Generate a source file with ~20 % comment density."""
    out = ["# Module header\n"]
    for i in range(lines):
        if i % 4 == 0:
            out.append(f"# comment line {i}\n")
        else:
            out.append(f"x = {i}\n")
    return "".join(out)


def _uncommented_file(lines: int = 50) -> str:
    return "".join(f"x = {i}\n" for i in range(lines))


def _small_functions_file() -> str:
    """Generate a file with many small functions (< 30 lines each)."""
    funcs = []
    for i in range(10):
        body = "\n".join(f"    x = {j}" for j in range(5))
        funcs.append(f"def function_{i}_handler():\n{body}\n\n")
    return "".join(funcs)


class TestAICodeQualityChecker:
    def _run(self, tmp_path, languages=None):
        checker = AICodeQualityChecker(repo_path=tmp_path, languages=languages)
        return {c.name: c for c in checker.run_checks()}

    # ── Comment density ──────────────────────────────────────────────

    def test_no_source_files_skip(self, tmp_path):
        results = self._run(tmp_path)
        assert results["Comment density"].status is CheckStatus.SKIP

    def test_well_commented_passes(self, tmp_path):
        for i in range(5):
            create_file(tmp_path, f"src/mod_{i}.py", _well_commented_file(80))
        results = self._run(tmp_path)
        assert results["Comment density"].status is CheckStatus.PASS

    def test_no_comments_fails(self, tmp_path):
        for i in range(5):
            create_file(tmp_path, f"src/mod_{i}.py", _uncommented_file(80))
        results = self._run(tmp_path)
        assert results["Comment density"].status is CheckStatus.FAIL

    # ── Function sizes ───────────────────────────────────────────────

    def test_small_functions_passes(self, tmp_path):
        create_file(tmp_path, "src/app.py", _small_functions_file())
        results = self._run(tmp_path)
        assert results["Function sizes"].status is CheckStatus.PASS

    def test_no_functions_skip(self, tmp_path):
        create_file(tmp_path, "src/data.py", "x = 1\ny = 2\n")
        results = self._run(tmp_path)
        assert results["Function sizes"].status is CheckStatus.SKIP

    # ── Examples present ─────────────────────────────────────────────

    def test_examples_dir_passes(self, tmp_path):
        create_file(tmp_path, "examples/demo.py", "print('hi')")
        create_file(tmp_path, "src/main.py", "pass")
        results = self._run(tmp_path)
        assert results["Examples/samples present"].status is CheckStatus.PASS

    def test_samples_dir_passes(self, tmp_path):
        create_file(tmp_path, "samples/basic.js", "console.log('hi')")
        create_file(tmp_path, "src/main.py", "pass")
        results = self._run(tmp_path)
        assert results["Examples/samples present"].status is CheckStatus.PASS

    def test_no_examples_fails(self, tmp_path):
        create_file(tmp_path, "src/main.py", "pass")
        results = self._run(tmp_path)
        assert results["Examples/samples present"].status is CheckStatus.FAIL

    def test_readme_code_blocks_passes(self, tmp_path):
        readme = "# Proj\n```python\nprint('a')\n```\n\n```python\nprint('b')\n```\n"
        create_file(tmp_path, "README.md", readme)
        create_file(tmp_path, "src/main.py", "pass")
        results = self._run(tmp_path)
        assert results["Examples/samples present"].status is CheckStatus.PASS

    # ── File modularity ──────────────────────────────────────────────

    def test_small_files_pass(self, tmp_path):
        for i in range(10):
            create_file(tmp_path, f"src/mod_{i}.py", "x = 1\n" * 50)
        results = self._run(tmp_path)
        assert results["File modularity"].status is CheckStatus.PASS

    # ── Inline documentation ─────────────────────────────────────────

    def test_files_with_headers_pass(self, tmp_path):
        for i in range(10):
            create_file(tmp_path, f"src/mod_{i}.py", f"# Module {i}\nx = 1\n")
        results = self._run(tmp_path)
        assert results["Inline documentation"].status is CheckStatus.PASS

    def test_files_without_headers_fail(self, tmp_path):
        for i in range(10):
            create_file(tmp_path, f"src/mod_{i}.py", "x = 1\ny = 2\n")
        results = self._run(tmp_path)
        assert results["Inline documentation"].status is CheckStatus.FAIL

    # ── evaluate() ───────────────────────────────────────────────────

    def test_evaluate_empty_repo(self, tmp_path):
        checker = AICodeQualityChecker(repo_path=tmp_path)
        ds = checker.evaluate()
        assert ds.dimension_id == "ai_code_quality"
        assert 0.0 <= ds.score <= 10.0

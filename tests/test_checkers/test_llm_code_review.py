"""Tests for ai_readiness.checkers.llm_code_review.LLMCodeReviewChecker."""
from __future__ import annotations

import json

import pytest
from unittest.mock import patch, MagicMock

from ai_readiness.checkers.llm_code_review import (
    LLMCodeReviewChecker,
    SKIP_DIRS,
    SOURCE_EXTENSIONS,
    ENTRY_POINT_NAMES,
)
from ai_readiness.core.models import CheckStatus
from tests.conftest import create_file


MOCK_LLM_RESPONSE = json.dumps({
    "dimensions": {
        "readability": {"score": 7, "rationale": "Good naming conventions."},
        "error_handling": {"score": 5, "rationale": "Basic try/catch."},
        "architecture": {"score": 6, "rationale": "Decent separation."},
        "code_smells": {"score": 8, "rationale": "Clean code."},
        "ai_friendliness": {"score": 7, "rationale": "Predictable patterns."},
        "maintainability": {"score": 6, "rationale": "Modular design."},
    },
    "files_reviewed_summary": "Code is generally clean.",
})


def _make_checker(tmp_path, **kwargs):
    return LLMCodeReviewChecker(repo_path=tmp_path, languages=["python"], **kwargs)


# ── File selection ───────────────────────────────────────────────────

def test_skips_test_directories(tmp_path):
    create_file(tmp_path, "tests/test_foo.py", "def test(): pass")
    create_file(tmp_path, "src/app.py", "print('hello')")
    checker = _make_checker(tmp_path)
    samples = checker._select_files()
    paths = [p for p, _ in samples]
    assert not any("tests" in p for p in paths)
    assert any("app.py" in p for p in paths)


def test_skips_vendor_and_node_modules(tmp_path):
    create_file(tmp_path, "vendor/lib.py", "x = 1")
    create_file(tmp_path, "node_modules/pkg/index.js", "module.exports = {}")
    create_file(tmp_path, "src/main.py", "print('hello')")
    checker = _make_checker(tmp_path)
    samples = checker._select_files()
    paths = [p for p, _ in samples]
    assert not any("vendor" in p for p in paths)
    assert not any("node_modules" in p for p in paths)


def test_samples_from_multiple_directories(tmp_path):
    create_file(tmp_path, "src/core/engine.py", "class Engine: pass")
    create_file(tmp_path, "src/utils/helpers.py", "def helper(): pass")
    create_file(tmp_path, "lib/parser.py", "def parse(): pass")
    checker = _make_checker(tmp_path)
    samples = checker._select_files()
    dirs = {p.split("/")[0] if "/" in p else p.split("\\")[0] for p, _ in samples}
    assert len(dirs) >= 2


def test_prioritizes_entry_points(tmp_path):
    create_file(tmp_path, "main.py", "if __name__ == '__main__': pass")
    create_file(tmp_path, "src/utils.py", "def util(): pass")
    create_file(tmp_path, "src/other.py", "x = 1")
    checker = _make_checker(tmp_path)
    samples = checker._select_files()
    paths = [p for p, _ in samples]
    # main.py should appear (it's an entry point)
    assert any("main.py" in p for p in paths)


# ── _read_smart ──────────────────────────────────────────────────────

def test_read_smart_small_file(tmp_path):
    content = "\n".join(f"line {i}" for i in range(50))
    f = tmp_path / "small.py"
    f.write_text(content, encoding="utf-8")
    checker = _make_checker(tmp_path)
    result = checker._read_smart(f, max_lines=300)
    assert result == content


def test_read_smart_large_file_samples(tmp_path):
    content = "\n".join(f"line {i}" for i in range(1000))
    f = tmp_path / "big.py"
    f.write_text(content, encoding="utf-8")
    checker = _make_checker(tmp_path)
    result = checker._read_smart(f, max_lines=300)
    assert "lines omitted" in result
    # Should contain top lines
    assert "line 0" in result
    # Should contain bottom lines
    assert "line 999" in result


# ── _parse_review ────────────────────────────────────────────────────

def test_parse_review_valid_json(tmp_path):
    checker = _make_checker(tmp_path)
    checker._files_sent = ["src/app.py"]
    results = checker._parse_review(MOCK_LLM_RESPONSE)
    names = {r.name for r in results}
    assert "Code Readability & Clarity" in names
    assert "Error Handling & Robustness" in names
    assert "Review Summary" in names
    # Check raw_score is set
    readability = next(r for r in results if r.name == "Code Readability & Clarity")
    assert readability.raw_score == 7.0


def test_parse_review_malformed_json(tmp_path):
    checker = _make_checker(tmp_path)
    results = checker._parse_review("this is not json at all {{{")
    assert len(results) == 1
    assert results[0].status is CheckStatus.WARN
    assert results[0].raw_score == 5.0


# ── _build_review_prompt ─────────────────────────────────────────────

def test_build_review_prompt_includes_structure_and_files(tmp_path):
    create_file(tmp_path, "src/app.py", "print('hello')")
    checker = _make_checker(tmp_path)
    samples = [("src/app.py", "print('hello')")]
    prompt = checker._build_review_prompt(samples)
    assert "Repository Structure" in prompt
    assert "src/app.py" in prompt
    assert "print('hello')" in prompt


# ── run_checks integration (mocked LLM) ─────────────────────────────

def test_run_checks_no_source_files_returns_skip(tmp_path):
    # Empty repo → no source files
    checker = _make_checker(tmp_path)
    results = checker.run_checks()
    assert len(results) == 1
    assert results[0].status is CheckStatus.SKIP


def test_run_checks_llm_failure_returns_skip(tmp_path):
    create_file(tmp_path, "src/app.py", "print('hello')")
    checker = _make_checker(tmp_path)
    with patch.object(checker, "_call_llm", side_effect=Exception("API error")):
        results = checker.run_checks()
    assert len(results) == 1
    assert results[0].status is CheckStatus.SKIP
    assert "API error" in results[0].message


def test_run_checks_success_with_mocked_llm(tmp_path):
    create_file(tmp_path, "src/app.py", "print('hello')")
    checker = _make_checker(tmp_path)
    with patch.object(checker, "_call_llm", return_value=MOCK_LLM_RESPONSE):
        results = checker.run_checks()
    # Should have 6 dimension checks + 1 summary = 7
    assert len(results) == 7
    scored = [r for r in results if r.raw_score is not None]
    assert len(scored) == 6

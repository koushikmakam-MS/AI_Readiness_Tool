"""Tests for ai_readiness.core.reporter — JSON and Markdown output."""
from __future__ import annotations

import json

import pytest

from ai_readiness.core.models import CheckResult, CheckStatus, DimensionScore, Report
from ai_readiness.core.reporter import JSONReporter, MarkdownReporter, format_report


def _sample_report() -> Report:
    checks = [
        CheckResult("README exists", CheckStatus.PASS, "Found"),
        CheckResult("Tests exist", CheckStatus.FAIL, "None", recommendation="Add tests"),
        CheckResult("Skipped", CheckStatus.SKIP, "n/a"),
    ]
    dim = DimensionScore(
        dimension_id="doc",
        dimension_name="Documentation",
        score=5.0,
        weight=50.0,
        checks=checks,
    )
    return Report(
        repo_path="/repo",
        dimensions=[dim],
        languages_detected=["Python", "JavaScript"],
    )


class TestJSONReporter:
    def test_valid_json(self):
        report = _sample_report()
        output = JSONReporter.render(report)
        data = json.loads(output)
        assert isinstance(data, dict)

    def test_contains_overall_score(self):
        report = _sample_report()
        data = json.loads(JSONReporter.render(report))
        assert "overall_score" in data
        assert isinstance(data["overall_score"], (int, float))

    def test_contains_dimensions(self):
        report = _sample_report()
        data = json.loads(JSONReporter.render(report))
        assert len(data["dimensions"]) == 1
        assert data["dimensions"][0]["id"] == "doc"

    def test_contains_rating(self):
        report = _sample_report()
        data = json.loads(JSONReporter.render(report))
        assert data["rating"] in ("Poor", "Fair", "Good", "Excellent")

    def test_contains_languages(self):
        report = _sample_report()
        data = json.loads(JSONReporter.render(report))
        assert data["languages"] == ["Python", "JavaScript"]

    def test_contains_recommendations(self):
        report = _sample_report()
        data = json.loads(JSONReporter.render(report))
        assert "Add tests" in data["recommendations"]


class TestMarkdownReporter:
    def test_contains_header(self):
        report = _sample_report()
        md = MarkdownReporter.render(report)
        assert "# " in md
        assert "AI Readiness Report" in md

    def test_contains_overall_score(self):
        report = _sample_report()
        md = MarkdownReporter.render(report)
        assert "Overall Score" in md

    def test_contains_dimension_table(self):
        report = _sample_report()
        md = MarkdownReporter.render(report)
        assert "Dimension Scores" in md
        assert "Documentation" in md

    def test_contains_detailed_findings(self):
        report = _sample_report()
        md = MarkdownReporter.render(report)
        assert "Detailed Findings" in md
        assert "README exists" in md

    def test_contains_recommendations(self):
        report = _sample_report()
        md = MarkdownReporter.render(report)
        assert "Recommendations" in md
        assert "Add tests" in md

    def test_contains_languages(self):
        report = _sample_report()
        md = MarkdownReporter.render(report)
        assert "Python" in md


class TestFormatReport:
    def test_json_format(self):
        report = _sample_report()
        output = format_report(report, format="json")
        data = json.loads(output)
        assert "overall_score" in data

    def test_markdown_format(self):
        report = _sample_report()
        output = format_report(report, format="markdown")
        assert "AI Readiness Report" in output

    def test_terminal_format_returns_empty(self):
        report = _sample_report()
        output = format_report(report, format="terminal")
        assert output == ""

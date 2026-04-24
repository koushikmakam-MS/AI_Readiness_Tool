"""Tests for ai_readiness.core.engine.AssessmentEngine."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from ai_readiness.core.engine import AssessmentEngine
from ai_readiness.core.models import Report
from tests.conftest import create_file


def _minimal_config() -> dict:
    """Config with a single known checker to keep tests fast."""
    return {
        "dimensions": {
            "documentation": {
                "enabled": True,
                "checker": "ai_readiness.checkers.documentation.DocumentationChecker",
                "weight": 20.0,
            },
        },
        "llm": {"enabled": False},
    }


def _multi_checker_config() -> dict:
    return {
        "dimensions": {
            "documentation": {
                "enabled": True,
                "checker": "ai_readiness.checkers.documentation.DocumentationChecker",
                "weight": 20.0,
            },
            "testing": {
                "enabled": True,
                "checker": "ai_readiness.checkers.testing.TestingChecker",
                "weight": 20.0,
            },
            "ai_config": {
                "enabled": True,
                "checker": "ai_readiness.checkers.ai_config.AIConfigChecker",
                "weight": 15.0,
            },
        },
        "llm": {"enabled": False},
    }


class TestAssessmentEngine:
    def test_runs_without_crash_on_empty_repo(self, tmp_path):
        engine = AssessmentEngine(config=_minimal_config(), repo_path=tmp_path, no_llm=True)
        report = engine.run()
        assert isinstance(report, Report)

    def test_produces_report_with_correct_dimensions(self, tmp_path):
        engine = AssessmentEngine(config=_multi_checker_config(), repo_path=tmp_path, no_llm=True)
        report = engine.run()

        dim_ids = {d.dimension_id for d in report.dimensions}
        assert "documentation" in dim_ids
        assert "testing" in dim_ids
        assert "ai_config" in dim_ids

    def test_report_has_languages(self, tmp_path):
        create_file(tmp_path, "app.py", "print('hi')")
        engine = AssessmentEngine(config=_minimal_config(), repo_path=tmp_path, no_llm=True)
        report = engine.run()
        assert "Python" in report.languages_detected

    def test_disabled_dimension_skipped(self, tmp_path):
        config = {
            "dimensions": {
                "documentation": {
                    "enabled": False,
                    "checker": "ai_readiness.checkers.documentation.DocumentationChecker",
                    "weight": 20.0,
                },
            },
            "llm": {"enabled": False},
        }
        engine = AssessmentEngine(config=config, repo_path=tmp_path, no_llm=True)
        report = engine.run()
        assert len(report.dimensions) == 0

    def test_handles_bad_checker_path_gracefully(self, tmp_path):
        config = {
            "dimensions": {
                "bogus": {
                    "enabled": True,
                    "checker": "ai_readiness.checkers.nonexistent.BogusChecker",
                    "weight": 10.0,
                },
            },
            "llm": {"enabled": False},
        }
        engine = AssessmentEngine(config=config, repo_path=tmp_path, no_llm=True)
        report = engine.run()
        # Should not crash; dimension is skipped
        assert len(report.dimensions) == 0

    def test_overall_score_range(self, tmp_path):
        engine = AssessmentEngine(config=_multi_checker_config(), repo_path=tmp_path, no_llm=True)
        report = engine.run()
        assert 0.0 <= report.overall_score <= 100.0

"""Assessment engine — orchestrates checkers and optional LLM analysis."""

from __future__ import annotations

import logging
from pathlib import Path

from rich.console import Console

from ai_readiness.core.category_mapper import build_categories
from ai_readiness.core.config import get_dimension_configs, get_llm_config, load_checker_class
from ai_readiness.core.models import DimensionScore, Report
from ai_readiness.utils.language_detect import detect_languages

logger = logging.getLogger(__name__)
console = Console(stderr=True)

# Dimensions that require LLM — handled specially at engine level
LLM_REQUIRED_DIMENSIONS = {"llm_code_review"}


class AssessmentEngine:
    """Run every enabled dimension checker and produce a Report."""

    def __init__(self, config: dict, repo_path: Path, no_llm: bool = False) -> None:
        self.config = config
        self.repo_path = repo_path
        self.no_llm = no_llm
        self.languages = detect_languages(repo_path)

    # ------------------------------------------------------------------

    def run(self) -> Report:
        """Execute all dimension checks and optional LLM analysis."""
        dimensions: list[DimensionScore] = []
        dim_configs = get_dimension_configs(self.config)
        llm_config = get_llm_config(self.config)
        llm_available = self._is_llm_available(llm_config)

        for dim_id, dim_cfg in dim_configs.items():
            if not dim_cfg.get("enabled", True):
                continue

            # Skip LLM-dependent dimensions entirely when LLM is unavailable
            if dim_id in LLM_REQUIRED_DIMENSIONS and (self.no_llm or not llm_available):
                logger.info("Dimension '%s' skipped — LLM not available.", dim_id)
                continue

            checker_path = dim_cfg.get("checker", "")
            if not checker_path:
                logger.warning("Dimension '%s' has no checker configured — skipping.", dim_id)
                continue

            try:
                console.print(f"  [dim]▸[/dim] Evaluating [bold]{dim_id}[/bold] …")
                checker_cls = load_checker_class(checker_path)

                # Inject extra config for special checkers
                if dim_id in LLM_REQUIRED_DIMENSIONS:
                    checker = checker_cls(
                        repo_path=self.repo_path,
                        languages=self.languages,
                        llm_config=llm_config,
                    )
                elif dim_id == "ai_config":
                    target_agents = (self.config.get("assessment") or {}).get("target_agents")
                    checker = checker_cls(
                        repo_path=self.repo_path,
                        languages=self.languages,
                        target_agents=target_agents,
                    )
                else:
                    checker = checker_cls(repo_path=self.repo_path, languages=self.languages)

                score = checker.evaluate(weight=dim_cfg.get("weight", 10.0))
                dimensions.append(score)
            except Exception:
                logger.warning("Checker for '%s' failed — skipping.", dim_id, exc_info=True)

        report = Report(
            repo_path=str(self.repo_path),
            dimensions=dimensions,
            languages_detected=self.languages,
        )

        # --- Optional LLM enrichment (insights for static dimensions) ---
        if llm_config.get("enabled", False) and not self.no_llm and llm_available:
            try:
                from ai_readiness.llm.analyzer import LLMAnalyzer

                analyzer = LLMAnalyzer(llm_config)
                if analyzer.is_available:
                    console.print("  [dim]▸[/dim] Running LLM analysis …")
                    insights, summary = analyzer.analyze(report, self.repo_path)
                    for dim in report.dimensions:
                        if dim.dimension_id in insights:
                            dim.llm_insights = insights[dim.dimension_id]
                    report.llm_summary = summary
                else:
                    logger.info("LLM analysis skipped — no API key configured.")
            except Exception:
                logger.warning("LLM analysis failed — continuing without it.", exc_info=True)

        # --- Build AI-focused categories from dimension checks ---
        console.print("  [dim]▸[/dim] Building category scores …")
        target_agents = (self.config.get("assessment") or {}).get("target_agents")
        report.categories = build_categories(report, target_agents=target_agents)

        return report

    @staticmethod
    def _is_llm_available(llm_config: dict) -> bool:
        """Check if LLM is configured and available."""
        import os
        if not llm_config.get("enabled", False):
            return False
        api_key = (
            llm_config.get("api_key", "")
            or os.environ.get("AZURE_OPENAI_API_KEY", "")
            or os.environ.get("OPENAI_API_KEY", "")
        )
        return bool(api_key)

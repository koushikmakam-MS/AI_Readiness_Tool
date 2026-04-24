"""LLM-powered deep analysis of assessment results."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from ai_readiness.core.models import Report

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are an expert software-engineering consultant specialising in making \
codebases ready for AI coding agents (e.g. GitHub Copilot, Cursor, Codex).

You will receive:
1. Static analysis results — dimension scores and individual check outcomes.
2. A snapshot of the repository structure and key file contents.

Your tasks:
• For **each dimension** provide a concise insight (2-3 sentences) explaining \
  what the repository does well and what could be improved.
• Provide an **overall summary** (4-6 sentences) with the top 3 actionable \
  recommendations to improve AI readiness.

Return your response as valid JSON with this structure:
{
  "dimension_insights": {
    "<dimension_id>": "<insight text>",
    ...
  },
  "overall_summary": "<summary text>"
}
Return ONLY the JSON object, no markdown fencing or extra text.\
"""


class LLMAnalyzer:
    """Optional LLM enrichment for the assessment report."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.provider: str = config.get("provider", "openai")
        self.model: str = config.get("model", "gpt-4o")

        # Azure OpenAI settings
        self.azure_endpoint: str = config.get("azure_endpoint", "") or os.environ.get("AZURE_OPENAI_ENDPOINT", "")
        self.azure_api_version: str = config.get("azure_api_version", "") or os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
        self.azure_deployment: str = config.get("azure_deployment", "") or self.model

        # API key: config > provider-specific env > generic env
        self.api_key: str = (
            config.get("api_key", "")
            or os.environ.get("AZURE_OPENAI_API_KEY", "")
            or os.environ.get("OPENAI_API_KEY", "")
        )

    @property
    def is_available(self) -> bool:
        if self.provider == "azure":
            return bool(self.api_key and self.azure_endpoint)
        return bool(self.api_key)

    # ------------------------------------------------------------------

    def analyze(self, report: Report, repo_path: Path) -> tuple[dict[str, str], str]:
        """Return ``(dimension_insights, overall_summary)``.

        On any failure the method logs a warning and returns empty results so
        the rest of the tool keeps working.
        """
        try:
            prompt = self._build_prompt(report, repo_path)
            raw = self._call_llm(prompt)
            return self._parse_response(raw)
        except Exception:
            logger.warning("LLM analysis failed.", exc_info=True)
            return {}, ""

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_prompt(self, report: Report, repo_path: Path) -> str:
        sections: list[str] = []

        # 1. Static analysis results
        sections.append("## Static Analysis Results")
        sections.append(f"Overall score: {report.overall_score:.1f}/100 ({report.rating.value})")
        sections.append(f"Languages: {', '.join(report.languages_detected)}")
        sections.append("")
        for dim in report.dimensions:
            sections.append(
                f"- **{dim.dimension_name}** (id={dim.dimension_id}): "
                f"{dim.score:.1f}/10, {dim.passed_checks}/{dim.total_checks} checks passed"
            )
            for check in dim.checks:
                sections.append(f"  - [{check.status.value}] {check.name}: {check.message}")

        # 2. Repo structure (top-level)
        sections.append("")
        sections.append("## Repository Structure (top level)")
        try:
            entries = sorted(repo_path.iterdir())
            for entry in entries[:50]:
                kind = "dir" if entry.is_dir() else "file"
                sections.append(f"  {kind}: {entry.name}")
        except OSError:
            sections.append("  (unable to list directory)")

        # 3. Key file snippets
        sections.append("")
        sections.append("## Key File Contents (truncated)")
        for name in ("README.md", "README.rst", "README", "CONTRIBUTING.md"):
            fpath = repo_path / name
            if fpath.is_file():
                content = self._read_snippet(fpath, max_chars=2000)
                sections.append(f"\n### {name}\n```\n{content}\n```")
                break

        return "\n".join(sections)

    @staticmethod
    def _read_snippet(path: Path, max_chars: int = 2000) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="replace")[:max_chars]
        except OSError:
            return "(unable to read)"

    def _call_llm(self, user_prompt: str) -> str:
        if self.provider == "azure":
            return self._call_azure_openai(user_prompt)
        return self._call_openai(user_prompt)

    def _call_openai(self, user_prompt: str) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )
        return response.choices[0].message.content or ""

    def _call_azure_openai(self, user_prompt: str) -> str:
        from openai import AzureOpenAI

        client = AzureOpenAI(
            api_key=self.api_key,
            azure_endpoint=self.azure_endpoint,
            api_version=self.azure_api_version,
        )
        response = client.chat.completions.create(
            model=self.azure_deployment,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )
        return response.choices[0].message.content or ""

    @staticmethod
    def _parse_response(raw: str) -> tuple[dict[str, str], str]:
        """Extract dimension insights and overall summary from the LLM JSON."""
        # Strip possible markdown code fences
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Could not parse LLM response as JSON.")
            return {}, raw.strip()

        insights: dict[str, str] = data.get("dimension_insights", {})
        summary: str = data.get("overall_summary", "")
        return insights, summary

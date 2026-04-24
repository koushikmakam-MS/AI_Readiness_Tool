"""LLM-powered holistic code quality review.

This checker sends actual code samples to the LLM for deep quality assessment.
Unlike static heuristics, it reads and understands the code to judge readability,
error handling, design patterns, and AI-agent friendliness.
"""

from __future__ import annotations

import json
import logging
import os
import random
from pathlib import Path
from typing import Any, Optional

from ai_readiness.checkers.base import BaseChecker
from ai_readiness.core.models import CheckResult, CheckStatus

logger = logging.getLogger(__name__)

SKIP_DIRS = {
    ".git", "node_modules", "vendor", "dist", "build", "bin", "obj",
    "packages", ".vs", ".idea", "__pycache__", ".tox", "venv", ".venv",
    "target", "out", ".next", ".nuxt", "coverage", "TestResults",
}

SOURCE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".cs", ".java", ".go", ".rs",
    ".rb", ".php", ".cpp", ".c", ".h", ".hpp", ".swift", ".kt", ".kts",
    ".scala", ".r", ".R", ".lua", ".ps1", ".sh", ".bash", ".dart",
    ".vue", ".svelte", ".ex", ".exs", ".clj", ".zig", ".nim",
}

# Files likely to be entry points or important
ENTRY_POINT_NAMES = {
    "program.cs", "startup.cs", "main.py", "app.py", "__main__.py",
    "index.ts", "index.js", "main.go", "main.rs", "main.java",
    "application.java", "app.rb", "server.py", "server.ts", "server.js",
    "index.php", "main.cpp", "main.c", "lib.rs",
}

_REVIEW_SYSTEM_PROMPT = """\
You are a senior software engineer performing a code quality review focused on \
how well this codebase supports AI coding agents (e.g. GitHub Copilot, Cursor, Codex).

You will receive:
1. Repository structure (top-level directories and files)
2. Source code samples from different parts of the codebase

Score each of these 6 quality dimensions on a scale of 1-10:

1. **readability** — Is the code clear? Good variable/function names? Consistent style?
2. **error_handling** — Are errors handled properly? Edge cases covered? Defensive coding?
3. **architecture** — Good separation of concerns? Appropriate abstractions? Low coupling?
4. **code_smells** — Absence of code smells (duplication, god classes, magic numbers, etc). \
   10 = very clean, 1 = heavy smells.
5. **ai_friendliness** — Can an AI agent understand and safely modify this code? \
   Clear boundaries, predictable patterns, good context for LLM understanding?
6. **maintainability** — Can this code be easily extended? Is it modular? Well-documented?

For each dimension, provide:
- score (1-10 integer)
- rationale (2-3 sentences with specific file/code references)

Return your response as valid JSON:
{
  "dimensions": {
    "readability": {"score": N, "rationale": "..."},
    "error_handling": {"score": N, "rationale": "..."},
    "architecture": {"score": N, "rationale": "..."},
    "code_smells": {"score": N, "rationale": "..."},
    "ai_friendliness": {"score": N, "rationale": "..."},
    "maintainability": {"score": N, "rationale": "..."}
  },
  "files_reviewed_summary": "Brief note on what you observed across the files."
}
Return ONLY the JSON object, no markdown fencing or extra text.\
"""

_DIMENSION_LABELS = {
    "readability": "Code Readability & Clarity",
    "error_handling": "Error Handling & Robustness",
    "architecture": "Design Patterns & Architecture",
    "code_smells": "Code Smells (absence of)",
    "ai_friendliness": "AI Agent Friendliness",
    "maintainability": "Maintainability & Extensibility",
}


class LLMCodeReviewChecker(BaseChecker):
    """Sends code samples to LLM for holistic quality assessment."""

    dimension_id = "llm_code_review"
    dimension_name = "LLM Code Review"
    default_weight = 20.0

    def __init__(
        self,
        repo_path: Path,
        languages: Optional[list[str]] = None,
        llm_config: Optional[dict[str, Any]] = None,
    ):
        super().__init__(repo_path, languages)
        self.llm_config = llm_config or {}
        self._files_sent: list[str] = []

    def run_checks(self) -> list[CheckResult]:
        """Sample files, send to LLM, parse scored review."""
        # Collect candidate files
        samples = self._select_files(max_files=15)
        if not samples:
            return [CheckResult(
                name="LLM Code Review",
                status=CheckStatus.SKIP,
                message="No source files found to review.",
            )]

        # Build the prompt
        prompt = self._build_review_prompt(samples)

        # Call the LLM
        try:
            raw_response = self._call_llm(prompt)
        except Exception as e:
            logger.warning("LLM code review call failed: %s", e, exc_info=True)
            return [CheckResult(
                name="LLM Code Review",
                status=CheckStatus.SKIP,
                message=f"LLM call failed: {e}",
            )]

        # Parse and validate
        results = self._parse_review(raw_response)

        # Log which files were sent for transparency
        if self._files_sent:
            logger.info(
                "LLM Code Review analyzed %d files: %s",
                len(self._files_sent),
                ", ".join(self._files_sent),
            )

        return results

    def _select_files(self, max_files: int = 15) -> list[tuple[str, str]]:
        """Select diverse source files for LLM review.

        Returns list of (relative_path, content) tuples.
        Uses per-directory quotas to ensure diversity.
        """
        candidates: dict[str, list[Path]] = {}  # directory → files

        for f in self.repo_path.rglob("*"):
            if not f.is_file():
                continue
            if f.suffix.lower() not in SOURCE_EXTENSIONS:
                continue
            # Skip excluded dirs
            parts = f.relative_to(self.repo_path).parts
            if any(p.lower() in SKIP_DIRS for p in parts):
                continue
            # Skip test files for this review (we assess production code)
            if any("test" in p.lower() or "spec" in p.lower() for p in parts):
                continue

            # Group by top-level directory (or root)
            dir_key = parts[0] if len(parts) > 1 else "__root__"
            candidates.setdefault(dir_key, []).append(f)

        if not candidates:
            return []

        # Allocate quota per directory, prioritizing entry points
        selected: list[Path] = []
        entry_points: list[Path] = []

        # First pass: find entry points
        for files in candidates.values():
            for f in files:
                if f.name.lower() in ENTRY_POINT_NAMES:
                    entry_points.append(f)

        selected.extend(entry_points[:3])

        # Second pass: distribute remaining quota across directories
        remaining = max_files - len(selected)
        dirs = list(candidates.keys())
        random.seed(42)  # Deterministic sampling
        per_dir = max(1, remaining // len(dirs))

        for dir_key in sorted(dirs):
            files = [f for f in candidates[dir_key] if f not in selected]
            if not files:
                continue
            # Prefer larger files (more logic to review) but cap it
            files.sort(key=lambda f: f.stat().st_size, reverse=True)
            # Take a mix: first (largest) + some random middle ones
            picks = files[:max(1, per_dir // 2)]
            if len(files) > 2:
                mid = files[len(files) // 4 : 3 * len(files) // 4]
                random.shuffle(mid)
                picks.extend(mid[: per_dir - len(picks)])
            selected.extend(picks)

        selected = selected[:max_files]

        # Read file contents with smart truncation
        result: list[tuple[str, str]] = []
        for f in selected:
            rel_path = str(f.relative_to(self.repo_path))
            content = self._read_smart(f, max_lines=300)
            if content:
                result.append((rel_path, content))
                self._files_sent.append(rel_path)

        return result

    def _read_smart(self, path: Path, max_lines: int = 300) -> Optional[str]:
        """Read a file, sampling top + middle sections for large files."""
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return None

        if len(lines) <= max_lines:
            return "\n".join(lines)

        # Take top (imports/declarations) + middle chunk (business logic)
        top = lines[:100]
        mid_start = len(lines) // 3
        mid = lines[mid_start : mid_start + 150]
        bottom = lines[-50:]

        return "\n".join(
            top
            + [f"\n... [{len(lines) - 300} lines omitted] ...\n"]
            + mid
            + [f"\n... [skipped to end] ...\n"]
            + bottom
        )

    def _build_review_prompt(self, samples: list[tuple[str, str]]) -> str:
        """Build the user prompt with repo structure and code samples."""
        sections: list[str] = []

        # Repo structure
        sections.append("## Repository Structure (top level)")
        try:
            entries = sorted(self.repo_path.iterdir())
            for entry in entries[:40]:
                kind = "dir/" if entry.is_dir() else ""
                sections.append(f"  {kind}{entry.name}")
        except OSError:
            sections.append("  (unable to list)")

        sections.append(f"\n## Languages Detected: {', '.join(self.languages)}")

        # Code samples
        sections.append(f"\n## Source Code Samples ({len(samples)} files)")
        for rel_path, content in samples:
            sections.append(f"\n### File: {rel_path}")
            sections.append(f"```\n{content}\n```")

        sections.append(f"\n## Files Sent for Review")
        for rel_path, _ in samples:
            sections.append(f"  - {rel_path}")

        return "\n".join(sections)

    def _call_llm(self, user_prompt: str, retries: int = 2) -> str:
        """Call the LLM with retry on JSON parse failure."""
        provider = self.llm_config.get("provider", "openai")

        for attempt in range(retries + 1):
            raw = self._do_call(provider, user_prompt)
            # Validate JSON
            try:
                parsed = self._extract_json(raw)
                if "dimensions" in parsed:
                    return raw
            except (json.JSONDecodeError, ValueError):
                pass

            if attempt < retries:
                logger.info("LLM returned invalid JSON, retrying (%d/%d)...", attempt + 1, retries)

        return raw  # Return last attempt even if not perfect JSON

    def _do_call(self, provider: str, user_prompt: str) -> str:
        """Execute the actual LLM API call."""
        if provider == "azure":
            from openai import AzureOpenAI
            client = AzureOpenAI(
                api_key=self.llm_config.get("api_key", "") or os.environ.get("AZURE_OPENAI_API_KEY", ""),
                azure_endpoint=self.llm_config.get("azure_endpoint", "") or os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
                api_version=self.llm_config.get("azure_api_version", "") or os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
            )
            model = self.llm_config.get("azure_deployment", "") or self.llm_config.get("model", "gpt-4o")
        else:
            from openai import OpenAI
            client = OpenAI(
                api_key=self.llm_config.get("api_key", "") or os.environ.get("OPENAI_API_KEY", ""),
            )
            model = self.llm_config.get("model", "gpt-4o")

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _REVIEW_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content or ""

    def _extract_json(self, raw: str) -> dict:
        """Strip markdown fences and parse JSON."""
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        return json.loads(text.strip())

    def _parse_review(self, raw_response: str) -> list[CheckResult]:
        """Parse LLM response into scored CheckResults."""
        try:
            data = self._extract_json(raw_response)
        except (json.JSONDecodeError, ValueError):
            logger.warning("Could not parse LLM code review JSON.")
            return [CheckResult(
                name="LLM Code Review",
                status=CheckStatus.WARN,
                message="LLM returned unparseable response — falling back to partial analysis.",
                raw_score=5.0,
            )]

        dims = data.get("dimensions", {})
        summary = data.get("files_reviewed_summary", "")
        results: list[CheckResult] = []

        for dim_key, label in _DIMENSION_LABELS.items():
            dim_data = dims.get(dim_key, {})
            score = dim_data.get("score")
            rationale = dim_data.get("rationale", "No rationale provided.")

            if score is None:
                results.append(CheckResult(
                    name=label,
                    status=CheckStatus.SKIP,
                    message="LLM did not score this dimension.",
                ))
                continue

            score = max(1.0, min(10.0, float(score)))

            if score >= 7:
                status = CheckStatus.PASS
            elif score >= 4:
                status = CheckStatus.WARN
            else:
                status = CheckStatus.FAIL

            results.append(CheckResult(
                name=label,
                status=status,
                message=f"Score: {score:.0f}/10 — {rationale}",
                raw_score=score,
                recommendation=self._recommendation(dim_key, score) if score < 7 else None,
                details=f"Files reviewed: {', '.join(self._files_sent[:5])}{'...' if len(self._files_sent) > 5 else ''}",
            ))

        # Add summary as an info check
        if summary:
            results.append(CheckResult(
                name="Review Summary",
                status=CheckStatus.PASS,
                message=summary,
            ))

        return results

    @staticmethod
    def _recommendation(dim_key: str, score: float) -> str:
        """Generate targeted recommendation based on dimension and score."""
        recs = {
            "readability": "Improve variable/function naming, add inline comments, and ensure consistent formatting.",
            "error_handling": "Add proper error handling, validate inputs, and cover edge cases in critical paths.",
            "architecture": "Reduce coupling between modules, apply SOLID principles, and clarify component boundaries.",
            "code_smells": "Refactor duplicated code, break up large classes/functions, and replace magic numbers with constants.",
            "ai_friendliness": "Add function docstrings, reduce complex nesting, and make code patterns more predictable for AI agents.",
            "maintainability": "Improve modularity, reduce file sizes, and add interface documentation for extension points.",
        }
        return recs.get(dim_key, "Review and improve code quality in this area.")

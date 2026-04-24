"""Checker for AI agent configuration files."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from ai_readiness.checkers.base import BaseChecker
from ai_readiness.core.models import CheckResult, CheckStatus

# Mapping: agent name → (check method name suffix, display name)
AGENT_REGISTRY = {
    "copilot": {
        "checks": ["copilot_instructions", "copilot_setup_steps"],
        "display": "GitHub Copilot",
    },
    "cursor": {
        "checks": ["cursor_config"],
        "display": "Cursor",
    },
    "claude": {
        "checks": ["claude_md"],
        "display": "Claude Code",
    },
    "aider": {
        "checks": ["aider_config"],
        "display": "Aider",
    },
    "agents_md": {
        "checks": ["agents_md"],
        "display": "AGENTS.md (generic)",
    },
}


class AIConfigChecker(BaseChecker):
    """Assess the presence of configuration files that help AI coding agents."""

    dimension_id: str = "ai_config"
    dimension_name: str = "AI Agent Configuration"
    default_weight: float = 15.0

    def __init__(
        self,
        repo_path: Path,
        languages: Optional[list[str]] = None,
        target_agents: Optional[list[str]] = None,
    ):
        super().__init__(repo_path, languages)
        # None = check all; list = only score these
        self.target_agents = target_agents

    def run_checks(self) -> list[CheckResult]:
        results: list[CheckResult] = []
        results.append(self._check_copilot_instructions())
        results.append(self._check_copilot_setup_steps())
        results.append(self._check_cursor_config())
        results.append(self._check_agents_md())
        results.append(self._check_claude_md())
        results.append(self._check_aider_config())
        results.append(self._check_has_any_ai_config())

        # If target_agents is set, mark non-targeted agent checks as non-scorable
        if self.target_agents:
            targeted_check_names = set()
            for agent in self.target_agents:
                agent_info = AGENT_REGISTRY.get(agent.lower())
                if agent_info:
                    for check_method in agent_info["checks"]:
                        targeted_check_names.add(check_method)

            # Map check names to their method suffixes for matching
            check_name_map = {
                "Copilot instructions": "copilot_instructions",
                "Copilot setup steps": "copilot_setup_steps",
                "Cursor config": "cursor_config",
                "AGENTS.md": "agents_md",
                "CLAUDE.md": "claude_md",
                "Aider config": "aider_config",
            }

            for check in results:
                method_key = check_name_map.get(check.name)
                if method_key and method_key not in targeted_check_names:
                    check.scorable = False  # Info-only for non-targeted agents

        return results

    # ------------------------------------------------------------------

    def _check_copilot_instructions(self) -> CheckResult:
        if self.files_exist_any(".github/copilot-instructions.md"):
            return CheckResult(
                name="Copilot instructions",
                status=CheckStatus.PASS,
                message=".github/copilot-instructions.md found.",
            )
        return CheckResult(
            name="Copilot instructions",
            status=CheckStatus.FAIL,
            message="No .github/copilot-instructions.md found.",
            recommendation="Add .github/copilot-instructions.md with project-specific guidance for GitHub Copilot.",
        )

    def _check_copilot_setup_steps(self) -> CheckResult:
        if self.files_exist_any(".github/copilot-setup-steps.yml"):
            return CheckResult(
                name="Copilot setup steps",
                status=CheckStatus.PASS,
                message=".github/copilot-setup-steps.yml found.",
            )
        return CheckResult(
            name="Copilot setup steps",
            status=CheckStatus.FAIL,
            message="No .github/copilot-setup-steps.yml found.",
            recommendation="Add .github/copilot-setup-steps.yml to automate environment setup for Copilot coding agent.",
        )

    def _check_cursor_config(self) -> CheckResult:
        if self.files_exist_any(".cursorrules"):
            return CheckResult(
                name="Cursor config",
                status=CheckStatus.PASS,
                message=".cursorrules file found.",
            )
        cursor_dir = self.repo_path / ".cursor"
        if cursor_dir.is_dir():
            return CheckResult(
                name="Cursor config",
                status=CheckStatus.PASS,
                message=".cursor/ directory found.",
            )
        return CheckResult(
            name="Cursor config",
            status=CheckStatus.FAIL,
            message="No .cursorrules or .cursor/ directory found.",
            recommendation="Add a .cursorrules file or .cursor/ directory with project rules for Cursor AI.",
        )

    def _check_agents_md(self) -> CheckResult:
        if self.files_exist_any("AGENTS.md"):
            return CheckResult(
                name="AGENTS.md",
                status=CheckStatus.PASS,
                message="AGENTS.md found.",
            )
        return CheckResult(
            name="AGENTS.md",
            status=CheckStatus.FAIL,
            message="No AGENTS.md found.",
            recommendation="Add an AGENTS.md with instructions and conventions for AI coding agents.",
        )

    def _check_claude_md(self) -> CheckResult:
        if self.files_exist_any("CLAUDE.md"):
            return CheckResult(
                name="CLAUDE.md",
                status=CheckStatus.PASS,
                message="CLAUDE.md found.",
            )
        return CheckResult(
            name="CLAUDE.md",
            status=CheckStatus.FAIL,
            message="No CLAUDE.md found.",
            recommendation="Add a CLAUDE.md with project-specific instructions for Claude Code.",
        )

    def _check_aider_config(self) -> CheckResult:
        aider_patterns = [".aider.conf.yml", ".aider.model.settings.yml", ".aiderignore"]
        for pattern in aider_patterns:
            if self.files_exist_any(pattern):
                return CheckResult(
                    name="Aider config",
                    status=CheckStatus.PASS,
                    message=f"Aider configuration file ({pattern}) found.",
                )
        return CheckResult(
            name="Aider config",
            status=CheckStatus.FAIL,
            message="No .aider* configuration files found.",
            recommendation="Add aider config files (e.g. .aider.conf.yml) if using Aider for AI-assisted development.",
        )

    def _check_has_any_ai_config(self) -> CheckResult:
        ai_indicators = [
            ".github/copilot-instructions.md",
            ".github/copilot-setup-steps.yml",
            ".cursorrules",
            "AGENTS.md",
            "CLAUDE.md",
            ".aider.conf.yml",
            ".aider.model.settings.yml",
            ".aiderignore",
        ]
        for indicator in ai_indicators:
            if self.files_exist_any(indicator):
                return CheckResult(
                    name="Has any AI config",
                    status=CheckStatus.PASS,
                    message="At least one AI agent configuration file is present.",
                )
        cursor_dir = self.repo_path / ".cursor"
        if cursor_dir.is_dir():
            return CheckResult(
                name="Has any AI config",
                status=CheckStatus.PASS,
                message="At least one AI agent configuration (.cursor/) is present.",
            )
        return CheckResult(
            name="Has any AI config",
            status=CheckStatus.FAIL,
            message="No AI agent configuration files found.",
            recommendation=(
                "Add at least one AI config file (e.g. .github/copilot-instructions.md, "
                "CLAUDE.md, AGENTS.md) to help AI agents understand your project."
            ),
        )

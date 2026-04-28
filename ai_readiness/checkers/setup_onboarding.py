"""Checker for project setup and developer onboarding experience."""
from __future__ import annotations

from ai_readiness.checkers.base import BaseChecker
from ai_readiness.core.models import CheckResult, CheckStatus


class SetupOnboardingChecker(BaseChecker):
    """Assess how easy it is for a new developer (or AI agent) to set up the project."""

    dimension_id: str = "setup_onboarding"
    dimension_name: str = "Setup & Onboarding"
    default_weight: float = 15.0

    def run_checks(self) -> list[CheckResult]:
        results: list[CheckResult] = []
        results.append(self._check_single_command_build())
        results.append(self._check_containerisation())
        results.append(self._check_scripts_dir())
        results.append(self._check_env_template())
        return results

    # ------------------------------------------------------------------

    def _check_single_command_build(self) -> CheckResult:
        # Check for task runners
        if self.files_exist_any("Makefile", "justfile", "Taskfile.yml", "Taskfile.yaml"):
            return CheckResult(
                name="Single-command build",
                status=CheckStatus.PASS,
                message="Build automation file found (Makefile, justfile, or Taskfile).",
            )
        # Check for root-level build/init scripts (any language)
        import re
        build_patterns = re.compile(
            r"^(init|build|setup|bootstrap|start|run)\.(ps1|cmd|sh|bash|bat|py|rb)$",
            re.IGNORECASE,
        )
        try:
            root_scripts = [
                f.name for f in self.repo_path.iterdir()
                if f.is_file() and build_patterns.match(f.name)
            ]
        except OSError:
            root_scripts = []

        if root_scripts:
            names = ", ".join(sorted(root_scripts)[:5])
            return CheckResult(
                name="Single-command build",
                status=CheckStatus.PASS,
                message=f"Build/init scripts found at root: {names}.",
            )
        return CheckResult(
            name="Single-command build",
            status=CheckStatus.FAIL,
            message="No Makefile, justfile, Taskfile, or build/init scripts found.",
            recommendation="Add a Makefile or justfile so the project can be built/tested with a single command.",
        )

    def _check_containerisation(self) -> CheckResult:
        if self.files_exist_any(
            "Dockerfile",
            "docker-compose.yml",
            "docker-compose.yaml",
            "compose.yml",
            "compose.yaml",
        ):
            return CheckResult(
                name="Container support",
                status=CheckStatus.PASS,
                message="Dockerfile or Docker Compose configuration found.",
            )
        # Skip if repo doesn't look like a deployable service
        if not self._looks_like_service():
            return CheckResult(
                name="Container support",
                status=CheckStatus.SKIP,
                message="Skipped — repo does not appear to be a deployable service.",
                scorable=False,
            )
        return CheckResult(
            name="Container support",
            status=CheckStatus.FAIL,
            message="No Dockerfile or docker-compose file found.",
            recommendation="Add a Dockerfile or docker-compose.yml for reproducible environment setup.",
        )

    def _check_scripts_dir(self) -> CheckResult:
        # Check for scripts/ or bin/ directories
        for dirname in ("scripts", "bin", ".config/.scripts", "tools"):
            d = self.repo_path / dirname
            if d.is_dir() and any(d.iterdir()):
                return CheckResult(
                    name="Helper scripts",
                    status=CheckStatus.PASS,
                    message=f"{dirname}/ directory with helper scripts found.",
                )
        # Check for root-level helper scripts
        try:
            script_exts = {".ps1", ".cmd", ".sh", ".bash", ".bat", ".py", ".rb"}
            root_scripts = [
                f.name for f in self.repo_path.iterdir()
                if f.is_file() and f.suffix.lower() in script_exts
            ]
        except OSError:
            root_scripts = []

        if root_scripts:
            count = len(root_scripts)
            return CheckResult(
                name="Helper scripts",
                status=CheckStatus.PASS,
                message=f"{count} script(s) found at repo root.",
            )
        return CheckResult(
            name="Helper scripts",
            status=CheckStatus.FAIL,
            message="No scripts/ or bin/ directory with helper scripts found.",
            recommendation="Add a scripts/ or bin/ directory with setup/build/test helper scripts.",
        )

    def _check_env_template(self) -> CheckResult:
        if self.files_exist_any(".env.example", ".env.template", ".env.sample"):
            return CheckResult(
                name="Environment template",
                status=CheckStatus.PASS,
                message="Environment variable template found.",
            )
        # Skip if repo doesn't show env var usage signals
        if not self._has_env_var_usage() and not self._looks_like_service():
            return CheckResult(
                name="Environment template",
                status=CheckStatus.SKIP,
                message="Skipped — no environment variable usage detected.",
                scorable=False,
            )
        return CheckResult(
            name="Environment template",
            status=CheckStatus.FAIL,
            message="No .env.example or .env.template found.",
            recommendation="Add a .env.example documenting required environment variables.",
        )

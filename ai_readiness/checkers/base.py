"""Abstract base class for all assessment checkers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from ai_readiness.core.models import CheckResult, CheckStatus, DimensionScore


class BaseChecker(ABC):
    """Base class for all dimension checkers.

    Subclasses implement `run_checks()` to return a list of CheckResults.
    The framework handles scoring and aggregation.
    """

    dimension_id: str = ""
    dimension_name: str = ""
    default_weight: float = 10.0

    def __init__(self, repo_path: Path, languages: Optional[list[str]] = None):
        self.repo_path = repo_path
        self.languages = languages or []

    @abstractmethod
    def run_checks(self) -> list[CheckResult]:
        """Run all checks for this dimension and return results."""
        ...

    def evaluate(self, weight: Optional[float] = None) -> DimensionScore:
        """Run checks and compute the dimension score."""
        checks = self.run_checks()
        weight = weight if weight is not None else self.default_weight

        # If checks have raw_score values (e.g. from LLM), use their average
        raw_scores = [c.raw_score for c in checks if c.raw_score is not None]
        if raw_scores:
            score = sum(raw_scores) / len(raw_scores)
        else:
            scorable = [c for c in checks if c.status != CheckStatus.SKIP]
            if not scorable:
                score = 0.0
            else:
                passed = sum(1 for c in scorable if c.status == CheckStatus.PASS)
                warned = sum(1 for c in scorable if c.status == CheckStatus.WARN)
                score = ((passed + warned * 0.5) / len(scorable)) * 10.0

        return DimensionScore(
            dimension_id=self.dimension_id,
            dimension_name=self.dimension_name,
            score=round(score, 1),
            weight=weight,
            checks=checks,
        )

    # --- Helper methods for subclasses ---

    def file_exists(self, *patterns: str) -> Optional[Path]:
        """Check if any file matching the patterns exists (case-insensitive)."""
        for pattern in patterns:
            matches = list(self.repo_path.glob(pattern))
            if not matches:
                # Try case-insensitive on Windows/macOS
                lower = pattern.lower()
                for f in self.repo_path.rglob("*"):
                    if f.relative_to(self.repo_path).as_posix().lower() == lower:
                        return f
            if matches:
                return matches[0]
        return None

    def files_exist_any(self, *patterns: str) -> bool:
        """Return True if any of the patterns match a file."""
        return self.file_exists(*patterns) is not None

    def glob_files(self, pattern: str) -> list[Path]:
        """Return all files matching a glob pattern."""
        return list(self.repo_path.rglob(pattern))

    def read_file_safe(self, path: Path, max_bytes: int = 50_000) -> Optional[str]:
        """Read a file safely, returning None on failure."""
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            return content[:max_bytes]
        except (OSError, UnicodeDecodeError):
            return None

    def has_language(self, *langs: str) -> bool:
        """Check if any of the given languages were detected."""
        return any(lang.lower() in [l.lower() for l in self.languages] for lang in langs)

    # --- Repo context detection helpers ---

    def _looks_like_service(self) -> bool:
        """Heuristic: does this repo look like a deployable service/app?

        Returns True if the repo has signals like web frameworks, server
        entry points, deployment configs, or CI/CD pipelines that deploy.
        """
        # Web framework / server indicators
        service_files = [
            "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
            "compose.yml", "compose.yaml",
            "Procfile", "app.yaml", "serverless.yml", "serverless.yaml",
            "kubernetes", "k8s", "helm",
            "terraform", ".terraform",
        ]
        for name in service_files:
            if (self.repo_path / name).exists():
                return True

        # Check for deployment directories
        deploy_dirs = ["deploy", "deployment", "infra", "infrastructure", "k8s", "helm", "kubernetes"]
        for d in deploy_dirs:
            if (self.repo_path / d).is_dir():
                return True

        # Check for web/server entry points in common manifests
        for manifest in ["package.json", "pyproject.toml", "setup.py", "pom.xml", "build.gradle"]:
            path = self.repo_path / manifest
            if path.is_file():
                try:
                    content = path.read_text(encoding="utf-8", errors="replace")[:10_000]
                    server_hints = ["flask", "django", "fastapi", "express", "koa", "hapi",
                                    "spring-boot", "asp.net", "webapi", "grpc", "uvicorn",
                                    "gunicorn", "nginx", "server", "host"]
                    if any(h in content.lower() for h in server_hints):
                        return True
                except OSError:
                    pass

        return False

    def _has_env_var_usage(self) -> bool:
        """Heuristic: does this repo reference environment variables?"""
        # Check for .env files (not templates)
        env_patterns = [".env", ".env.local", ".env.development", ".env.production"]
        for p in env_patterns:
            if (self.repo_path / p).is_file():
                return True

        # Check common config files for env var patterns
        config_files = ["appsettings.json", "config.yaml", "config.yml",
                        ".env.example", ".env.template", ".env.sample"]
        for c in config_files:
            if (self.repo_path / c).is_file():
                return True

        return False

    def _is_collaborative(self) -> bool:
        """Heuristic: does this repo look like a multi-contributor project?"""
        signals = [
            ".github/CODEOWNERS", "CODEOWNERS",
            ".github/pull_request_template.md",
            ".github/ISSUE_TEMPLATE",
            "CONTRIBUTING.md", "CONTRIBUTING",
        ]
        for s in signals:
            if (self.repo_path / s).exists():
                return True

        # Check git log for multiple authors (lightweight: just check if .git exists
        # and there's evidence of collaboration)
        if (self.repo_path / ".github").is_dir():
            return True

        return False

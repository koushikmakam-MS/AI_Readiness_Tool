"""Repository resolver — handles local paths and remote Git URLs."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from rich.console import Console

console = Console(stderr=True)


class RepoResolver:
    """Resolves a repo target (local path or remote URL) to a scannable local path.

    For private repos in CI, set GITHUB_TOKEN env var. The resolver injects it
    into HTTPS clone URLs automatically.
    """

    def __init__(self, target: str, clone_dir: Optional[str] = None, github_token: Optional[str] = None):
        self.target = target.strip()
        self.clone_dir = clone_dir
        self.github_token = github_token or os.environ.get("GITHUB_TOKEN", "")
        self._temp_dir: Optional[tempfile.TemporaryDirectory] = None
        self._cloned_path: Optional[Path] = None

    @property
    def is_remote(self) -> bool:
        """Check if the target is a remote Git URL."""
        if self.target.startswith(("http://", "https://", "git@", "ssh://")):
            return True
        # Handle shorthand like "owner/repo"
        if "/" in self.target and not Path(self.target).exists():
            parts = self.target.split("/")
            if len(parts) == 2 and not self.target.startswith((".", "/")):
                return True
        return False

    def resolve(self) -> Path:
        """Resolve the target to a local path, cloning if necessary."""
        if not self.is_remote:
            path = Path(self.target).resolve()
            if not path.exists():
                raise FileNotFoundError(f"Local path does not exist: {path}")
            if not path.is_dir():
                raise NotADirectoryError(f"Path is not a directory: {path}")
            return path

        return self._clone_repo()

    def _normalize_url(self) -> str:
        """Normalize the target into a proper Git clone URL."""
        # Handle shorthand "owner/repo" → full GitHub URL
        if not self.target.startswith(("http", "git@", "ssh://")):
            if "/" in self.target:
                parts = self.target.strip("/").split("/")
                if len(parts) >= 2:
                    return f"https://github.com/{parts[0]}/{parts[1]}.git"

        url = self.target
        # Ensure .git suffix for HTTPS URLs (skip Azure DevOps _git URLs)
        if url.startswith("https://") and not url.endswith(".git") and "/_git/" not in url:
            url = url.rstrip("/") + ".git"

        return url

    def _get_clone_url(self) -> str:
        """Get the clone URL, injecting GitHub token for private repos if available."""
        url = self._normalize_url()

        if self.github_token and url.startswith("https://"):
            # Inject token: https://github.com/... → https://<token>@github.com/...
            parsed = urlparse(url)
            url = f"https://{self.github_token}@{parsed.hostname}{parsed.path}"

        return url

    def _derive_repo_name(self) -> str:
        """Extract a repo name from the URL for the clone directory."""
        url = self._normalize_url()
        parsed = urlparse(url)
        path = parsed.path.rstrip("/").removesuffix(".git")
        name = path.split("/")[-1] if "/" in path else "repo"
        return name or "repo"

    def _clone_repo(self) -> Path:
        """Clone the remote repository."""
        clone_url = self._get_clone_url()
        display_url = self._normalize_url()  # safe for logging (no token)
        repo_name = self._derive_repo_name()

        if self.clone_dir:
            # User-specified directory
            clone_path = Path(self.clone_dir).resolve() / repo_name
            clone_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            # Temp directory (auto-cleaned)
            self._temp_dir = tempfile.TemporaryDirectory(prefix="ai-readiness-")
            clone_path = Path(self._temp_dir.name) / repo_name

        if clone_path.exists() and (clone_path / ".git").exists():
            # Already cloned — pull latest (shallow fetch to stay fast)
            console.print(f"[dim]Repository already cloned at {clone_path}, pulling latest...[/dim]")
            try:
                subprocess.run(
                    ["git", "-C", str(clone_path), "fetch", "--depth", "1", "--quiet"],
                    check=True,
                    capture_output=True,
                    timeout=120,
                )
                subprocess.run(
                    ["git", "-C", str(clone_path), "reset", "--hard", "FETCH_HEAD"],
                    check=True,
                    capture_output=True,
                    timeout=30,
                )
            except subprocess.CalledProcessError:
                console.print("[yellow]Warning: git pull failed, using existing clone.[/yellow]")
        else:
            # Fresh shallow clone (no history, single branch, no tags)
            console.print(f"[dim]Cloning {display_url} → {clone_path} (shallow)...[/dim]")
            try:
                subprocess.run(
                    [
                        "git", "clone",
                        "--depth", "1",
                        "--single-branch",
                        "--no-tags",
                        "--quiet",
                        clone_url,
                        str(clone_path),
                    ],
                    check=True,
                    capture_output=True,
                    timeout=300,
                )
            except subprocess.CalledProcessError as e:
                stderr = e.stderr.decode(errors="replace") if e.stderr else "Unknown error"
                raise RuntimeError(f"Failed to clone {display_url}: {stderr}") from e
            except FileNotFoundError:
                raise RuntimeError(
                    "Git is not installed or not on PATH. Install git to clone remote repos."
                )

        self._cloned_path = clone_path
        console.print(f"[green]✓[/green] Repository ready at {clone_path}")
        return clone_path

    def cleanup(self) -> None:
        """Clean up temp directory if one was created."""
        if self._temp_dir:
            try:
                self._temp_dir.cleanup()
            except (OSError, PermissionError):
                pass
            self._temp_dir = None

    def __enter__(self) -> RepoResolver:
        return self

    def __exit__(self, *args) -> None:
        self.cleanup()

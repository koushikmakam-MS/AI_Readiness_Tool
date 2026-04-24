"""Detect programming languages used in a repository."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

# Map file extensions to language names
EXTENSION_MAP: dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".kt": "Kotlin",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".cpp": "C++",
    ".c": "C",
    ".h": "C",
    ".hpp": "C++",
    ".swift": "Swift",
    ".scala": "Scala",
    ".r": "R",
    ".R": "R",
    ".m": "Objective-C",
    ".dart": "Dart",
    ".lua": "Lua",
    ".pl": "Perl",
    ".sh": "Shell",
    ".bash": "Shell",
    ".ps1": "PowerShell",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".erl": "Erlang",
    ".hs": "Haskell",
    ".clj": "Clojure",
    ".vue": "Vue",
    ".svelte": "Svelte",
}

# Map manifest files to languages
MANIFEST_MAP: dict[str, str] = {
    "package.json": "JavaScript",
    "tsconfig.json": "TypeScript",
    "requirements.txt": "Python",
    "setup.py": "Python",
    "pyproject.toml": "Python",
    "Pipfile": "Python",
    "go.mod": "Go",
    "Cargo.toml": "Rust",
    "Gemfile": "Ruby",
    "composer.json": "PHP",
    "pom.xml": "Java",
    "build.gradle": "Java",
    "build.gradle.kts": "Kotlin",
    "Package.swift": "Swift",
    "mix.exs": "Elixir",
    "pubspec.yaml": "Dart",
}

# Glob patterns for manifests that need wildcard matching
MANIFEST_GLOB_MAP: dict[str, str] = {
    "*.sln": "C#",
    "*.csproj": "C#",
    "*.fsproj": "F#",
}

# Directories to skip during scanning
SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv", "env",
    "vendor", "dist", "build", ".tox", ".mypy_cache", ".pytest_cache",
    "target", "bin", "obj", ".next", ".nuxt", "coverage",
    "out", ".vs", ".vscode", "packages", "TestResults",
}


def detect_languages(repo_path: Path, max_files: int = 5000) -> list[str]:
    """Detect languages in a repo, ordered by prevalence.

    Returns a list of language names sorted by file count (descending).
    """
    counter: Counter[str] = Counter()
    files_scanned = 0

    # Check manifest files first (strong signals)
    for manifest, lang in MANIFEST_MAP.items():
        if (repo_path / manifest).exists():
            counter[lang] += 50  # heavy weight for manifests

    # Check glob-based manifests (e.g., *.sln, *.csproj)
    for pattern, lang in MANIFEST_GLOB_MAP.items():
        if list(repo_path.glob(pattern)):
            counter[lang] += 50

    # Scan file extensions
    for item in _walk_files(repo_path, max_files):
        files_scanned += 1
        ext = item.suffix.lower()
        if ext in EXTENSION_MAP:
            counter[EXTENSION_MAP[ext]] += 1
        if files_scanned >= max_files:
            break

    # Return sorted by count
    return [lang for lang, _ in counter.most_common()]


def _walk_files(repo_path: Path, max_files: int) -> list[Path]:
    """Walk repository files, skipping irrelevant directories."""
    results: list[Path] = []
    try:
        for item in repo_path.rglob("*"):
            if item.is_file():
                # Skip files in ignored directories
                parts = item.relative_to(repo_path).parts
                if any(p in SKIP_DIRS for p in parts):
                    continue
                results.append(item)
                if len(results) >= max_files:
                    break
    except (PermissionError, OSError):
        pass
    return results

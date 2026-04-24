"""Common file utility functions."""

from __future__ import annotations

from pathlib import Path
from typing import Optional


def find_file_case_insensitive(repo_path: Path, name: str) -> Optional[Path]:
    """Find a file by name, case-insensitive, in the repo root."""
    for item in repo_path.iterdir():
        if item.is_file() and item.name.lower() == name.lower():
            return item
    return None


def count_lines(path: Path) -> int:
    """Count lines in a file, returning 0 on error."""
    try:
        return sum(1 for _ in path.open(encoding="utf-8", errors="replace"))
    except (OSError, UnicodeDecodeError):
        return 0


def file_has_content(path: Path, min_chars: int = 10) -> bool:
    """Check if a file exists and has meaningful content."""
    if not path.exists():
        return False
    try:
        content = path.read_text(encoding="utf-8", errors="replace").strip()
        return len(content) >= min_chars
    except (OSError, UnicodeDecodeError):
        return False

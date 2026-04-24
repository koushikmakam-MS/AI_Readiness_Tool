"""Shared fixtures and helpers for the AI Readiness test suite."""
from __future__ import annotations

from pathlib import Path

import pytest


def create_file(base: Path, name: str, content: str = "") -> Path:
    """Create a file inside *base*, making parent dirs as needed."""
    p = base / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p

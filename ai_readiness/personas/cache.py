"""SQLite-backed cache for embeddings and per-doc persona scores.

Located OUTSIDE the target repo (default: ``~/.ai-readiness/cache/<repo-id>``).
The target repo is never modified.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_CACHE_ROOT = Path.home() / ".ai-readiness" / "cache"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS embeddings (
    model TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    vector_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (model, content_hash)
);

CREATE TABLE IF NOT EXISTS scores (
    persona_id TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (persona_id, prompt_version, content_hash)
);

CREATE TABLE IF NOT EXISTS manifest (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def repo_cache_id(repo_path: Path, override: Optional[str] = None) -> str:
    """Stable id for a repo. Prefers git remote URL, then absolute path."""
    if override:
        return hashlib.sha256(override.encode("utf-8")).hexdigest()[:16]

    git_config = repo_path / ".git" / "config"
    if git_config.is_file():
        try:
            text = git_config.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                line = line.strip()
                if line.startswith("url ="):
                    url = line.split("=", 1)[1].strip()
                    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
        except OSError:
            pass

    return hashlib.sha256(
        str(repo_path.resolve()).encode("utf-8")
    ).hexdigest()[:16]


class PersonaCache:
    """SQLite cache for embeddings and persona rubric scores."""

    def __init__(
        self,
        repo_path: Path,
        *,
        cache_root: Optional[Path] = None,
        cache_key_override: Optional[str] = None,
        enabled: bool = True,
    ) -> None:
        self.enabled = enabled
        root = cache_root or DEFAULT_CACHE_ROOT
        self.repo_id = repo_cache_id(repo_path, cache_key_override)
        self.cache_dir = root / self.repo_id
        self.db_path = self.cache_dir / "cache.db"
        self._conn: Optional[sqlite3.Connection] = None

        if self.enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.executescript(_SCHEMA)
            self._conn.commit()
            self._touch_manifest(repo_path)

    # ------------------------------------------------------------------
    # Embeddings
    # ------------------------------------------------------------------

    def get_embedding(self, model: str, content_hash: str) -> Optional[list[float]]:
        if not self._conn:
            return None
        row = self._conn.execute(
            "SELECT vector_json FROM embeddings WHERE model=? AND content_hash=?",
            (model, content_hash),
        ).fetchone()
        if not row:
            return None
        try:
            return json.loads(row[0])
        except json.JSONDecodeError:
            return None

    def put_embedding(
        self, model: str, content_hash: str, vector: list[float]
    ) -> None:
        if not self._conn:
            return
        self._conn.execute(
            "INSERT OR REPLACE INTO embeddings(model, content_hash, vector_json, created_at) "
            "VALUES (?, ?, ?, ?)",
            (model, content_hash, json.dumps(vector), time.time()),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Scores
    # ------------------------------------------------------------------

    def get_score(
        self, persona_id: str, prompt_version: str, content_hash: str
    ) -> Optional[dict[str, Any]]:
        if not self._conn:
            return None
        row = self._conn.execute(
            "SELECT payload_json FROM scores "
            "WHERE persona_id=? AND prompt_version=? AND content_hash=?",
            (persona_id, prompt_version, content_hash),
        ).fetchone()
        if not row:
            return None
        try:
            return json.loads(row[0])
        except json.JSONDecodeError:
            return None

    def put_score(
        self,
        persona_id: str,
        prompt_version: str,
        content_hash: str,
        payload: dict[str, Any],
    ) -> None:
        if not self._conn:
            return
        self._conn.execute(
            "INSERT OR REPLACE INTO scores"
            "(persona_id, prompt_version, content_hash, payload_json, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                persona_id,
                prompt_version,
                content_hash,
                json.dumps(payload),
                time.time(),
            ),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def _touch_manifest(self, repo_path: Path) -> None:
        if not self._conn:
            return
        self._conn.execute(
            "INSERT OR REPLACE INTO manifest(key, value) VALUES(?, ?)",
            ("repo_path", str(repo_path.resolve())),
        )
        self._conn.execute(
            "INSERT OR REPLACE INTO manifest(key, value) VALUES(?, ?)",
            ("last_run", str(time.time())),
        )
        self._conn.commit()

    def clear(self) -> None:
        """Wipe all cached data for this repo."""
        if not self._conn:
            return
        self._conn.executescript(
            "DELETE FROM embeddings; DELETE FROM scores; DELETE FROM manifest;"
        )
        self._conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> PersonaCache:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

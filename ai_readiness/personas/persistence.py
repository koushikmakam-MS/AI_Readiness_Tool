"""Persist persona run reports to ``<cache_dir>/<repo_id>/runs/<timestamp>/``.

Writes both a `report.json` and a `report.md` for each run, plus updates a
`latest.json` pointer. Never touches the target repository.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from ai_readiness.personas.cache import PersonaCache
from ai_readiness.personas.reporter import to_json, to_markdown
from ai_readiness.personas.runner import RunReport

logger = logging.getLogger(__name__)


def persist_run(report: RunReport, cache: PersonaCache) -> Path | None:
    """Write the run report into the cache dir. Returns the run directory."""
    if not cache.enabled or not cache.cache_dir:
        return None

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    run_dir = cache.cache_dir / "runs" / timestamp
    try:
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "report.json").write_text(to_json(report), encoding="utf-8")
        (run_dir / "report.md").write_text(to_markdown(report), encoding="utf-8")
        # Update "latest" pointer.
        latest = cache.cache_dir / "runs" / "latest.json"
        latest.write_text(to_json(report), encoding="utf-8")
    except OSError:
        logger.warning("Could not persist run report to %s", run_dir, exc_info=True)
        return None
    return run_dir

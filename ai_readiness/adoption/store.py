"""Persistent JSON store for adoption snapshots.

Data is stored in ``<repo_root>/adoption_data/github_traffic.json`` so it
lives inside the repository and can be committed for historical tracking.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_FILENAME = "github_traffic.json"


def _data_dir(repo_root: Path) -> Path:
    return repo_root / "adoption_data"


def _data_path(repo_root: Path, filename: str = DEFAULT_FILENAME) -> Path:
    return _data_dir(repo_root) / filename


def load_history(repo_root: Path, filename: str = DEFAULT_FILENAME) -> dict[str, Any]:
    """Load the full history file, returning a dict with a ``snapshots`` list."""
    path = _data_path(repo_root, filename)
    if path.exists():
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return {"repo": "", "snapshots": []}


def append_snapshot(
    repo_root: Path,
    snapshot: dict[str, Any],
    filename: str = DEFAULT_FILENAME,
) -> Path:
    """Append *snapshot* to the history file, merging daily data intelligently.

    GitHub traffic API returns a rolling 14-day window.  We merge daily
    clone/view entries so that repeated fetches extend the timeline rather
    than duplicating rows.
    """
    history = load_history(repo_root, filename)
    history["repo"] = snapshot.get("repo", history.get("repo", ""))
    history["last_updated"] = datetime.now(timezone.utc).isoformat()

    # --- merge daily timeseries ------------------------------------------
    existing_daily_clones = _collect_daily(history, "daily_clones")
    existing_daily_views = _collect_daily(history, "daily_views")

    for entry in snapshot.get("daily_clones", []):
        ts = entry["timestamp"]
        existing_daily_clones[ts] = entry
    for entry in snapshot.get("daily_views", []):
        ts = entry["timestamp"]
        existing_daily_views[ts] = entry

    # Store merged timeseries at the top level
    history["daily_clones"] = sorted(
        existing_daily_clones.values(), key=lambda e: e["timestamp"]
    )
    history["daily_views"] = sorted(
        existing_daily_views.values(), key=lambda e: e["timestamp"]
    )

    # --- append the summary snapshot (without duplicating daily arrays) ---
    slim_snapshot = {k: v for k, v in snapshot.items() if k not in ("daily_clones", "daily_views")}
    history["snapshots"].append(slim_snapshot)

    # --- merge fork owners across all snapshots --------------------------
    all_forks = set()
    for snap in history["snapshots"]:
        all_forks.update(snap.get("fork_owners", []))
    history["all_fork_owners"] = sorted(all_forks)

    # --- write -----------------------------------------------------------
    path = _data_path(repo_root, filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(history, fh, indent=2, default=str)

    return path


def _collect_daily(history: dict, key: str) -> dict[str, dict]:
    """Collect daily entries from top-level merged store + older snapshots."""
    by_ts: dict[str, dict] = {}
    # Top-level merged data (preferred)
    for entry in history.get(key, []):
        by_ts[entry["timestamp"]] = entry
    # Fallback: scan older snapshots
    for snap in history.get("snapshots", []):
        for entry in snap.get(key, []):
            if entry["timestamp"] not in by_ts:
                by_ts[entry["timestamp"]] = entry
    return by_ts

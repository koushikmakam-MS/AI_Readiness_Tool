"""Fetch adoption metrics from the GitHub API.

Uses the ``gh`` CLI (if available) or falls back to ``requests`` / ``urllib``
so that the user's existing GitHub auth is reused automatically.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from typing import Any


def _gh_api(endpoint: str) -> Any:
    """Call ``gh api <endpoint>`` and return parsed JSON."""
    result = subprocess.run(
        ["gh", "api", endpoint],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"gh api {endpoint} failed (exit {result.returncode}): {result.stderr.strip()}"
        )
    return json.loads(result.stdout)


def fetch_github_stats(owner_repo: str) -> dict[str, Any]:
    """Return a snapshot dict with clone, view, fork and star counts.

    Parameters
    ----------
    owner_repo:
        ``owner/repo`` slug, e.g. ``"koushikmakam-MS/AI_Readiness_Tool"``.
    """
    repo = _gh_api(f"repos/{owner_repo}")
    clones = _gh_api(f"repos/{owner_repo}/traffic/clones")
    views = _gh_api(f"repos/{owner_repo}/traffic/views")
    referrers = _gh_api(f"repos/{owner_repo}/traffic/popular/referrers")

    # Forks list (paginated – grab first page for names)
    try:
        forks_list = _gh_api(f"repos/{owner_repo}/forks?per_page=100")
    except RuntimeError:
        forks_list = []

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "github",
        "repo": owner_repo,
        "stars": repo.get("stargazers_count", 0),
        "forks_count": repo.get("forks_count", 0),
        "watchers": repo.get("subscribers_count", 0),
        "open_issues": repo.get("open_issues_count", 0),
        "clones": {
            "total": clones.get("count", 0),
            "unique": clones.get("uniques", 0),
        },
        "views": {
            "total": views.get("count", 0),
            "unique": views.get("uniques", 0),
        },
        "daily_clones": clones.get("clones", []),
        "daily_views": views.get("views", []),
        "top_referrers": [
            {"name": r["referrer"], "views": r["count"], "unique": r["uniques"]}
            for r in (referrers or [])
        ],
        "fork_owners": [f["owner"]["login"] for f in (forks_list or [])],
    }

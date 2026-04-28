"""Tests for run-report persistence."""

from __future__ import annotations

import json
from pathlib import Path

from ai_readiness.personas.cache import PersonaCache
from ai_readiness.personas.persistence import persist_run
from ai_readiness.personas.runner import RunReport
from ai_readiness.personas.scorer import aggregate


def test_persist_run_writes_json_and_md(tmp_path: Path) -> None:
    cache = PersonaCache(tmp_path, cache_root=tmp_path / "cache", enabled=True)
    report = RunReport(
        overall=aggregate([]),
        persona_results=[],
        docs_total=0,
        chunks_total=0,
    )
    run_dir = persist_run(report, cache)
    assert run_dir is not None
    assert (run_dir / "report.json").is_file()
    assert (run_dir / "report.md").is_file()
    # latest.json is updated.
    latest = cache.cache_dir / "runs" / "latest.json"
    assert latest.is_file()
    payload = json.loads(latest.read_text(encoding="utf-8"))
    assert payload["docs_total"] == 0
    cache.close()


def test_persist_run_noop_when_cache_disabled(tmp_path: Path) -> None:
    cache = PersonaCache(tmp_path, enabled=False)
    report = RunReport(
        overall=aggregate([]),
        persona_results=[],
        docs_total=0,
        chunks_total=0,
    )
    assert persist_run(report, cache) is None
    cache.close()

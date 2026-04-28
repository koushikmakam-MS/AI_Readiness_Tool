"""Unit tests for ai_readiness.personas.cache."""

from __future__ import annotations

from pathlib import Path

from ai_readiness.personas.cache import PersonaCache, repo_cache_id


def test_repo_cache_id_uses_override(tmp_path: Path) -> None:
    a = repo_cache_id(tmp_path, override="my-key")
    b = repo_cache_id(tmp_path, override="my-key")
    c = repo_cache_id(tmp_path, override="other")
    assert a == b
    assert a != c


def test_cache_roundtrip_embeddings(tmp_path: Path) -> None:
    cache = PersonaCache(tmp_path, cache_root=tmp_path / "cache")
    assert cache.get_embedding("m", "h") is None
    cache.put_embedding("m", "h", [0.1, 0.2, 0.3])
    assert cache.get_embedding("m", "h") == [0.1, 0.2, 0.3]
    cache.close()


def test_cache_roundtrip_scores(tmp_path: Path) -> None:
    cache = PersonaCache(tmp_path, cache_root=tmp_path / "cache")
    payload = {"scores": {"context_sufficiency": 4.0}, "justification": "ok"}
    cache.put_score("dora", "v1", "abc", payload)
    got = cache.get_score("dora", "v1", "abc")
    assert got == payload
    cache.close()


def test_cache_disabled_is_noop(tmp_path: Path) -> None:
    cache = PersonaCache(tmp_path, enabled=False)
    cache.put_embedding("m", "h", [1.0])
    assert cache.get_embedding("m", "h") is None
    cache.close()


def test_clear_wipes_data(tmp_path: Path) -> None:
    cache = PersonaCache(tmp_path, cache_root=tmp_path / "cache")
    cache.put_embedding("m", "h", [1.0])
    cache.clear()
    assert cache.get_embedding("m", "h") is None
    cache.close()

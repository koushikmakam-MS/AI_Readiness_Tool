"""Unit tests for ai_readiness.personas.doc_index."""

from __future__ import annotations

from pathlib import Path

from ai_readiness.personas.doc_index import chunk_doc, discover_docs


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_discover_docs_finds_markdown_and_skips_excluded(tmp_path: Path) -> None:
    _write(tmp_path / "README.md", "# Hello\n\nworld")
    _write(tmp_path / "docs" / "guide.md", "# Guide")
    _write(tmp_path / "node_modules" / "junk.md", "# nope")
    _write(tmp_path / ".git" / "HEAD", "junk")
    _write(tmp_path / "AGENTS.md", "agents")
    _write(tmp_path / "src" / "code.py", "print(1)")  # not a doc

    docs = discover_docs(tmp_path)
    rels = {d.relative_path for d in docs}

    assert "README.md" in rels
    assert "AGENTS.md" in rels
    assert "docs/guide.md" in rels
    assert not any("node_modules" in r for r in rels)
    assert not any(".git" in r for r in rels)
    assert not any(r.endswith(".py") for r in rels)


def test_chunk_doc_small_returns_single_chunk(tmp_path: Path) -> None:
    p = tmp_path / "small.md"
    _write(p, "# Title\n\nshort content")
    docs = discover_docs(tmp_path)
    assert len(docs) == 1
    chunks = chunk_doc(docs[0], max_chunk_chars=8000)
    assert len(chunks) == 1
    assert chunks[0].chunk_id == "small.md"


def test_chunk_doc_large_splits_by_heading(tmp_path: Path) -> None:
    body = (
        "# A\n"
        + ("alpha " * 500)
        + "\n# B\n"
        + ("beta " * 500)
        + "\n# C\n"
        + ("gamma " * 500)
    )
    p = tmp_path / "big.md"
    _write(p, body)
    docs = discover_docs(tmp_path)
    chunks = chunk_doc(docs[0], max_chunk_chars=1000)
    headings = [c.heading for c in chunks]
    # Each section may be further split into "(part N)" pieces; check that
    # all three top-level headings are represented somewhere.
    assert any(h.startswith("A") for h in headings)
    assert any(h.startswith("B") for h in headings)
    assert any(h.startswith("C") for h in headings)
    assert all(len(c.text) <= 1000 for c in chunks)


def test_discover_docs_skips_oversized(tmp_path: Path) -> None:
    p = tmp_path / "huge.md"
    _write(p, "x" * (6 * 1024 * 1024))
    docs = discover_docs(tmp_path)
    assert all(d.relative_path != "huge.md" for d in docs)

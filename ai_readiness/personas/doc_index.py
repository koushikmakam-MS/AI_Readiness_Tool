"""Walk a repo for documentation files and chunk large docs by heading.

Read-only: never modifies the target repository.
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Iterable

from ai_readiness.personas.base import DocChunk, DocFile

logger = logging.getLogger(__name__)

# Default doc file patterns. Picked to match common AI-agent / human docs.
DEFAULT_DOC_GLOBS: tuple[str, ...] = (
    "*.md",
    "*.markdown",
    "*.mdx",
    "*.rst",
    "*.txt",
    "AGENTS.md",
    ".cursorrules",
    ".windsurfrules",
    ".github/copilot-instructions.md",
    ".github/instructions/*.md",
)

# Directories to skip even if they contain matching files.
DEFAULT_EXCLUDE_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        ".venv",
        "venv",
        "env",
        "__pycache__",
        ".tox",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "dist",
        "build",
        ".idea",
        ".vscode",
    }
)

# Heading regex for splitting markdown by H1/H2.
_HEADING_RE = re.compile(r"^(#{1,2})\s+(.+?)\s*$", re.MULTILINE)


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _slugify(text: str) -> str:
    slug = re.sub(r"[^\w\-]+", "-", text.strip().lower())
    return slug.strip("-")[:60] or "section"


def discover_docs(
    repo_path: Path,
    *,
    extra_globs: Iterable[str] = (),
    exclude_dirs: Iterable[str] = (),
    max_file_bytes: int = 5 * 1024 * 1024,  # skip files >5MB
) -> list[DocFile]:
    """Find all doc files under ``repo_path``.

    Files are loaded into memory and hashed for cache keying.
    """
    repo_path = repo_path.resolve()
    excluded = DEFAULT_EXCLUDE_DIRS | set(exclude_dirs)
    patterns = list(DEFAULT_DOC_GLOBS) + list(extra_globs)

    seen: set[Path] = set()
    docs: list[DocFile] = []

    for pattern in patterns:
        for path in repo_path.rglob(pattern):
            if not path.is_file() or path in seen:
                continue
            # Skip if any path part is in excluded dirs.
            try:
                rel_parts = path.relative_to(repo_path).parts
            except ValueError:
                continue
            if any(part in excluded for part in rel_parts[:-1]):
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size > max_file_bytes:
                logger.debug("Skipping oversized doc: %s (%d bytes)", path, size)
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            seen.add(path)
            rel = path.relative_to(repo_path).as_posix()
            docs.append(
                DocFile(
                    path=path,
                    relative_path=rel,
                    size_bytes=size,
                    content_hash=_hash_text(text),
                    text=text,
                    headings=[m.group(2) for m in _HEADING_RE.finditer(text)],
                )
            )

    docs.sort(key=lambda d: d.relative_path)
    return docs


def chunk_doc(doc: DocFile, *, max_chunk_chars: int = 8000) -> list[DocChunk]:
    """Split a doc into heading-bounded chunks.

    Small docs return a single chunk covering the whole file. Large docs
    (> ``max_chunk_chars``) are split at H1/H2 boundaries.
    """
    text = doc.text or ""
    if len(text) <= max_chunk_chars or not _HEADING_RE.search(text):
        return [
            DocChunk(
                doc=doc,
                chunk_id=doc.relative_path,
                heading=doc.relative_path,
                text=text,
                content_hash=doc.content_hash,
            )
        ]

    # Split on H1/H2 markers; preserve the heading line in each chunk.
    matches = list(_HEADING_RE.finditer(text))
    chunks: list[DocChunk] = []

    # Preamble before the first heading, if non-empty.
    first_start = matches[0].start()
    preamble = text[:first_start].strip()
    if preamble:
        chunks.append(
            DocChunk(
                doc=doc,
                chunk_id=f"{doc.relative_path}#preamble",
                heading="(preamble)",
                text=preamble,
                content_hash=_hash_text(preamble),
            )
        )

    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if not body:
            continue
        heading = m.group(2).strip()
        slug = _slugify(heading)
        chunks.append(
            DocChunk(
                doc=doc,
                chunk_id=f"{doc.relative_path}#{slug}",
                heading=heading,
                text=body,
                content_hash=_hash_text(body),
            )
        )

    # Hard cap any chunk that's still huge by simple character truncation.
    capped: list[DocChunk] = []
    for c in chunks:
        if len(c.text) <= max_chunk_chars:
            capped.append(c)
            continue
        # Split into sequential pieces.
        parts = [
            c.text[i : i + max_chunk_chars]
            for i in range(0, len(c.text), max_chunk_chars)
        ]
        for idx, part in enumerate(parts):
            capped.append(
                DocChunk(
                    doc=c.doc,
                    chunk_id=f"{c.chunk_id}~{idx}",
                    heading=f"{c.heading} (part {idx + 1})",
                    text=part,
                    content_hash=_hash_text(part),
                )
            )
    return capped


def chunk_docs(docs: list[DocFile], *, max_chunk_chars: int = 8000) -> list[DocChunk]:
    """Chunk every doc in ``docs``."""
    out: list[DocChunk] = []
    for d in docs:
        out.extend(chunk_doc(d, max_chunk_chars=max_chunk_chars))
    return out

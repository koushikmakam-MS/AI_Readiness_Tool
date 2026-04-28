"""Embedding-based relevance ranking for personas.

Computes (and caches) embeddings for every doc chunk, then ranks chunks
against each persona's "interests" query via cosine similarity.
"""

from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass
from typing import Optional

from ai_readiness.llm.client import LLMClient
from ai_readiness.personas.base import DocChunk, PersonaDefinition
from ai_readiness.personas.cache import PersonaCache
from ai_readiness.personas.throttle import AdaptiveThrottle

logger = logging.getLogger(__name__)

# Embeddings API hard limit per request for safety.
_EMBED_BATCH_SIZE = 64
# Truncate per-text input to keep batches well under provider token limits.
_EMBED_MAX_CHARS = 6000
# Default parallel embedding-batch fan-out.
_DEFAULT_EMBED_CONCURRENCY = 8


@dataclass
class RankedChunk:
    chunk: DocChunk
    score: float  # cosine similarity, -1..1


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _embed_text_for(chunk: DocChunk) -> str:
    """Build the input string used for embedding a chunk."""
    head = f"{chunk.doc.relative_path}\n# {chunk.heading}\n"
    body = chunk.text[: _EMBED_MAX_CHARS - len(head)]
    return head + body


class Embedder:
    """Computes & caches chunk embeddings; ranks them per persona."""

    def __init__(
        self,
        client: LLMClient,
        cache: Optional[PersonaCache] = None,
        *,
        concurrency: int = _DEFAULT_EMBED_CONCURRENCY,
        throttle: Optional[AdaptiveThrottle] = None,
    ) -> None:
        self.client = client
        self.cache = cache
        self.concurrency = max(1, concurrency)
        self.throttle = throttle or AdaptiveThrottle(
            initial_concurrency=self.concurrency
        )
        self.tokens_used = 0

    def embed_chunks(self, chunks: list[DocChunk]) -> dict[str, list[float]]:
        """Synchronous wrapper around :meth:`embed_chunks_async`."""
        return asyncio.run(self.embed_chunks_async(chunks))

    async def embed_chunks_async(
        self, chunks: list[DocChunk]
    ) -> dict[str, list[float]]:
        """Embed all chunks (cached + parallel batches)."""
        model = self.client.embedding_model
        out: dict[str, list[float]] = {}
        to_compute: list[DocChunk] = []

        for c in chunks:
            cached = (
                self.cache.get_embedding(model, c.content_hash) if self.cache else None
            )
            if cached is not None:
                out[c.chunk_id] = cached
            else:
                to_compute.append(c)

        if not to_compute:
            return out

        batches = [
            to_compute[i : i + _EMBED_BATCH_SIZE]
            for i in range(0, len(to_compute), _EMBED_BATCH_SIZE)
        ]
        logger.info(
            "Embedding %d new chunks in %d batches (concurrency=%d, %d cached)",
            len(to_compute),
            len(batches),
            self.concurrency,
            len(chunks) - len(to_compute),
        )

        sem = asyncio.Semaphore(self.concurrency)
        completed = 0

        async def run_batch(batch: list[DocChunk]) -> None:
            nonlocal completed
            texts = [_embed_text_for(c) for c in batch]
            async with sem:
                async with self.throttle:
                    try:
                        result = await asyncio.to_thread(self.client.embed, texts)
                    except Exception as exc:  # noqa: BLE001
                        msg = str(exc)
                        if "429" in msg or "RateLimit" in msg:
                            await self.throttle.record_429()
                            logger.warning(
                                "Embedding 429; throttle now %d concurrency",
                                self.throttle.concurrency,
                            )
                        else:
                            logger.warning(
                                "Embedding batch failed; skipping.", exc_info=True
                            )
                        return
                    await self.throttle.maybe_recover()
            self.tokens_used += result.prompt_tokens
            for c, vec in zip(batch, result.vectors):
                out[c.chunk_id] = vec
                if self.cache:
                    self.cache.put_embedding(model, c.content_hash, vec)
            completed += 1
            if completed % 5 == 0 or completed == len(batches):
                logger.info(
                    "Embedding progress: %d/%d batches", completed, len(batches)
                )

        await asyncio.gather(*(run_batch(b) for b in batches))
        return out

    def rank_for_persona(
        self,
        persona: PersonaDefinition,
        chunks: list[DocChunk],
        chunk_vectors: dict[str, list[float]],
        *,
        top_k: int,
    ) -> list[RankedChunk]:
        """Rank chunks by relevance to the persona's interests."""
        query = (
            f"Persona: {persona.display_name} ({persona.role})\n"
            f"Interests: {persona.interests}\n"
            f"Task: {persona.simulated_task}"
        )
        try:
            q_result = self.client.embed([query])
        except Exception:
            logger.warning("Query embedding failed for %s", persona.persona_id, exc_info=True)
            return []
        self.tokens_used += q_result.prompt_tokens
        if not q_result.vectors:
            return []
        q_vec = q_result.vectors[0]

        ranked: list[RankedChunk] = []
        for c in chunks:
            v = chunk_vectors.get(c.chunk_id)
            if v is None:
                continue
            ranked.append(RankedChunk(chunk=c, score=_cosine(q_vec, v)))

        ranked.sort(key=lambda r: r.score, reverse=True)
        return ranked[:top_k]

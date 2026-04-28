"""Orchestration: discover → embed → rank → score → simulated task → aggregate.

Async pipeline with configurable concurrency, hard cost cap, and caching.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ai_readiness.llm.client import CompletionResult, LLMClient
from ai_readiness.personas.base import (
    Dimension,
    DocChunk,
    PersonaDefinition,
    PersonaResult,
    RubricScore,
    SimulatedTaskResult,
)
from ai_readiness.personas.cache import PersonaCache
from ai_readiness.personas.doc_index import chunk_docs, discover_docs
from ai_readiness.personas.embedder import Embedder, RankedChunk
from ai_readiness.personas.registry import PersonaRegistry
from ai_readiness.personas.scorer import OverallReport, aggregate
from ai_readiness.personas.throttle import AdaptiveThrottle
from ai_readiness.personas.token_estimator import (
    DEFAULT_PRICES,
    estimate_cost,
)

logger = logging.getLogger(__name__)


class CostCapExceeded(Exception):
    """Raised when running another call would exceed the user's --max-cost."""


@dataclass
class RunOptions:
    persona_ids: Optional[list[str]] = None  # None = all enabled
    top_k: Optional[int] = None
    max_docs_per_persona: Optional[int] = None
    max_embed: Optional[int] = None  # cap chunks embedded (Azure quota relief)
    sample: Optional[int] = None  # random sample from shortlist
    max_cost_usd: Optional[float] = None
    concurrency: int = 5
    dry_run: bool = False
    simulated_tasks: Optional[bool] = None  # None = use registry default


@dataclass
class RunReport:
    overall: OverallReport
    persona_results: list[PersonaResult]
    docs_total: int
    chunks_total: int
    dry_run: bool = False
    aborted_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------

def _parse_rubric_json(raw: str) -> tuple[dict[str, float], str, list[str]]:
    """Parse persona rubric JSON. Returns (scores_dict, justification, suggestions)."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    text = text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}, "", []
    raw_scores = data.get("scores", {}) or {}
    scores: dict[str, float] = {}
    for k, v in raw_scores.items():
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        # Clamp to 1-5.
        scores[k] = max(1.0, min(5.0, f))
    return (
        scores,
        str(data.get("justification", "")),
        list(data.get("suggestions", []) or []),
    )


def _parse_task_json(raw: str) -> tuple[str, float, list[str]]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    try:
        data = json.loads(text.strip())
    except json.JSONDecodeError:
        return raw.strip(), 0.0, []
    answer = str(data.get("answer", ""))
    try:
        score = float(data.get("score", 0.0))
    except (TypeError, ValueError):
        score = 0.0
    score = max(0.0, min(10.0, score))
    missing = list(data.get("missing_info", []) or [])
    return answer, score, missing


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


class PersonaRunner:
    """Orchestrates the persona evaluation pipeline."""

    def __init__(
        self,
        registry: PersonaRegistry,
        client: LLMClient,
        cache: Optional[PersonaCache] = None,
        prices: Optional[dict[str, dict[str, float]]] = None,
    ) -> None:
        self.registry = registry
        self.client = client
        self.cache = cache
        self.prices = prices or registry.prices or DEFAULT_PRICES
        self._cost_so_far = 0.0
        self._cost_cap: Optional[float] = None
        self._chat_throttle: Optional[AdaptiveThrottle] = None

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    def run(self, repo_path: Path, options: RunOptions) -> RunReport:
        return asyncio.run(self.run_async(repo_path, options))

    async def run_async(self, repo_path: Path, options: RunOptions) -> RunReport:
        self._cost_so_far = 0.0
        self._cost_cap = options.max_cost_usd
        self._chat_throttle = AdaptiveThrottle(
            initial_concurrency=max(1, options.concurrency)
        )

        # 1) Discover + chunk
        docs = discover_docs(repo_path)
        chunks = chunk_docs(docs, max_chunk_chars=self.registry.max_chunk_chars)
        logger.info("Discovered %d docs / %d chunks", len(docs), len(chunks))

        # Optional pre-embed cap: prioritise short paths (READMEs, top-level
        # docs) which are usually the most agent-relevant.
        if options.max_embed is not None and len(chunks) > options.max_embed:
            chunks = sorted(
                chunks,
                key=lambda c: (c.doc.relative_path.count("/"), c.doc.relative_path),
            )[: options.max_embed]
            logger.info(
                "Capped chunks to embed at %d (max_embed)", options.max_embed
            )

        # 2) Pick personas
        personas = (
            self.registry.select(options.persona_ids)
            if options.persona_ids
            else self.registry.enabled()
        )
        if not personas:
            return RunReport(
                overall=aggregate([]),
                persona_results=[],
                docs_total=len(docs),
                chunks_total=len(chunks),
                dry_run=options.dry_run,
                aborted_reason="no personas selected",
            )

        # 3) Dry run: estimate without any LLM calls (except embeddings if cached)
        if options.dry_run:
            est_cost = self._estimate_dry_run_cost(chunks, personas, options)
            placeholder = OverallReport(
                overall_score=0.0,
                per_persona={p.persona_id: 0.0 for p in personas},
                per_dimension={d: 0.0 for d in Dimension},
                weights_used={p.persona_id: p.weight for p in personas},
                total_cost_usd=est_cost,
            )
            return RunReport(
                overall=placeholder,
                persona_results=[],
                docs_total=len(docs),
                chunks_total=len(chunks),
                dry_run=True,
            )

        if not self.client.is_available:
            return RunReport(
                overall=aggregate([]),
                persona_results=[],
                docs_total=len(docs),
                chunks_total=len(chunks),
                aborted_reason="LLM client not configured (missing API key)",
            )

        # 4) Embed all chunks (cached) + rank per persona
        embedder = Embedder(
            self.client,
            self.cache,
            concurrency=options.concurrency,
            throttle=self._chat_throttle,
        )
        chunk_vectors = await embedder.embed_chunks_async(chunks)
        embedding_tokens = embedder.tokens_used

        top_k = options.top_k or self.registry.top_k

        # 5) For each persona, score in parallel
        persona_results: list[PersonaResult] = []
        aborted_reason: Optional[str] = None
        run_simulated = (
            options.simulated_tasks
            if options.simulated_tasks is not None
            else self.registry.simulated_tasks_enabled
        )

        for persona in personas:
            try:
                ranked = embedder.rank_for_persona(
                    persona, chunks, chunk_vectors, top_k=top_k
                )
                shortlist = self._apply_caps(ranked, options)
                result = await self._score_persona(
                    persona,
                    shortlist,
                    concurrency=options.concurrency,
                    run_simulated_task=run_simulated,
                )
                # Embedding tokens are amortised across personas; attribute
                # them to the first persona for accounting simplicity.
                if persona is personas[0]:
                    result.embedding_tokens = embedder.tokens_used
                    result.estimated_cost_usd += estimate_cost(
                        chat_model=self.client.model,
                        embedding_model=self.client.embedding_model,
                        chat_prompt_tokens=0,
                        chat_completion_tokens=0,
                        embedding_tokens=embedder.tokens_used,
                        prices=self.prices,
                    )
                persona_results.append(result)
            except CostCapExceeded as e:
                aborted_reason = str(e)
                break

        embedding_tokens  # keep ref; total tracked on first persona

        overall = aggregate(
            persona_results,
            weights={p.persona_id: p.weight for p in personas},
        )
        return RunReport(
            overall=overall,
            persona_results=persona_results,
            docs_total=len(docs),
            chunks_total=len(chunks),
            aborted_reason=aborted_reason,
        )

    # ------------------------------------------------------------------
    # Per-persona pipeline
    # ------------------------------------------------------------------

    def _apply_caps(
        self,
        ranked: list[RankedChunk],
        options: RunOptions,
    ) -> list[RankedChunk]:
        out = list(ranked)
        if options.max_docs_per_persona is not None:
            out = out[: options.max_docs_per_persona]
        if options.sample is not None and options.sample > 0 and len(out) > options.sample:
            random.seed(42)
            out = random.sample(out, options.sample)
        return out

    async def _score_persona(
        self,
        persona: PersonaDefinition,
        shortlist: list[RankedChunk],
        *,
        concurrency: int,
        run_simulated_task: bool,
    ) -> PersonaResult:
        result = PersonaResult(
            persona_id=persona.persona_id,
            display_name=persona.display_name,
            docs_considered=len(shortlist),
        )
        if not shortlist:
            return result

        sem = asyncio.Semaphore(max(1, concurrency))

        async def score_one(rc: RankedChunk) -> Optional[RubricScore]:
            async with sem:
                return await self._rubric_for_chunk(persona, rc.chunk, result)

        tasks = [asyncio.create_task(score_one(rc)) for rc in shortlist]
        for t in asyncio.as_completed(tasks):
            try:
                rs = await t
            except CostCapExceeded:
                # Cancel remaining tasks and re-raise.
                for other in tasks:
                    if not other.done():
                        other.cancel()
                raise
            if rs is not None:
                result.rubric_scores.append(rs)

        result.docs_scored = len(result.rubric_scores)

        if run_simulated_task:
            try:
                task_res = await self._simulated_task(persona, shortlist, result)
                result.task_result = task_res
            except CostCapExceeded:
                raise

        return result

    async def _rubric_for_chunk(
        self,
        persona: PersonaDefinition,
        chunk: DocChunk,
        result: PersonaResult,
    ) -> Optional[RubricScore]:
        # Cache check.
        cached = (
            self.cache.get_score(
                persona.persona_id,
                self.registry.prompt_version,
                chunk.content_hash,
            )
            if self.cache
            else None
        )
        if cached is not None:
            return self._build_rubric_from_payload(chunk, cached)

        user_prompt = (
            f"## Doc path\n{chunk.doc.relative_path}\n\n"
            f"## Section\n{chunk.heading}\n\n"
            f"## Content\n{chunk.text}\n"
        )
        try:
            completion = await self._call_chat(
                persona.prompt_template,
                user_prompt,
            )
        except Exception:
            logger.warning(
                "Rubric call failed for %s / %s",
                persona.persona_id,
                chunk.chunk_id,
                exc_info=True,
            )
            return None

        self._track_cost(persona, result, completion)

        scores_raw, justification, suggestions = _parse_rubric_json(completion.text)
        if not scores_raw:
            return None
        scores = self._coerce_dimensions(scores_raw)
        if not scores:
            return None

        payload = {
            "scores": {k.value: v for k, v in scores.items()},
            "justification": justification,
            "suggestions": suggestions,
        }
        if self.cache:
            self.cache.put_score(
                persona.persona_id,
                self.registry.prompt_version,
                chunk.content_hash,
                payload,
            )

        return RubricScore(
            chunk_id=chunk.chunk_id,
            relative_path=chunk.doc.relative_path,
            scores=scores,
            justification=justification,
            suggestions=suggestions,
        )

    def _build_rubric_from_payload(
        self, chunk: DocChunk, payload: dict
    ) -> Optional[RubricScore]:
        scores_raw = payload.get("scores", {}) or {}
        scores = self._coerce_dimensions(
            {k: float(v) for k, v in scores_raw.items() if isinstance(v, (int, float))}
        )
        if not scores:
            return None
        return RubricScore(
            chunk_id=chunk.chunk_id,
            relative_path=chunk.doc.relative_path,
            scores=scores,
            justification=str(payload.get("justification", "")),
            suggestions=list(payload.get("suggestions", []) or []),
        )

    @staticmethod
    def _coerce_dimensions(raw: dict[str, float]) -> dict[Dimension, float]:
        out: dict[Dimension, float] = {}
        for dim in Dimension:
            if dim.value in raw:
                out[dim] = raw[dim.value]
        return out

    async def _simulated_task(
        self,
        persona: PersonaDefinition,
        shortlist: list[RankedChunk],
        result: PersonaResult,
    ) -> Optional[SimulatedTaskResult]:
        # Build a context bundle from top chunks (cap by char count).
        bundle: list[str] = []
        char_budget = 24000
        for rc in shortlist:
            piece = (
                f"### {rc.chunk.doc.relative_path} — {rc.chunk.heading}\n"
                f"{rc.chunk.text}\n"
            )
            if char_budget - len(piece) <= 0:
                break
            bundle.append(piece)
            char_budget -= len(piece)
        context = "\n".join(bundle) or "(no docs available)"

        system = (
            f"You are {persona.display_name} ({persona.role}). You are an AI "
            f"agent who must complete a task using ONLY the documentation "
            f"snippets provided. You have NO access to the source code.\n\n"
            "After answering, self-evaluate on a 0-10 scale how well the docs "
            "supported you (10 = perfect, 0 = useless), and list any missing "
            "information that would have helped.\n\n"
            "Return ONLY JSON with this shape:\n"
            '{"answer": "...", "score": 7, "missing_info": ["...", "..."]}'
        )
        user = f"## Task\n{persona.simulated_task}\n\n## Documentation\n{context}"
        try:
            completion = await self._call_chat(system, user)
        except Exception:
            logger.warning(
                "Simulated task failed for %s", persona.persona_id, exc_info=True
            )
            return None

        self._track_cost(persona, result, completion)
        answer, score, missing = _parse_task_json(completion.text)
        return SimulatedTaskResult(
            task=persona.simulated_task,
            answer=answer,
            score=score,
            missing_info=missing,
        )

    # ------------------------------------------------------------------
    # Cost tracking
    # ------------------------------------------------------------------

    async def _call_chat(
        self, system_prompt: str, user_prompt: str
    ) -> CompletionResult:
        """Invoke the chat client through the adaptive throttle."""
        throttle = self._chat_throttle
        if throttle is None:
            return await asyncio.to_thread(
                self.client.complete,
                system_prompt,
                user_prompt,
                temperature=0.0,
                json_mode=True,
            )
        async with throttle:
            try:
                completion = await asyncio.to_thread(
                    self.client.complete,
                    system_prompt,
                    user_prompt,
                    temperature=0.0,
                    json_mode=True,
                )
            except Exception as exc:
                msg = str(exc)
                if "429" in msg or "RateLimit" in msg:
                    await throttle.record_429()
                    logger.warning(
                        "Chat 429; throttle now %d concurrency",
                        throttle.concurrency,
                    )
                raise
            await throttle.maybe_recover()
            return completion

    def _track_cost(
        self,
        persona: PersonaDefinition,
        result: PersonaResult,
        completion: CompletionResult,
    ) -> None:
        result.prompt_tokens += completion.prompt_tokens
        result.completion_tokens += completion.completion_tokens
        cost = estimate_cost(
            chat_model=self.client.model,
            embedding_model=self.client.embedding_model,
            chat_prompt_tokens=completion.prompt_tokens,
            chat_completion_tokens=completion.completion_tokens,
            embedding_tokens=0,
            prices=self.prices,
        )
        result.estimated_cost_usd += cost
        self._cost_so_far += cost
        if self._cost_cap is not None and self._cost_so_far > self._cost_cap:
            raise CostCapExceeded(
                f"Cost cap ${self._cost_cap:.2f} exceeded "
                f"(spent ${self._cost_so_far:.2f}); aborting."
            )

    # ------------------------------------------------------------------
    # Dry-run estimation
    # ------------------------------------------------------------------

    def _estimate_dry_run_cost(
        self,
        chunks: list[DocChunk],
        personas: list[PersonaDefinition],
        options: RunOptions,
    ) -> float:
        """Rough up-front cost estimate (4 chars ≈ 1 token heuristic)."""
        # Embedding cost: every chunk once.
        embed_chars = sum(len(c.text) for c in chunks)
        embed_tokens = embed_chars // 4

        top_k = options.top_k or self.registry.top_k
        per_persona_chunks = min(len(chunks), top_k)
        if options.max_docs_per_persona is not None:
            per_persona_chunks = min(per_persona_chunks, options.max_docs_per_persona)
        if options.sample is not None:
            per_persona_chunks = min(per_persona_chunks, options.sample)

        avg_chunk_chars = (
            sum(len(c.text) for c in chunks) // len(chunks) if chunks else 0
        )
        avg_chunk_tokens = avg_chunk_chars // 4
        # Persona prompt + chunk + ~150 token JSON response.
        per_call_in = avg_chunk_tokens + 800
        per_call_out = 150
        total_chat_in = per_call_in * per_persona_chunks * len(personas)
        total_chat_out = per_call_out * per_persona_chunks * len(personas)

        # Add simulated-task budget per persona.
        if (
            options.simulated_tasks
            if options.simulated_tasks is not None
            else self.registry.simulated_tasks_enabled
        ):
            total_chat_in += 6000 * len(personas)
            total_chat_out += 400 * len(personas)

        return estimate_cost(
            chat_model=self.client.model,
            embedding_model=self.client.embedding_model,
            chat_prompt_tokens=total_chat_in,
            chat_completion_tokens=total_chat_out,
            embedding_tokens=embed_tokens,
            prices=self.prices,
        )

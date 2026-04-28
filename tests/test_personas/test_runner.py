"""End-to-end runner test with a fake LLMClient (no network)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai_readiness.llm.client import CompletionResult, EmbeddingResult
from ai_readiness.personas import load_persona_registry
from ai_readiness.personas.cache import PersonaCache
from ai_readiness.personas.runner import PersonaRunner, RunOptions


class _FakeClient:
    """Stand-in for LLMClient that returns deterministic content."""

    provider = "openai"
    model = "gpt-4o-mini"
    embedding_model = "text-embedding-3-small"
    is_available = True

    def __init__(self) -> None:
        self.chat_calls = 0
        self.embed_calls = 0

    def embed(self, texts: list[str]) -> EmbeddingResult:
        self.embed_calls += 1
        # 4-dim vector keyed off text length parity for variety.
        vectors = [
            [
                1.0 if len(t) % 2 == 0 else 0.0,
                float(min(len(t), 100)) / 100.0,
                0.5,
                0.25,
            ]
            for t in texts
        ]
        return EmbeddingResult(
            vectors=vectors,
            prompt_tokens=sum(len(t) // 4 for t in texts),
            model=self.embedding_model,
        )

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.0,
        json_mode: bool = False,
        model: str | None = None,
    ) -> CompletionResult:
        self.chat_calls += 1
        # If it looks like a simulated task (asks for "answer"), respond
        # with that schema. Otherwise return rubric.
        if '"answer"' in system_prompt:
            payload: dict[str, Any] = {
                "answer": "Per the docs, run `pip install` and `pytest`.",
                "score": 7.5,
                "missing_info": ["No deploy steps documented"],
            }
        else:
            payload = {
                "scores": {
                    "context_sufficiency": 4.0,
                    "ambiguity_risk": 3.5,
                    "token_efficiency": 4.5,
                },
                "justification": "Clear purpose; minor jargon.",
                "suggestions": ["Add a 1-line architecture diagram."],
            }
        return CompletionResult(
            text=json.dumps(payload),
            prompt_tokens=200,
            completion_tokens=80,
            model=self.model,
        )


def _seed_repo(tmp_path: Path) -> Path:
    (tmp_path / "README.md").write_text(
        "# MyTool\n\nDoes a thing.\n\n## Install\n\n`pip install mytool`\n",
        encoding="utf-8",
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text(
        "# Guide\n\nUse it like this.\n", encoding="utf-8"
    )
    return tmp_path


def test_runner_dry_run_skips_llm(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path)
    fake = _FakeClient()
    registry = load_persona_registry()
    cache = PersonaCache(repo, cache_root=tmp_path / "cache", enabled=False)
    runner = PersonaRunner(registry=registry, client=fake, cache=cache)

    report = runner.run(
        repo, RunOptions(persona_ids=["onboarding"], dry_run=True)
    )
    assert report.dry_run is True
    assert fake.chat_calls == 0
    assert fake.embed_calls == 0
    assert report.docs_total == 2
    assert report.overall.total_cost_usd > 0  # estimate is non-zero
    cache.close()


def test_runner_full_pipeline_with_fake_client(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path)
    fake = _FakeClient()
    registry = load_persona_registry()
    cache = PersonaCache(repo, cache_root=tmp_path / "cache", enabled=True)
    runner = PersonaRunner(registry=registry, client=fake, cache=cache)

    options = RunOptions(
        persona_ids=["onboarding"],
        top_k=5,
        concurrency=2,
        simulated_tasks=True,
    )
    report = runner.run(repo, options)

    assert len(report.persona_results) == 1
    pr = report.persona_results[0]
    assert pr.persona_id == "onboarding"
    assert pr.docs_scored >= 1
    assert pr.task_result is not None
    assert pr.task_result.score == 7.5
    # Rubric scores parsed correctly.
    first = pr.rubric_scores[0]
    assert 1.0 <= first.average <= 5.0
    assert any("architecture" in s for s in first.suggestions)
    cache.close()


def test_runner_uses_score_cache_on_second_run(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path)
    registry = load_persona_registry()
    cache = PersonaCache(repo, cache_root=tmp_path / "cache", enabled=True)

    fake1 = _FakeClient()
    runner1 = PersonaRunner(registry=registry, client=fake1, cache=cache)
    runner1.run(
        repo,
        RunOptions(persona_ids=["onboarding"], top_k=5, simulated_tasks=False),
    )
    first_chat_calls = fake1.chat_calls
    assert first_chat_calls > 0

    fake2 = _FakeClient()
    runner2 = PersonaRunner(registry=registry, client=fake2, cache=cache)
    runner2.run(
        repo,
        RunOptions(persona_ids=["onboarding"], top_k=5, simulated_tasks=False),
    )
    # All scores cached → no chat calls on the second run.
    assert fake2.chat_calls == 0
    cache.close()


def test_runner_aborts_on_cost_cap(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path)
    fake = _FakeClient()
    registry = load_persona_registry()
    cache = PersonaCache(repo, cache_root=tmp_path / "cache", enabled=False)
    runner = PersonaRunner(registry=registry, client=fake, cache=cache)

    # Tiny cap forces abort after first chat call.
    report = runner.run(
        repo,
        RunOptions(
            persona_ids=["onboarding"],
            top_k=5,
            concurrency=1,
            simulated_tasks=False,
            max_cost_usd=0.0000001,
        ),
    )
    assert report.aborted_reason is not None
    assert "cost cap" in report.aborted_reason.lower()
    cache.close()

"""Unit tests for ai_readiness.personas.scorer and token_estimator."""

from __future__ import annotations

from ai_readiness.personas.base import (
    Dimension,
    PersonaResult,
    RubricScore,
    SimulatedTaskResult,
)
from ai_readiness.personas.scorer import aggregate
from ai_readiness.personas.token_estimator import estimate_cost


def _result(persona_id: str, scores: list[float], task_score: float | None = None) -> PersonaResult:
    pr = PersonaResult(persona_id=persona_id, display_name=persona_id.title())
    for i, s in enumerate(scores):
        pr.rubric_scores.append(
            RubricScore(
                chunk_id=f"c{i}",
                relative_path=f"docs/{i}.md",
                scores={
                    Dimension.CONTEXT_SUFFICIENCY: s,
                    Dimension.AMBIGUITY_RISK: s,
                    Dimension.TOKEN_EFFICIENCY: s,
                },
            )
        )
    pr.docs_scored = len(scores)
    if task_score is not None:
        pr.task_result = SimulatedTaskResult(task="t", answer="a", score=task_score)
    return pr


def test_persona_overall_score_uses_rubric_only_when_no_task() -> None:
    pr = _result("dora", [5.0, 5.0])
    # Pure rubric: 5/5 = 100
    assert pr.overall_score == 100.0


def test_persona_overall_score_blends_task_and_rubric() -> None:
    pr = _result("dora", [3.0, 3.0], task_score=10.0)
    # rubric_100 = 60, task_100 = 100 → 60*0.7 + 100*0.3 = 72
    assert pr.overall_score == 72.0


def test_aggregate_weighted_average() -> None:
    a = _result("dora", [5.0])           # 100
    b = _result("sherlock", [3.0])       # 60
    overall = aggregate([a, b], weights={"dora": 1.0, "sherlock": 3.0})
    # (100*1 + 60*3) / 4 = 70
    assert overall.overall_score == 70.0
    assert overall.per_persona == {"dora": 100.0, "sherlock": 60.0}


def test_aggregate_default_simple_average() -> None:
    a = _result("dora", [4.0])           # 80
    b = _result("scooby", [2.0])         # 40
    overall = aggregate([a, b])
    assert overall.overall_score == 60.0


def test_estimate_cost_basic() -> None:
    cost = estimate_cost(
        chat_model="gpt-4o",
        embedding_model="text-embedding-3-small",
        chat_prompt_tokens=1_000_000,
        chat_completion_tokens=1_000_000,
        embedding_tokens=1_000_000,
    )
    # 2.50 + 10.00 + 0.02 = 12.52
    assert cost == 12.52

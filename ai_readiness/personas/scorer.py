"""Score aggregation: persona-level and overall doc-AI-readiness score."""

from __future__ import annotations

from dataclasses import dataclass, field

from ai_readiness.personas.base import Dimension, PersonaResult


@dataclass
class OverallReport:
    overall_score: float  # 0-100
    per_persona: dict[str, float] = field(default_factory=dict)
    per_dimension: dict[Dimension, float] = field(default_factory=dict)  # 1-5 scale
    weights_used: dict[str, float] = field(default_factory=dict)
    total_cost_usd: float = 0.0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_embedding_tokens: int = 0


def aggregate(
    results: list[PersonaResult],
    *,
    weights: dict[str, float] | None = None,
) -> OverallReport:
    """Aggregate per-persona results into an overall report."""
    weights = weights or {}
    per_persona = {r.persona_id: r.overall_score for r in results}

    # Weighted overall (default = simple average if no weights provided).
    if weights:
        total_w = sum(max(0.0, weights.get(r.persona_id, 1.0)) for r in results)
    else:
        total_w = float(len(results))

    if total_w <= 0:
        overall = 0.0
    else:
        weighted_sum = sum(
            r.overall_score * max(0.0, weights.get(r.persona_id, 1.0))
            for r in results
        )
        overall = weighted_sum / total_w

    # Per-dimension averages across all personas.
    per_dim: dict[Dimension, float] = {}
    for dim in Dimension:
        values: list[float] = []
        for r in results:
            avg = r.dimension_averages.get(dim, 0.0)
            if avg > 0:
                values.append(avg)
        per_dim[dim] = round(sum(values) / len(values), 2) if values else 0.0

    return OverallReport(
        overall_score=round(overall, 1),
        per_persona={k: round(v, 1) for k, v in per_persona.items()},
        per_dimension=per_dim,
        weights_used={r.persona_id: weights.get(r.persona_id, 1.0) for r in results},
        total_cost_usd=round(sum(r.estimated_cost_usd for r in results), 4),
        total_prompt_tokens=sum(r.prompt_tokens for r in results),
        total_completion_tokens=sum(r.completion_tokens for r in results),
        total_embedding_tokens=sum(r.embedding_tokens for r in results),
    )

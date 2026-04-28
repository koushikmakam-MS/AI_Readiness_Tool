"""Token usage and cost estimation for the personas pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field

# USD per 1M tokens. Conservative defaults; override via YAML.
DEFAULT_PRICES: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "text-embedding-3-small": {"input": 0.02, "output": 0.0},
    "text-embedding-3-large": {"input": 0.13, "output": 0.0},
}


@dataclass
class CostBreakdown:
    chat_prompt_tokens: int = 0
    chat_completion_tokens: int = 0
    embedding_tokens: int = 0
    cost_usd: float = 0.0
    by_persona: dict[str, float] = field(default_factory=dict)


def price_per_million(prices: dict[str, dict[str, float]], model: str) -> dict[str, float]:
    return prices.get(model, {"input": 0.0, "output": 0.0})


def estimate_cost(
    *,
    chat_model: str,
    embedding_model: str,
    chat_prompt_tokens: int,
    chat_completion_tokens: int,
    embedding_tokens: int,
    prices: dict[str, dict[str, float]] | None = None,
) -> float:
    """Return USD cost estimate for the given token usage."""
    p = prices or DEFAULT_PRICES
    chat_p = price_per_million(p, chat_model)
    emb_p = price_per_million(p, embedding_model)
    cost = (
        chat_prompt_tokens / 1_000_000 * chat_p["input"]
        + chat_completion_tokens / 1_000_000 * chat_p["output"]
        + embedding_tokens / 1_000_000 * emb_p["input"]
    )
    return round(cost, 4)

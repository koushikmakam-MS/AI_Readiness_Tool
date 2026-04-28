"""Tests for AdaptiveThrottle."""

from __future__ import annotations

import asyncio

from ai_readiness.personas.throttle import AdaptiveThrottle


def test_throttle_starts_at_initial() -> None:
    t = AdaptiveThrottle(initial_concurrency=4)
    assert t.concurrency == 4


def test_record_429_tightens_after_threshold() -> None:
    async def go() -> int:
        t = AdaptiveThrottle(
            initial_concurrency=8,
            threshold=3,
            cooldown_secs=0.0,
            window_secs=10.0,
            min_concurrency=1,
        )
        for _ in range(3):
            await t.record_429()
        return t.concurrency

    assert asyncio.run(go()) < 8


def test_below_threshold_keeps_concurrency() -> None:
    async def go() -> int:
        t = AdaptiveThrottle(
            initial_concurrency=8,
            threshold=5,
            cooldown_secs=0.0,
        )
        for _ in range(2):
            await t.record_429()
        return t.concurrency

    assert asyncio.run(go()) == 8


def test_throttle_acquire_release_works_as_context_manager() -> None:
    async def go() -> None:
        t = AdaptiveThrottle(initial_concurrency=2)
        async with t:
            async with t:
                pass

    asyncio.run(go())  # Should not deadlock or raise.

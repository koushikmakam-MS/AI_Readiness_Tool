"""Adaptive throttle: dynamically slow down when we see 429s.

Used to wrap embedding / chat calls so that a burst of rate-limit responses
shrinks the effective concurrency for a cool-down window, rather than just
hammering Azure with sync retries.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass


@dataclass
class _Window:
    hits: list[float]


class AdaptiveThrottle:
    """Concurrency limiter that shrinks under sustained 429 pressure.

    - Starts with ``initial_concurrency`` slots.
    - Each ``record_429()`` call narrows the active window.
    - If >``threshold`` 429s land in the rolling ``window_secs``, we sleep
      ``cooldown_secs`` before releasing more work and halve concurrency
      (down to ``min_concurrency``).
    - Concurrency slowly recovers (+1 every ``recover_secs`` of clean sailing).
    """

    def __init__(
        self,
        initial_concurrency: int = 4,
        *,
        min_concurrency: int = 1,
        max_concurrency: int = 16,
        window_secs: float = 30.0,
        threshold: int = 3,
        cooldown_secs: float = 5.0,
        recover_secs: float = 30.0,
    ) -> None:
        self._concurrency = max(min_concurrency, min(initial_concurrency, max_concurrency))
        self._min = min_concurrency
        self._max = max_concurrency
        self._window_secs = window_secs
        self._threshold = threshold
        self._cooldown_secs = cooldown_secs
        self._recover_secs = recover_secs

        self._sem = asyncio.Semaphore(self._concurrency)
        self._429s = _Window(hits=[])
        self._last_recover = time.monotonic()
        self._lock = asyncio.Lock()

    @property
    def concurrency(self) -> int:
        return self._concurrency

    async def acquire(self) -> None:
        await self._sem.acquire()

    def release(self) -> None:
        self._sem.release()

    async def __aenter__(self) -> "AdaptiveThrottle":
        await self.acquire()
        return self

    async def __aexit__(self, *exc: object) -> None:
        self.release()

    async def record_429(self) -> None:
        """Record a rate-limit response and possibly tighten concurrency."""
        now = time.monotonic()
        async with self._lock:
            self._429s.hits.append(now)
            cutoff = now - self._window_secs
            self._429s.hits = [t for t in self._429s.hits if t >= cutoff]
            if len(self._429s.hits) >= self._threshold and self._concurrency > self._min:
                await self._tighten()

    async def maybe_recover(self) -> None:
        """Loosen concurrency if we've had a clean recent window."""
        now = time.monotonic()
        async with self._lock:
            cutoff = now - self._window_secs
            self._429s.hits = [t for t in self._429s.hits if t >= cutoff]
            if (
                not self._429s.hits
                and now - self._last_recover >= self._recover_secs
                and self._concurrency < self._max
            ):
                self._concurrency += 1
                self._sem.release()
                self._last_recover = now

    async def _tighten(self) -> None:
        new = max(self._min, self._concurrency // 2)
        # Drain extra permits.
        for _ in range(self._concurrency - new):
            try:
                await asyncio.wait_for(self._sem.acquire(), timeout=0.001)
            except asyncio.TimeoutError:
                # Couldn't reclaim; that's fine, the semaphore will tighten
                # naturally as in-flight tasks release.
                break
        self._concurrency = new
        await asyncio.sleep(self._cooldown_secs)

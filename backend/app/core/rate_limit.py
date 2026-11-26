"""Async sliding-window rate limiter for outbound provider calls."""
from __future__ import annotations

import asyncio
import time
from collections import deque


class RateLimiter:
    def __init__(self, max_calls: int, period: float = 60.0, max_wait: float = 8.0):
        self.max_calls = max_calls
        self.period = period
        self.max_wait = max_wait
        self._calls: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        """Wait for a slot. Returns False if waiting would exceed ``max_wait``."""
        async with self._lock:
            now = time.monotonic()
            while self._calls and now - self._calls[0] >= self.period:
                self._calls.popleft()
            if len(self._calls) >= self.max_calls:
                wait = self.period - (now - self._calls[0])
                if wait > self.max_wait:
                    return False
                await asyncio.sleep(wait)
                now = time.monotonic()
                while self._calls and now - self._calls[0] >= self.period:
                    self._calls.popleft()
            self._calls.append(time.monotonic())
            return True

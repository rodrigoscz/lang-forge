from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable


class AsyncRateLimiter:
    """Async sliding-window rate limiter for outbound API calls."""

    def __init__(
        self,
        requests_per_second: int = 5,
        *,
        clock: Callable[[], float] | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        if requests_per_second < 1:
            raise ValueError("requests_per_second must be at least 1")
        self.requests_per_second = requests_per_second
        self._clock = clock or time.monotonic
        self._sleep = sleep or asyncio.sleep
        self._lock = asyncio.Lock()
        self._dispatch_times: list[float] = []

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = self._clock()
                window_start = now - 1.0
                self._dispatch_times = [timestamp for timestamp in self._dispatch_times if timestamp > window_start]

                if len(self._dispatch_times) < self.requests_per_second:
                    self._dispatch_times.append(now)
                    return

                wait_for = max(0.0, 1.0 - (now - self._dispatch_times[0]))
                await self._sleep(wait_for)

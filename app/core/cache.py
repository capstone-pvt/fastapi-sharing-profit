"""Tiny in-memory TTL cache used to shave Atlas round-trips off hot paths.

Motivation: each round-trip to Atlas from our edge is ~300ms, so caching
auth/role lookups for a handful of seconds cuts observed latency by 3-5x.
"""

from __future__ import annotations

import time
from typing import Any, Awaitable, Callable, Hashable


class AsyncTtlCache:
    def __init__(self, ttl_seconds: float) -> None:
        self._ttl = ttl_seconds
        self._store: dict[Hashable, tuple[float, Any]] = {}

    async def get_or_set(
        self,
        key: Hashable,
        factory: Callable[[], Awaitable[Any]],
    ) -> Any:
        now = time.monotonic()
        hit = self._store.get(key)
        if hit is not None and (now - hit[0]) < self._ttl:
            return hit[1]
        value = await factory()
        self._store[key] = (now, value)
        return value

    def invalidate(self, key: Hashable) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

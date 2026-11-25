"""A small in-memory cache with a time limit (TTL), a size limit (LRU) and a hit-ratio counter.

Stands in for Redis so the lab runs with no server. The clock is passed in, so tests
can move time forward without sleeping.
"""
from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable, Hashable

_MISSING = object()


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expirations: int = 0

    @property
    def requests(self) -> int:
        return self.hits + self.misses

    @property
    def hit_ratio(self) -> float:
        """Share of reads answered from the cache. 0.0 before any read (no divide-by-zero)."""
        return self.hits / self.requests if self.requests else 0.0


class TTLCache:
    def __init__(
        self,
        ttl_seconds: float,
        max_entries: int = 1000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        if max_entries < 1:
            raise ValueError("max_entries must be at least 1")
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self._clock = clock
        self._data: "OrderedDict[Hashable, tuple[float, Any]]" = OrderedDict()
        self.stats = CacheStats()

    def get(self, key: Hashable) -> Any:
        """Return the cached value, or the module sentinel _MISSING. Counts a hit or a miss."""
        entry = self._data.get(key)
        if entry is not None:
            expires_at, value = entry
            if self._clock() < expires_at:
                self._data.move_to_end(key)  # recently used
                self.stats.hits += 1
                return value
            del self._data[key]
            self.stats.expirations += 1
        self.stats.misses += 1
        return _MISSING

    def set(self, key: Hashable, value: Any) -> None:
        self._data[key] = (self._clock() + self.ttl, value)
        self._data.move_to_end(key)
        while len(self._data) > self.max_entries:
            self._data.popitem(last=False)  # least recently used
            self.stats.evictions += 1

    def delete(self, key: Hashable) -> None:
        self._data.pop(key, None)

    def __len__(self) -> int:
        return len(self._data)


def is_missing(value: Any) -> bool:
    return value is _MISSING

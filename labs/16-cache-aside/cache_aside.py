"""Cache-aside (lazy loading): the app checks the cache, and only on a miss reads the
database and fills the cache. Writes go to the database first, then delete the cached copy.
"""
from __future__ import annotations

from typing import Any, Callable, Hashable

from cache import TTLCache, is_missing


class FakeDB:
    """A products table that counts every query, so the tests can prove the cache saved them."""

    QUERY_MS = 40  # assumed cost of one database round trip, used only for the estimate

    def __init__(self, prices: dict[str, int]) -> None:
        self._prices = dict(prices)
        self.reads = 0
        self.writes = 0

    def get_price(self, product_id: str) -> int | None:
        self.reads += 1
        return self._prices.get(product_id)

    def set_price(self, product_id: str, price: int) -> None:
        self.writes += 1
        self._prices[product_id] = price


class ProductService:
    def __init__(self, db: FakeDB, cache: TTLCache, invalidate_on_write: bool = True) -> None:
        self.db = db
        self.cache = cache
        self.invalidate_on_write = invalidate_on_write

    def get_price(self, product_id: str) -> int | None:
        return get_or_load(self.cache, f"price:{product_id}", lambda: self.db.get_price(product_id))

    def update_price(self, product_id: str, price: int) -> None:
        self.db.set_price(product_id, price)  # 1. the database is the source of truth
        if self.invalidate_on_write:
            self.cache.delete(f"price:{product_id}")  # 2. drop the copy; next read reloads it


def get_or_load(cache: TTLCache, key: Hashable, loader: Callable[[], Any]) -> Any:
    value = cache.get(key)
    if not is_missing(value):
        return value
    value = loader()  # if this raises, nothing is cached and the error reaches the caller
    cache.set(key, value)  # None is cached too, so a missing product does not hit the DB every time
    return value

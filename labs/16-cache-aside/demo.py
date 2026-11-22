"""Run a skewed read workload with and without a cache and print the numbers in the README."""
from __future__ import annotations

import random

from cache import TTLCache
from cache_aside import FakeDB, ProductService

PRODUCTS = 200
READS = 5_000
SEED = 42


def make_prices() -> dict[str, int]:
    return {f"p{i}": 100 + i for i in range(PRODUCTS)}


def skewed_keys(n: int, seed: int = SEED) -> list[str]:
    """A few products are much more popular than the rest (Zipf-like), as in real shops."""
    rng = random.Random(seed)
    ids = [f"p{i}" for i in range(PRODUCTS)]
    weights = [1 / (rank + 1) for rank in range(PRODUCTS)]
    return rng.choices(ids, weights=weights, k=n)


class StepClock:
    """Fake clock: each read moves time forward by a fixed step."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def run(ttl_seconds: float = 60.0, max_entries: int = 1000, seconds_per_read: float = 0.1) -> dict:
    clock = StepClock()
    db = FakeDB(make_prices())
    service = ProductService(db, TTLCache(ttl_seconds, max_entries, clock=clock))
    for key in skewed_keys(READS):
        service.get_price(key)
        clock.now += seconds_per_read
    stats = service.cache.stats
    return {
        "reads": READS,
        "hits": stats.hits,
        "misses": stats.misses,
        "hit_ratio": stats.hit_ratio,
        "db_reads": db.reads,
        "db_ms_saved": (READS - db.reads) * FakeDB.QUERY_MS,
    }


def stale_read_demo(invalidate: bool) -> tuple[int, int]:
    """Read a price, change it, read again. Returns (price before, price seen after the update)."""
    clock = StepClock()
    db = FakeDB(make_prices())
    service = ProductService(db, TTLCache(60, clock=clock), invalidate_on_write=invalidate)
    before = service.get_price("p0")
    service.update_price("p0", 999)
    clock.now += 5  # well inside the 60 s TTL
    return before, service.get_price("p0")


if __name__ == "__main__":
    print(f"{READS} reads over {PRODUCTS} products, a few far more popular than the rest\n")
    print("| Setup | Hit ratio | DB reads | DB time saved (at 40 ms each) |")
    print("| --- | --- | --- | --- |")
    print(f"| No cache | 0% | {READS:,} | 0 s |")
    for label, kwargs in [
        ("Cache, TTL 60 s, room for all 200", {}),
        ("Cache, TTL 60 s, room for 20", {"max_entries": 20}),
        ("Cache, TTL 5 s, room for all 200", {"ttl_seconds": 5}),
    ]:
        r = run(**kwargs)
        print(f"| {label} | {r['hit_ratio']:.1%} | {r['db_reads']:,} | {r['db_ms_saved'] / 1000:.0f} s |")
    print()
    for invalidate in (False, True):
        before, after = stale_read_demo(invalidate)
        print(f"Price update 100 -> 999, invalidate_on_write={invalidate}: read after update returns {after}")

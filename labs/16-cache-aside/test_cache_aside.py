import pytest

import demo
from cache import TTLCache
from cache_aside import FakeDB, ProductService, get_or_load


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def make_service(invalidate=True, ttl=60, clock=None):
    db = FakeDB({"p1": 100})
    return ProductService(db, TTLCache(ttl, clock=clock or Clock()), invalidate_on_write=invalidate), db


def test_repeated_reads_hit_the_database_once():
    service, db = make_service()
    assert [service.get_price("p1") for _ in range(10)] == [100] * 10
    assert db.reads == 1
    assert service.cache.stats.hit_ratio == 0.9


def test_missing_product_is_cached_so_the_db_is_not_hammered():
    service, db = make_service()
    for _ in range(5):
        assert service.get_price("nope") is None
    assert db.reads == 1


def test_write_then_invalidate_gives_the_new_price_at_once():
    service, db = make_service(invalidate=True)
    service.get_price("p1")
    service.update_price("p1", 999)
    assert service.get_price("p1") == 999
    assert db.reads == 2


def test_without_invalidation_the_old_price_is_served_until_ttl():
    clock = Clock()
    service, _ = make_service(invalidate=False, ttl=60, clock=clock)
    service.get_price("p1")
    service.update_price("p1", 999)
    clock.now = 59
    assert service.get_price("p1") == 100  # stale
    clock.now = 60
    assert service.get_price("p1") == 999  # TTL is the safety net


def test_loader_error_is_not_cached():
    cache = TTLCache(60, clock=Clock())
    calls = []

    def broken():
        calls.append(1)
        raise ConnectionError("db down")

    for _ in range(2):
        with pytest.raises(ConnectionError):
            get_or_load(cache, "k", broken)
    assert len(calls) == 2
    assert len(cache) == 0


def test_skewed_workload_hit_ratio_and_db_reads_match():
    r = demo.run()
    assert r["hit_ratio"] >= 0.80
    assert r["db_reads"] == r["misses"]  # every miss is exactly one DB read
    assert r["hits"] + r["misses"] == r["reads"]


def test_smaller_cache_or_shorter_ttl_lowers_hit_ratio():
    full = demo.run()["hit_ratio"]
    assert demo.run(max_entries=20)["hit_ratio"] < full
    assert demo.run(ttl_seconds=5)["hit_ratio"] < full


def test_demo_stale_read():
    assert demo.stale_read_demo(invalidate=False) == (100, 100)
    assert demo.stale_read_demo(invalidate=True) == (100, 999)

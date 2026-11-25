import pytest

from cache import TTLCache, is_missing


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_hit_ratio_is_zero_before_any_read():
    assert TTLCache(10).stats.hit_ratio == 0.0


def test_first_read_misses_then_hits():
    cache = TTLCache(10, clock=Clock())
    assert is_missing(cache.get("a"))
    cache.set("a", 1)
    assert cache.get("a") == 1
    assert (cache.stats.hits, cache.stats.misses) == (1, 1)
    assert cache.stats.hit_ratio == 0.5


def test_entry_expires_after_ttl_and_counts_as_miss():
    clock = Clock()
    cache = TTLCache(10, clock=clock)
    cache.set("a", 1)
    clock.now = 9.9
    assert cache.get("a") == 1
    clock.now = 10.0
    assert is_missing(cache.get("a"))
    assert cache.stats.expirations == 1
    assert len(cache) == 0


def test_least_recently_used_entry_is_evicted_when_full():
    cache = TTLCache(10, max_entries=2, clock=Clock())
    cache.set("a", 1)
    cache.set("b", 2)
    cache.get("a")  # a is now more recent than b
    cache.set("c", 3)
    assert cache.get("a") == 1
    assert is_missing(cache.get("b"))
    assert cache.stats.evictions == 1


def test_none_is_a_real_cached_value():
    cache = TTLCache(10, clock=Clock())
    cache.set("gone", None)
    assert cache.get("gone") is None
    assert cache.stats.hits == 1


@pytest.mark.parametrize("ttl, size", [(0, 10), (-1, 10), (10, 0)])
def test_bad_settings_are_refused(ttl, size):
    with pytest.raises(ValueError):
        TTLCache(ttl, max_entries=size)

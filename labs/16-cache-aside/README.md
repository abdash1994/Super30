# Lab 16: cache-aside with a hit-ratio counter

**Result:** on 5,000 reads over 200 products (a few far more popular than the rest), a 60-second cache answers 81.2% of reads and cuts database reads from 5,000 to 939; shrink the cache to 20 slots or the TTL to 5 seconds and the hit ratio drops to about 47%; and without deleting the cached copy on a price change, the old price is served until the TTL runs out.

## The problem

A product page reads the same few prices thousands of times a minute. Every read going to the database makes the page slow and the database bill big, and most of those reads return exactly what the last one did. A cache keeps a copy close to the app. The questions a client will ask are: how much does it actually save, and can a customer ever see the wrong price?

## What this lab does

**Cache-aside** (also called lazy loading) is the most common pattern:

1. **Read:** look in the cache. If it is there (a *hit*), return it. If not (a *miss*), read the database, put the answer in the cache, return it.
2. **Write:** update the database first, then **delete** the cached copy, so the next read loads the new value.
3. **TTL** (time to live): every cached copy expires after a set time, as a safety net if a delete is ever missed.

**Hit ratio** = hits / (hits + misses). It is the one number that says whether a cache is earning its keep.

| File | Job |
| --- | --- |
| `cache.py` | In-memory cache with TTL, a size limit (least recently used entry goes first) and hit/miss/eviction/expiry counters. Stands in for Redis. |
| `cache_aside.py` | `get_or_load` (the read path), a `FakeDB` that counts queries, and `ProductService` with write-then-delete. |
| `demo.py` | Runs the skewed workload with different cache settings and the stale-price check. |
| `test_cache.py`, `test_cache_aside.py` | 16 tests: hit/miss counting, TTL expiry, LRU eviction, cached "not found", errors not cached, invalidation, stale reads until TTL, and the workload hit ratio (at least 80%, checked in CI). |

`python demo.py` output (fixed random seed, so the same every run):

| Setup | Hit ratio | DB reads | DB time saved (at 40 ms each) |
| --- | --- | --- | --- |
| No cache | 0% | 5,000 | 0 s |
| Cache, TTL 60 s, room for all 200 | 81.2% | 939 | 162 s |
| Cache, TTL 60 s, room for 20 | 46.9% | 2,655 | 94 s |
| Cache, TTL 5 s, room for all 200 | 46.5% | 2,673 | 93 s |

Price changed from 100 to 999, read again 5 seconds later: **100** without invalidation (stale), **999** with it.

The 40 ms per query is an assumption for the estimate, not a measurement. Time is a fake clock (each read moves it 0.1 s), so the tests never sleep and never flake.

## Run it

```bash
pip install -r requirements.txt
pytest -q          # 16 tests, standard library only, no Redis needed
python demo.py     # prints the table above
```

With real Redis the read path is the same three steps: `GET price:p1`, on a miss query the database and `SET price:p1 <value> EX 60`; on a write, update the database then `DEL price:p1`. Redis's `INFO stats` reports `keyspace_hits` and `keyspace_misses`, which give the same hit ratio.

## Why it matters to a business

A cache is often the cheapest way to make a slow client app fast without a bigger database: here 4 of every 5 reads never touch it. The hit ratio turns "add caching" into a number a client can track on a dashboard and set an alert on (a sudden drop usually means a deploy changed the cache keys). And the stale-price test is the conversation to have before switching it on: which data can be a minute old (product descriptions, a leaderboard) and which must never be (stock levels at checkout, account balances).

## Trade-off

Speed is paid for with freshness. A longer TTL and a bigger cache raise the hit ratio but use more memory and widen the window for stale data if an invalidation is missed (another server, a bulk import straight into the database). Deleting on write keeps data correct, but there is still a small race: a read that started before the write can put the old value back, which is why the TTL stays as a backstop. Cache-aside also means the first read of every key is slow, and when a very popular key expires, many requests can miss at once and all hit the database (a "stampede"); real systems add a lock or a little random jitter to the TTL. Finally, the cache is per process here; with several app servers you need a shared cache like Redis, which is one more service to run and monitor.

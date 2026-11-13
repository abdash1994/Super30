# Lab 08: three HTTP calls, one after another vs all at once

**Result:** the same three 300 ms service calls take about 900 ms one after another and about 300 ms with `asyncio.gather`, a 3x cut in wait time, with the same answers in the same order and one failing service recorded as an error instead of sinking the other two.

## The problem

An AI assistant rarely answers from one source. "Why was this customer charged twice?" needs the CRM record, the billing history and the open tickets before the model can say anything useful. Written the obvious way, the code asks the CRM, waits, asks billing, waits, asks the ticket system, waits. The user stares at a spinner for the **sum** of all three waits, even though none of the calls depends on another.

Two quieter problems come with the fix: if you run the calls together carelessly, one service that times out can throw away the two answers that did arrive, and the results can come back in a different order than the code expects.

## What this lab does

```
sequential:  CRM ======|
                       billing ======|
                                     tickets ======|      ~ 900 ms (sum)

concurrent:  CRM ======|
             billing ======|
             tickets ======|                              ~ 300 ms (slowest one)
```

| File | Job |
| --- | --- |
| `fetch.py` | `fetch_sequential` (plain `httpx.Client`) and `fetch_concurrent` (`httpx.AsyncClient` + `asyncio.gather`). Both time every call, keep the input order, apply a per-call timeout, and turn timeouts, refused connections and 4xx/5xx into a `CallResult` with an `error` instead of an exception. |
| `fake_services.py` | Three fake services (CRM, billing, tickets) that each take 300 ms, built on `httpx.MockTransport`, so the lab and CI need no network. `down.example` always returns 503. |
| `compare.py` | Runs both modes and prints a timing table. `--live` points it at real URLs. |
| `test_fetch.py` | 9 tests: sequential is about the sum, concurrent is about the slowest single call, at least 2x faster, same results and order, a 503 and a timeout are isolated. |

CI writes the measured table to the run's **Summary** page ("Lab 08 timings"). On this machine:

| Mode | Total | Calls OK |
| --- | --- | --- |
| sequential | 902 ms | 3/3 |
| concurrent | 301 ms | 3/3 |

## Run it

```bash
pip install -r requirements.txt
pytest -q                 # 9 tests, no network

python compare.py         # offline timing table
python compare.py --live https://httpbin.org/delay/1 https://httpbin.org/delay/1 https://httpbin.org/delay/1
```

## Why it matters to a business

Latency is a product feature. Every agent that gathers context from several systems pays this tax on every question, and the fix is a handful of lines. Cutting a 900 ms wait to 300 ms is the difference between "it feels instant" and "is it broken?", and it frees up room in the latency budget for the slow part that actually matters, the model call. Isolating failures matters just as much: when billing is down, the assistant can still say "here is the customer and their open tickets, billing is not responding" instead of a blank error page.

## Trade-off

Concurrency only helps when the calls are independent and the time is spent waiting on the network; if call two needs the answer from call one, or the work is CPU-heavy, `gather` buys nothing. Firing everything at once also hits the downstream services harder: three calls is fine, three hundred needs a limit (an `asyncio.Semaphore`) or you become the reason their rate limiter trips. Async code is also harder to read and debug than a plain loop, so it is worth it on hot paths, not everywhere. And the fake services give clean, repeatable numbers; real networks add jitter, so the real gain is "close to the slowest call", not exactly 3x.

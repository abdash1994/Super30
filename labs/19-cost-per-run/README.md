# Lab 19: an automation that logs cost per run

**Result:** a ticket-triage automation logs every model call to a JSONL file and writes one cost line per run: 20 tickets cost $0.0368 ($0.00184 per ticket), drafting replies is 99% of the spend, moving replies to the small model makes the run about 11x cheaper, and a $0.25 budget stops a 200-ticket run after 135 tickets instead of spending $0.37.

## The problem

An AI automation that runs every night has no one watching it. The invoice arrives at the end of the month as one number, with no way to tell which run, which step or which model made it big. A client will ask three things: what does one run cost, what does one item (a ticket, a document) cost, and what stops a bad night (a flood of tickets, a loop) from burning the month's budget?

## What this lab does

| File | Job |
| --- | --- |
| `cost_log.py` | `call_cost` (tokens x price per 1M, in `Decimal`), `RunLogger` (one per run: logs each call, keeps a running total, stops the run when it goes over budget, always writes a final run line), `summarise` and a small report CLI. |
| `automation.py` | The automation: classify each ticket with the cheap model, draft a reply with the large model only if it is not spam. `FakeLLM` stands in for the API (about 4 characters per token), so no key or network is needed. |
| `demo.py` | Runs four scenarios and prints the table below. |
| `test_cost_log.py` | 11 tests: hand-checked cost, no float drift, unknown model refused (never logged as free), every call logged, run total equals the sum of its calls, budget stop overshoots by at most one call, API errors still raise and are marked `failed`, per-step summary, report CLI. |

Each log line is one JSON object:

```json
{"type": "call", "run_id": "quiet", "step": "reply", "model": "large", "input_tokens": 59, "output_tokens": 150, "cost_usd": "0.002427", ...}
{"type": "run", "run_id": "quiet", "status": "ok", "calls": 35, "items": 20, "cost_usd": "0.03677250", "cost_per_item_usd": "0.001839", ...}
```

`python demo.py` output:

| Run | Status | Tickets done | Calls | Cost | Cost per ticket |
| --- | --- | --- | --- | --- | --- |
| quiet day, 20 tickets | ok | 20 | 35 | $0.0368 | $0.00184 |
| busy day, 200 tickets | ok | 200 | 350 | $0.3677 | $0.00184 |
| busy day, $0.25 budget | stopped_budget | 135 | 238 | $0.2501 | $0.00185 |
| 20 tickets, replies on small | ok | 20 | 35 | $0.0034 | $0.00017 |

Across all four runs, `reply` is 99% of spend and `classify` is 1%.

Prices are example numbers (small: $0.25 in / $1.25 out, large: $3 / $15 per 1M tokens), not quotes. Pass your provider's current prices as the price table.

## Run it

```bash
pip install -r requirements.txt
pytest -q                     # 11 tests, standard library only
python demo.py                # prints the table above
```

To report on your own log: `python cost_log.py runs.jsonl`. With a real API, pass `response.usage.input_tokens` and `response.usage.output_tokens` (the names most SDKs use) to `logger.record(step, model, usage)`.

## Why it matters to a business

Cost per run and cost per item turn "the AI bill went up" into "Tuesday's run handled 3x the tickets" or "the reply step got more expensive after the prompt change". Cost per item is the number to put next to the price the client charges or the minutes a human used to spend, which is how an automation gets kept or cut. The per-step split shows where to optimise: here, classification is almost free, so the savings are all in the reply step (a cheaper model, a shorter prompt, or not replying to some ticket types). The budget cap is the promise a client needs before letting anything run unattended.

## Trade-off

The budget is checked after each call, not before, because the real token count is only known once the call returns. So a run can go over budget by at most one call (here $0.00005). A stricter cap would estimate the next call first and refuse it, at the cost of sometimes stopping early when the estimate is too high. The log is a local file, which is simple and fine for one machine; several workers writing at once, or a dashboard across clients, would need a database table or the provider's usage API. Prices live in a table you have to keep up to date: a stale price gives a confident wrong number, which is why an unknown model is an error, not a silent $0.

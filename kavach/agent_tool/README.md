# KAVACH agent tool

**Result: an AI agent can ask KAVACH to score a payment, and when KAVACH is slow or down the agent gets a clear, structured error it can act on instead of crashing (17 tests, API and LLM mocked, CI-checked).**

## The problem

An agent that approves payments needs KAVACH's fraud score. A plain HTTP call inside an agent tool has three ways to go wrong:

1. **It hangs.** No timeout means one slow response freezes the whole agent run.
2. **It gives up too early, or retries the wrong things.** A brief 503 should be retried. A 422 (bad amount) never will succeed, so retrying it only wastes time.
3. **It raises.** An exception inside a tool usually ends the agent run. The agent never gets the chance to say "scoring is down, hold the payment".

## What this does

`kavach_tool.py` wraps `POST /v1/score` as a tool called `score_transaction`:

| Situation | What the tool does | What the agent gets |
| --- | --- | --- |
| 200 with JSON | Returns the score | `{"ok": true, "attempts": 1, "data": {...}}` |
| Timeout, connection error | Retries with backoff (0.5 s, 1 s, capped at 4 s) | `code: "timeout"` or `"unreachable"`, `retryable: true` |
| 429, 500, 502, 503, 504 | Retries, honouring `Retry-After` up to the cap | `code: "upstream_unavailable"`, `retryable: true` |
| 400, 422 | No retry | `code: "invalid_request"` with KAVACH's field-level reasons in `details` |
| 401, 403, other 4xx | No retry | `code: "rejected"` |
| 200 that is not JSON | No retry | `code: "bad_response"` |

Every attempt has a 2-second timeout (configurable) and sends the same `Idempotency-Key` (the transaction ID), so a retry after a lost response cannot score and audit-log the same payment twice.

`agent.py` is a minimal agent loop: the LLM asks for a tool, the loop runs it and feeds the result back. Any object with a `respond(messages, tools)` method can be the LLM, so tests use a scripted fake.

## How to run it

```bash
cd kavach/agent_tool
pip install -r requirements.txt
pytest
```

## Why it matters to a business

A fraud check that fails loudly and clearly is safe: the agent can hold the payment or send it to manual review. A check that hangs blocks checkout, and a check that crashes the agent loses the decision altogether. The structured error turns an outage into a business rule ("retryable, so queue it") instead of an incident.

## Trade-off

Retries make one slow call slower. With 3 attempts and a 2 s timeout, the worst case is about 7.5 s (3 x 2 s plus 0.5 s and 1 s of backoff) before the agent hears "timeout". For a checkout that is long, so a real deployment would tune `timeout_s` and `max_attempts` to the checkout's time budget. Retrying a 500 is also a judgement call: it helps with blips, but if the 500 is a real bug, it just repeats the failure twice more.

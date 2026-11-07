# Lab 04: status-code demo API

**Result:** a small orders API where each of the nine common HTTP status codes (200, 201, 400, 401, 403, 404, 409, 422, 500) has exactly one job, proven by one test per code and a curl script that checks all nine against the running server.

## The problem

When an integration breaks at a client, the first clue is the status code. If an API answers "500" for a missing record, or "200" with `{"error": ...}` inside, the client's engineers cannot tell whose problem it is: their request, their permissions, their data, or our bug. Tickets bounce between teams for days. Getting status codes right is the cheapest way to make an API self-explaining.

## What this lab does

`app.py` is a FastAPI service with one resource, orders, kept in memory. Two demo tokens: `viewer-token` can read, `admin-token` can read and create.

| Code | Meaning | How to trigger it here |
| --- | --- | --- |
| 200 OK | Here is what you asked for | `GET /orders/ord-001` with any valid token |
| 201 Created | I made it; it lives at the `Location` header | `POST /orders` with the admin token |
| 400 Bad Request | I can't even read your request | `POST /orders` with broken JSON |
| 401 Unauthorized | I don't know who you are | No token, or an unknown token |
| 403 Forbidden | I know who you are, and you can't do this | Viewer token tries to `POST /orders` |
| 404 Not Found | That thing doesn't exist | `GET /orders/ord-404` |
| 409 Conflict | That clashes with what already exists | `POST /orders` with an id that is taken |
| 422 Unprocessable Content | I read it, but it breaks the rules | `quantity: 0`, or a missing field |
| 500 Internal Server Error | Our bug, not yours | `GET /simulate/crash` |

Three details that matter in real work:

- **One error shape everywhere:** `{"error": {"status": 409, "code": "order_exists", "message": "..."}}`. A client writes one error handler, not nine. The `code` is stable for machines; the `message` is for humans.
- **400 vs 422:** FastAPI answers 422 for both broken JSON and rule-breaking JSON. This lab splits them, so 400 means "fix your client's serialiser" and 422 lists exactly which fields failed.
- **500 never leaks internals:** the response says "something went wrong on our side", never the stack trace or the exception text. A test checks this.

Auth is checked before the body, so a request with no token and a bad body gets 401, not 422.

## Run it

```bash
pip install -r requirements.txt
pytest -q                        # 18 tests, no server needed

uvicorn app:app --port 8000      # terminal 1
bash demo.sh                     # terminal 2: checks all nine codes against the live server
```

`demo.sh` prints one line per code, `ok` or `FAIL`, and exits non-zero if any code is wrong.

## Why it matters to a business

Correct status codes cut support cost. A client's developer who gets 403 knows to ask their admin for access; one who gets 409 knows the order already went through and must not retry it (no double shipment, no double charge); one who gets 500 knows to open a ticket with us. Monitoring also depends on it: alert on a spike in 5xx (our fault), but only watch 4xx (theirs). Mix them up and the on-call engineer gets paged for a customer's typo.

## Trade-off

The tokens are hard-coded strings and the store is an in-memory dict, so data disappears on restart and anyone who reads this file knows the tokens. That keeps the lab about status codes, not auth or databases. A real service would verify signed tokens (such as JWTs), load secrets from the environment, and keep orders in a database, where the 409 check becomes a unique constraint rather than a dictionary lookup. FastAPI's own 404 for an unknown URL still uses its default `{"detail": ...}` shape; only this API's routes use the shared error shape.

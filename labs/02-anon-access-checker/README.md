# Lab 02: anonymous-access checker

**Result:** one command lists which tables a public (anon) key can read, and exits with code 1 if any table leaks rows, so a CI pipeline can block the release.

## The problem

Supabase and other PostgREST-style backends ship a public "anon" key that lives in the browser. That is by design: the key is safe only if every table is protected by grants and Row Level Security (RLS). One table created without RLS, or with a too-broad policy, and anyone who opens the browser dev tools can read it. Nobody notices until a customer or a researcher does.

## What this lab does

`anon_check.py` calls `GET /rest/v1/<table>?select=*&limit=1` with only the anon key, for each table you name, and classifies the answer:

| Verdict | What the API said | What it means |
| --- | --- | --- |
| `EXPOSED` | 200 with rows | The anon key can read real data. Fix this. |
| `NO_ROWS_VISIBLE` | 200, empty list | Allowed, but RLS filtered every row (or the table is empty). Check which. |
| `BLOCKED` | 401 / 403 | The anon role has no grant on the table. |
| `NOT_FOUND` | 404 | Not exposed through the API at all. |
| `ERROR` | anything else | Network failure, 5xx, or a non-JSON body. Reported, never a crash. |

It reads at most one row per table and never prints the key.

The tests use a fake HTTP session, so CI needs no project, no key and no network.

## Run it yourself

Use your own throwaway project only.

```bash
pip install -r requirements.txt
export SUPABASE_URL=https://<your-project>.supabase.co
export SUPABASE_ANON_KEY=<your public anon key>
python anon_check.py profiles orders invoices
echo "exit code: $?"   # 1 means at least one table is exposed

pytest -q              # the tests, no project needed
```

## Why it matters beyond the code

"Is customer data readable by the public?" is the first question in any client security review. This turns it from an opinion into a repeatable check that runs on every release, and the exit code means a leaky table stops the deploy instead of reaching production.

## Trade-off

It only checks the tables you list and only reads (no insert, update or delete probes), so it is a fast smoke test, not a full audit. `NO_ROWS_VISIBLE` cannot tell "RLS worked" from "table is empty"; seeding one test row per table removes that ambiguity.

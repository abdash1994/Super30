# Super30: Forward Deployed Engineering, in public

I'm a product manager (5+ years in enterprise software) training as a **Forward Deployed Engineer / Forward Deployed PM**: the person who sits between a client's business problem and the system that solves it.

This repo is my working log for the Super30 programme. Every change arrives as a pull request with a written spec, a trade-off note and tests.

## What's inside

| Folder | What it is |
| --- | --- |
| [`labs/`](labs) | Small, runnable labs, one concept each (APIs, data, AI, infrastructure, ML). Each lab has a README with the one-line result it proves. |
| [`kavach/`](kavach) | KAVACH, my course project, built like a client engagement: issues as specs, PRs, weekly releases. |
| [`docs/`](docs) | The 60-day plan, architecture decision records and runbooks. |

## Labs

| # | Lab | Result |
| --- | --- | --- |
| 01 | [Slim Docker images](labs/01-docker-slim) | Full vs multi-stage slim image size, measured in CI |
| 02 | [Anonymous-access checker](labs/02-anon-access-checker) | Lists which tables a public key can read; exit code 1 blocks a release if any leak |
| 03 | [AI cost calculator](labs/03-ai-cost-calculator) | Tokens x price x volume into cost per request, per day and per month, models side by side |
| 04 | [Status-code demo API](labs/04-status-codes) | Nine HTTP status codes, one job each, one test per code and a curl script that checks all nine live |
| 05 | [Environment settings](labs/05-env-settings) | dev/test/prod from environment variables; prod refuses unsafe config, fake data only in test |
| 07 | [Transcript to action items](labs/07-action-items) | Schema-checked JSON `{task, owner, due}`, "unassigned" allowed, scored on 10 labelled samples (baseline 94% precision, 83% recall) |
| 08 | [Sync vs async HTTP](labs/08-async-http) | Three 300 ms calls: ~900 ms one after another, ~300 ms with `asyncio.gather`; one failing service does not sink the others |
| 09 | [Embedding similarity](labs/09-embedding-similarity) | Same-model search: 8/8 right; two models with the same vector size: 0/8 right and no error; a model-name check refuses the mix |
| 10 | [Ticket triage eval + agent cap](labs/10-triage-eval) | Keyword baseline: 35/50 tickets (70%) in the right queue, 12 to a human, 3 misrouted; a looping agent is stopped at 5 turns and escalated |
| 11 | [Rolling z-score anomaly detector](labs/11-rolling-zscore) | 14-day window, threshold 3: 3/3 incidents caught, 0 false alarms in 90 days; an earlier incident in the window halves the next one's z-score |
| 12 | [Query plan before and after an index](labs/12-explain-index) | One customer's 7 orders out of 50,000: full scan to index search, ~2,500x less work; wrapping the column in a function brings the full scan back; two indexes make inserts 1.6x costlier |
| 13 | [Prompt v1 vs v2](labs/13-prompt-ab) | Same 20 tickets: v1 8/20 (11 unparseable), v2 17/20; item-by-item diff shows 10 fixed, 1 broken; edited prompts cannot keep an old score |
| 14 | [Plain English to SQL, guarded](labs/14-text-to-sql) | 12 questions: 6/7 safe ones right, 5/5 dangerous answers (DELETE, DROP, stacked statement, salary table, runaway join) stopped; all 5 still stopped with the validator off |
| 15 | [File agent with an allowlist and confirmation](labs/15-file-agent-guardrails) | 8 tasks: 6/6 harmful requests stopped (deletes, a prompt-injected delete, path escapes, an emptying write, a shell command), 2/2 useful tasks done, 0 files deleted |
| 16 | [Cache-aside with a hit ratio](labs/16-cache-aside) | 5,000 skewed reads: 81.2% hit ratio, database reads 5,000 to 939; 20 slots or a 5 s TTL drops it to ~47%; without delete-on-write the old price is served until the TTL ends |
| 20 | [PDF cleaning plus query rewriting](labs/20-pdf-clean-rewrite) | 10 handbook questions: right paragraph 2/10 on raw PDF text, 5/10 after cleaning, 10/10 with query rewriting; raw text answers "confidential files" with the page footer |

## How I work

- **Issues first.** Every build starts as an issue with acceptance criteria.
- **Pull requests always,** with what changed, why, the trade-off, and how to check it.
- **Conventional commits** (`feat:`, `fix:`, `test:`, `docs:`, `ci:`).
- **CI on every push.** Each lab's tests run automatically.
- **Weekly releases** with a changelog.

The plan I'm following is in [`docs/60-day-plan.md`](docs/60-day-plan.md).

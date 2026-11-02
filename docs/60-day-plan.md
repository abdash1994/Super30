# 60-day build plan (3 Nov 2026 to 1 Jan 2027)

One real, reviewed build a day. `labs` = a self-contained lab in `labs/NN-name/`. `kavach` = the course project in `kavach/`. Sundays are release days. When a KAVACH course task arrives, it replaces that day's kavach row.

| Day | Date | Where | Build |
| --- | --- | --- | --- |
| 1 | Tue 3 Nov | labs | Lab 01: slim multi-stage Docker image (full vs slim size measured in CI) |
| 2 | Wed 4 Nov | labs | Lab 02: anonymous-access checker that tests which tables a public key can read (own throwaway project, mocked in tests) |
| 3 | Thu 5 Nov | kavach | Scaffold a FastAPI service with a /v1 router, a health check and a versioning policy in the README |
| 4 | Fri 6 Nov | labs | Lab 03: AI cost calculator CLI (tokens per request x price x volume, prices as inputs) |
| 5 | Sat 7 Nov | labs | Lab 04: status-code demo API (200, 201, 400, 401, 403, 404, 409, 422, 500) plus a curl script |
| 6 | Sun 8 Nov | labs | Release v0.1.0. Lab 05: dev/test/prod settings from environment, fake data only in test |
| 7 | Mon 9 Nov | kavach | Pydantic request models with Field constraints and a test for every rejected case |
| 8 | Tue 10 Nov | kavach | Agent tool that calls the KAVACH API, with timeouts, retries and a structured error returned to the agent (LLM call mocked in tests) |
| 9 | Wed 11 Nov | labs | Lab 06: mini chat over WebSocket vs SSE, with a README note on when to pick which |
| 10 | Thu 12 Nov | labs | Lab 07: transcript to action items via JSON-schema output, allowing "unassigned", evaluated on 10 samples |
| 11 | Fri 13 Nov | labs | Lab 08: three HTTP calls, sync vs asyncio.gather, timed |
| 12 | Sat 14 Nov | labs | Lab 09: cosine similarity on embeddings, and what breaks when two models are mixed (fixture vectors in tests) |
| 13 | Sun 15 Nov | labs | Release v0.2.0. Lab 10: ticket triage eval on 50 labelled examples, and an agent with a max-iterations cap |
| 14 | Mon 16 Nov | kavach | Refactor into routers, services and schemas, with tests unchanged and green |
| 15 | Tue 17 Nov | labs | Lab 11: rolling z-score anomaly detector with a chart |
| 16 | Wed 18 Nov | labs | Lab 12: EXPLAIN ANALYZE on a seeded table, before and after an index |
| 17 | Thu 19 Nov | labs | Lab 13: prompt v1 vs v2 scored on the same small eval set |
| 18 | Fri 20 Nov | labs | Lab 14: plain English to SQL with a read-only user and query validation |
| 19 | Sat 21 Nov | labs | Lab 15: agent with an allowlisted file tool and a confirmation step; test proves delete is blocked |
| 20 | Sun 22 Nov | labs | Release v0.3.0. Lab 16: cache-aside with a hit-ratio counter |
| 21 | Mon 23 Nov | labs | Lab 17: hybrid search (BM25 plus vectors, reciprocal rank fusion) with an exact-code test case |
| 22 | Tue 24 Nov | labs | Lab 18: metadata filters on vector search, with a regression test |
| 23 | Wed 25 Nov | kavach | README rewrite: problem, demo, architecture diagram, how to run, decision log |
| 24 | Thu 26 Nov | labs | Lab 19: a small automation that logs cost per run |
| 25 | Fri 27 Nov | labs | Lab 20: PDF cleaning pipeline plus query rewriting |
| 26 | Sat 28 Nov | kavach | Explainer endpoint that turns a decision into plain English with its evidence |
| 27 | Sun 29 Nov | labs | Release v0.4.0. Lab 21: RAG eval harness (recall@k and faithfulness on 20 questions) |
| 28 | Mon 30 Nov | kavach | Tests for LLM-calling code with mocks and schema checks, plus one consistent error JSON |
| 29 | Tue 1 Dec | labs | Lab 22: vector store comparison on the same data (setup, latency, recall) |
| 30 | Wed 2 Dec | labs | Lab 23: small vs large model on one task (accuracy, latency, cost per 1,000 calls) |
| 31 | Thu 3 Dec | kavach | Cache a hot endpoint, document the staleness rule, measure before and after |
| 32 | Fri 4 Dec | labs | Lab 24: token counter and prompt-trimming report |
| 33 | Sat 5 Dec | labs | Lab 25: harden Lab 14 SQL safety, plus a JOINs demo dataset |
| 34 | Sun 6 Dec | kavach | Release v0.5.0. Architecture decision record: monolith first |
| 35 | Mon 7 Dec | kavach | Background worker for slow jobs (retries, dead-letter) and an idempotency key on POST |
| 36 | Tue 8 Dec | labs | Lab 26: the same prompt at temperature 0 and 1, outputs compared |
| 37 | Wed 9 Dec | labs | Lab 27: request timing breakdown (DNS, connect, TLS, first byte) |
| 38 | Thu 10 Dec | kavach | ADR: one real trade-off, covering options, choice, reason and cost |
| 39 | Fri 11 Dec | kavach | Error catalogue: codes, messages and a docs page |
| 40 | Sat 12 Dec | kavach | Password hashing, JWT and roles, with tests for 401 vs 403 |
| 41 | Sun 13 Dec | kavach | Release v0.6.0. Rate limiting and CORS config with tests |
| 42 | Mon 14 Dec | kavach | Docker Compose: API, Postgres, Redis and worker up with one command |
| 43 | Tue 15 Dec | kavach | Deployment guide and smoke-test workflow |
| 44 | Wed 16 Dec | kavach | Structured logs, request IDs and a metrics endpoint |
| 45 | Thu 17 Dec | kavach | Load-test script at expected peak, P50/P95/P99 report |
| 46 | Fri 18 Dec | kavach | SLO, error budget, alert rules, runbook for the top three incidents |
| 47 | Sat 19 Dec | kavach | Security pass: dependency and secret scans, STRIDE threat-model table |
| 48 | Sun 20 Dec | kavach | Release v0.7.0. Profile README refresh |
| 49 | Mon 21 Dec | labs | Lab 28: baseline model with a time-based split, PR-AUC against the no-skill line |
| 50 | Tue 22 Dec | labs | Lab 29: threshold picked from the cost of false positives vs false negatives |
| 51 | Wed 23 Dec | labs | Lab 30: drift check (PSI) across two time windows |
| 52 | Thu 24 Dec | kavach | Model or decision card: data, metrics, limits, owners |
| 53 | Fri 25 Dec | labs | Light day: lab index README and issue tidy-up |
| 54 | Sat 26 Dec | kavach | Eval suite in CI that fails the build if quality drops below a threshold |
| 55 | Sun 27 Dec | kavach | Release v0.8.0. Demo video linked in the README |
| 56 | Mon 28 Dec | kavach | Feature flag for a risky change, with rollback tested |
| 57 | Tue 29 Dec | kavach | Cost report: cost per 1,000 requests, by component |
| 58 | Wed 30 Dec | kavach | Case-study README: problem, architecture, results, what next |
| 59 | Thu 31 Dec | both | Triage every open issue; 2027 roadmap as issues |
| 60 | Fri 1 Jan | both | Release v1.0.0 and a 60-day recap |

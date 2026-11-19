# Changelog

One release every Sunday. Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.2.0] - 2026-11-15

Week 2 (Days 7 to 13).

### Added

- KAVACH agent tool: calls the KAVACH API with timeouts, retries and a structured error returned to the agent (#16).
- Lab 07: transcript to action items via JSON-schema output, "unassigned" allowed, scored on 10 labelled samples (#18).
- Lab 08: three HTTP calls, one after another vs `asyncio.gather`, timed; one failing call does not sink the others (#20).
- Lab 09: cosine similarity on embeddings, the silent failure when two models are mixed, and a model-name guard (#22).
- Lab 10: ticket triage scored on 50 labelled tickets (keyword baseline 70%, 65% floor enforced in CI), and an agent loop with a max-iterations cap that escalates instead of looping.

### Pending

- KAVACH FastAPI scaffold (Day 3) is still open for review in #6.
- KAVACH Pydantic request models (Day 7) are still open for review in #14.
- Lab 06 (WebSocket vs SSE, Day 9) was not built this week; carried over.

## [0.1.0] - 2026-11-08

Week 1 (Days 1 to 6).

### Added

- Lab 01: full vs multi-stage slim Docker image, sizes measured in CI.
- Lab 02: anonymous-access checker for public API keys, exits 1 if any table leaks.
- Lab 03: AI cost calculator CLI (tokens x price x volume, models side by side).
- Lab 04: status-code demo API with one test per code and a live curl script.
- Lab 05: dev/test/prod settings from environment variables, unsafe prod config refused, fake data only in test.
- Repo setup: CI for every lab, PR and issue templates, secret scanning pre-commit hook, 60-day plan.

### Pending

- KAVACH FastAPI scaffold (Day 3) is still open for review in #6.

# KAVACH

My Super30 course project, built the way a client engagement runs: a requirement, a spec, then small reviewed changes.

The KAVACH video series on my YouTube channel, Problem to Prod, walks through each stage.

**Result: `POST /v1/explain` turns a fraud decision into plain English with its evidence; 66 tests pass in CI, including one that proves every number in the explanation comes from the decision.**

## Layout

```
app/
  main.py            create_app(): wires the routers together, nothing else
  routers/           thin HTTP layer: parse the request, call a service, return it
    health.py        GET /health (unversioned, for infrastructure)
    v1.py            GET /v1/status, POST /v1/explain (versioned, for clients)
  services/          business logic; never imports FastAPI
    status.py        builds the health and status answers
    decisions.py     in-memory decision store (seeded with one demo decision)
    explainer.py     decision -> plain-English summary and reasons
  schemas/           data shapes in and out
    requests.py      ScoreRequest, ExplainRequest (strict input rules)
    responses.py     HealthResponse, StatusResponse (the response contract)
    decisions.py     Decision, Signal, ExplanationResponse
tests/
  test_api.py        endpoints, versioning rules (unchanged by the refactor)
  test_schemas.py    one rejection test per request rule (unchanged)
  test_layout.py     fails if a service imports FastAPI or a schema imports a service
  test_explain.py    explainer templates, evidence numbers, /v1/explain errors
```

Request rules and why each exists: [`docs/request-models.md`](docs/request-models.md).
How decisions are explained, and why templates instead of an LLM: [`docs/explainer.md`](docs/explainer.md).

Rule of thumb: a new endpoint is one function in `routers/`, its logic in `services/`, and its input and output models in `schemas/`.

## Run it

```bash
cd kavach
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
pytest -q                          # run the tests
uvicorn app.main:app --reload      # then open http://127.0.0.1:8000/docs
```

## Endpoints

| Method | Path | Versioned? | Purpose |
| --- | --- | --- | --- |
| GET | `/health` | No | Liveness: "is the process up?" For load balancers and uptime monitors |
| GET | `/v1/status` | Yes | Which service, API version and build a client is talking to |
| POST | `/v1/explain` | Yes | A past decision in plain English, biggest reasons first, each with observed value and threshold. 404 if unknown |

## Versioning policy

1. **Every business endpoint lives under a version prefix** (`/v1/...`). There are no unversioned business routes; a test enforces that `/status` returns 404.
2. **Ops endpoints stay unversioned.** `/health` is called by infrastructure, not clients, so it never moves.
3. **Within a version, changes are additive only:** new endpoints, new optional request fields, new response fields. Clients must ignore fields they don't know.
4. **A breaking change means a new version.** Removing or renaming a field, changing a type, or tightening validation goes in a new router (`app/routers/v2.py`) mounted at `/v2`. The old version keeps running.
5. **Deprecation window:** an old version is announced as deprecated in the changelog and kept for at least 90 days (or until every known client has moved) before removal.
6. **Build number is separate from API version.** `build` in `/v1/status` follows semver for releases (`0.1.0`); `api_version` only changes on a breaking change.

## Why it matters to a business

A client integrating with KAVACH needs to know their integration won't break on a Tuesday because we renamed a field. URL versioning makes the contract visible in every request, so we can ship fast inside `/v1` and still make breaking changes later without a coordinated outage.

## Why the layers matter to a business

When the fraud model, a database or a second client channel (a batch job, a CLI) arrives, the logic in `services/` can be reused and tested without a web server, and the HTTP layer can change without touching the rules. Changes stay small and reviews stay fast, which is what keeps a client engagement shipping weekly.

## Trade-off: layers

More files for a service this small: a status endpoint now touches three folders. I accepted that now, while there are two endpoints and the move is cheap, rather than later when `/v1/score` and `/v1/explain` would have to be untangled from route functions.

## Trade-off: versioning

I chose URL-path versioning (`/v1/...`) over header versioning (`Accept: application/vnd.kavach.v1+json`). Path versioning is easier to see in logs, curl and browser docs, and easier for a client to get right. The cost is that a new version duplicates routes, and URLs change between versions. For a young API with few clients, visibility wins.

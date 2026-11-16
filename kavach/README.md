# KAVACH

My Super30 course project, built the way a client engagement runs: a requirement, a spec, then small reviewed changes.

The KAVACH video series on my YouTube channel, Problem to Prod, walks through each stage.

**Result: a running API skeleton with a `/health` check and a versioned `/v1` router, tested in CI.**

## What's here

| Path | What it does |
| --- | --- |
| `app/main.py` | Creates the FastAPI app, mounts the v1 router at `/v1`, serves `/health` |
| `app/routers/v1.py` | Version 1 of the public API. Today: `GET /v1/status` |
| `tests/test_api.py` | Checks health, the v1 status response, and that unversioned or unknown-version routes return 404 |

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

## Versioning policy

1. **Every business endpoint lives under a version prefix** (`/v1/...`). There are no unversioned business routes; a test enforces that `/status` returns 404.
2. **Ops endpoints stay unversioned.** `/health` is called by infrastructure, not clients, so it never moves.
3. **Within a version, changes are additive only:** new endpoints, new optional request fields, new response fields. Clients must ignore fields they don't know.
4. **A breaking change means a new version.** Removing or renaming a field, changing a type, or tightening validation goes in a new router (`app/routers/v2.py`) mounted at `/v2`. The old version keeps running.
5. **Deprecation window:** an old version is announced as deprecated in the changelog and kept for at least 90 days (or until every known client has moved) before removal.
6. **Build number is separate from API version.** `build` in `/v1/status` follows semver for releases (`0.1.0`); `api_version` only changes on a breaking change.

## Why it matters to a business

A client integrating with KAVACH needs to know their integration won't break on a Tuesday because we renamed a field. URL versioning makes the contract visible in every request, so we can ship fast inside `/v1` and still make breaking changes later without a coordinated outage.

## Trade-off

I chose URL-path versioning (`/v1/...`) over header versioning (`Accept: application/vnd.kavach.v1+json`). Path versioning is easier to see in logs, curl and browser docs, and easier for a client to get right. The cost is that a new version duplicates routes, and URLs change between versions. For a young API with few clients, visibility wins.

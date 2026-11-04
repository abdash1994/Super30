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

## How I work

- **Issues first.** Every build starts as an issue with acceptance criteria.
- **Pull requests always,** with what changed, why, the trade-off, and how to check it.
- **Conventional commits** (`feat:`, `fix:`, `test:`, `docs:`, `ci:`).
- **CI on every push.** Each lab's tests run automatically.
- **Weekly releases** with a changelog.

The plan I'm following is in [`docs/60-day-plan.md`](docs/60-day-plan.md).

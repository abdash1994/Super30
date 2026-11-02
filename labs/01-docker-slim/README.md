# Lab 01: slim Docker images

**Result:** full image ___ MB, slim multi-stage image ___ MB. *(Numbers are measured automatically in CI. Copy them from the run summary into this line.)*

## The problem

The default `python:3.11` image includes compilers, docs and tools the running app never uses. Every extra megabyte is pulled on every deploy, every scale-up and every rollback, and every extra package is something a security scanner can flag.

## What this lab does

The same tiny FastAPI app is built two ways:

| File | Approach |
| --- | --- |
| `Dockerfile.full` | One stage on the full `python:3.11` image |
| `Dockerfile` | Two stages: install in a builder, copy only what's needed onto `python:3.11-slim`, run as a non-root user |

CI builds both, records the sizes in the run summary, starts the slim container and calls `/health` to prove it still works.

## Run it yourself

```bash
docker build -f Dockerfile.full -t lab01:full .
docker build -t lab01:slim .
docker images | grep lab01
docker run -p 8000:8000 lab01:slim   # then open http://localhost:8000/health
```

## Why it matters beyond the code

Smaller images mean faster deploys, faster autoscaling when traffic spikes, quicker rollbacks, and fewer findings in a client's security review. In an enterprise deployment, that last one can be the difference between a two-day and a two-week approval.

## Trade-off

The slim base leaves out build tools. If a dependency ever needs to compile C extensions, that happens in the builder stage, which is exactly why there are two stages.

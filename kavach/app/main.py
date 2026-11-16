"""Entry point: `uvicorn app.main:app --reload` from inside kavach/."""

from fastapi import FastAPI

from app import __version__
from app.routers import v1

app = FastAPI(title="KAVACH API", version=__version__)

# Versioned business endpoints.
app.include_router(v1.router, prefix="/v1")


@app.get("/health", tags=["ops"])
def health() -> dict:
    """Liveness check for load balancers and uptime monitors.

    Deliberately unversioned and dependency-free: it answers "is the process
    up?", not "is the database up?".
    """
    return {"status": "ok"}

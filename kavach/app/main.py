"""Entry point: `uvicorn app.main:app --reload` from inside kavach/.

This file only wires routers together. Endpoints live in app/routers,
business logic in app/services, data shapes in app/schemas.
"""

from fastapi import FastAPI

from app import __version__
from app.routers import health, v1


def create_app() -> FastAPI:
    app = FastAPI(title="KAVACH API", version=__version__)
    app.include_router(health.router)  # /health, unversioned
    app.include_router(v1.router, prefix="/v1")  # versioned business endpoints
    return app


app = create_app()

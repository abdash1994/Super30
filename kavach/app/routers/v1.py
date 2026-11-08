"""Version 1 of the public KAVACH API.

Everything a client depends on lives under /v1. Breaking changes go in a new
router (v2.py) mounted at /v2, so existing clients keep working.
"""

from fastapi import APIRouter

from app import __version__

API_VERSION = "v1"

router = APIRouter(tags=["v1"])


@router.get("/status")
def status() -> dict:
    """Tell a client which service and API version it is talking to."""
    return {
        "service": "kavach",
        "api_version": API_VERSION,
        "build": __version__,
    }

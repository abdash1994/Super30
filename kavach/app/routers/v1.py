"""Version 1 of the public KAVACH API.

Everything a client depends on lives under /v1. Breaking changes go in a new
router (v2.py) mounted at /v2, so existing clients keep working.

Routes here stay thin: no business logic, just a call into app.services.
"""

from fastapi import APIRouter

from app.schemas import StatusResponse
from app.services import status as status_service

API_VERSION = "v1"

router = APIRouter(tags=["v1"])


@router.get("/status", response_model=StatusResponse)
def status() -> StatusResponse:
    """Tell a client which service and API version it is talking to."""
    return status_service.status(API_VERSION)

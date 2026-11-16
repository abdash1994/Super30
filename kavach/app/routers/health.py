"""Ops endpoints. Deliberately unversioned: infrastructure calls them, not clients."""

from fastapi import APIRouter

from app.schemas import HealthResponse
from app.services import status as status_service

router = APIRouter(tags=["ops"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness check for load balancers and uptime monitors."""
    return status_service.health()

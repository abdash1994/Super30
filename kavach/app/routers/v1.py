"""Version 1 of the public KAVACH API.

Everything a client depends on lives under /v1. Breaking changes go in a new
router (v2.py) mounted at /v2, so existing clients keep working.

Routes here stay thin: no business logic, just a call into app.services.
"""

from fastapi import APIRouter, HTTPException

from app.schemas import ExplainRequest, ExplanationResponse, StatusResponse
from app.services import decisions as decision_service
from app.services import explainer
from app.services import status as status_service

API_VERSION = "v1"

router = APIRouter(tags=["v1"])


@router.get("/status", response_model=StatusResponse)
def status() -> StatusResponse:
    """Tell a client which service and API version it is talking to."""
    return status_service.status(API_VERSION)


@router.post("/explain", response_model=ExplanationResponse)
def explain(request: ExplainRequest) -> ExplanationResponse:
    """Explain a past decision in plain English, with the evidence behind it."""
    decision = decision_service.store.get(request.transaction_id)
    if decision is None:
        raise HTTPException(
            status_code=404,
            detail=f"No decision found for transaction_id {request.transaction_id}",
        )
    return explainer.explain(decision, max_reasons=request.max_reasons)

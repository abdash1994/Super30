"""What the service reports about itself."""

from app import __version__
from app.schemas import HealthResponse, StatusResponse

SERVICE_NAME = "kavach"


def health() -> HealthResponse:
    """Liveness only: "is the process up?", not "is the database up?"."""
    return HealthResponse(status="ok")


def status(api_version: str) -> StatusResponse:
    """Which service, API version and build a client is talking to."""
    return StatusResponse(
        service=SERVICE_NAME,
        api_version=api_version,
        build=__version__,
    )

"""Response models: what the API promises to send back.

Declaring them as `response_model` on each route means FastAPI checks every
response against the contract and documents it in /docs.
"""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class StatusResponse(BaseModel):
    service: str
    api_version: str
    build: str

"""Lab 04: a tiny orders API that returns every common HTTP status code on purpose.

Each status code has exactly one job here:

    200 OK                    read an order that exists
    201 Created               create a new order (with a Location header)
    400 Bad Request           the body is not even valid JSON
    401 Unauthorized          no token, or a token we don't recognise
    403 Forbidden             a valid token that is not allowed to do this
    404 Not Found             the order does not exist
    409 Conflict              the order id is already taken
    422 Unprocessable Content valid JSON that breaks the rules (quantity 0, missing field)
    500 Internal Server Error a bug on our side, returned without a stack trace

Every error uses one shape: {"error": {"status": ..., "code": ..., "message": ...}}.
Run it with:  uvicorn app:app --reload
"""

from typing import Dict, Optional

from fastapi import Depends, FastAPI, Header, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Demo tokens only. A real service would verify a signed token (e.g. a JWT).
TOKENS = {
    "viewer-token": "viewer",  # can read
    "admin-token": "admin",  # can read and write
}


class OrderIn(BaseModel):
    order_id: str = Field(min_length=3, max_length=40, pattern=r"^[a-z0-9-]+$")
    item: str = Field(min_length=1, max_length=100)
    quantity: int = Field(gt=0, le=1000)


class ApiError(Exception):
    """Raised by our own code; turned into the shared error shape."""

    def __init__(self, status: int, code: str, message: str, headers: Optional[Dict[str, str]] = None):
        self.status = status
        self.code = code
        self.message = message
        self.headers = headers


def error_body(status: int, code: str, message: str, **extra) -> dict:
    body = {"status": status, "code": code, "message": message}
    body.update(extra)
    return {"error": body}


def create_app() -> FastAPI:
    """Build a fresh app with its own in-memory store (tests get a clean one each time)."""
    app = FastAPI(title="Lab 04: status-code demo")
    orders: Dict[str, dict] = {
        "ord-001": {"order_id": "ord-001", "item": "notebook", "quantity": 2},
    }

    def current_role(authorization: Optional[str] = Header(default=None)) -> str:
        if not authorization or not authorization.startswith("Bearer "):
            raise ApiError(401, "missing_token", "Send 'Authorization: Bearer <token>'.",
                           headers={"WWW-Authenticate": "Bearer"})
        role = TOKENS.get(authorization[len("Bearer "):])
        if role is None:
            raise ApiError(401, "invalid_token", "That token is not recognised.",
                           headers={"WWW-Authenticate": "Bearer"})
        return role

    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content=error_body(exc.status, exc.code, exc.message),
                            headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        # FastAPI reports unparseable JSON as a validation error; we split it out as 400,
        # because the client sent something we could not even read.
        if any(e.get("type") == "json_invalid" for e in errors):
            return JSONResponse(status_code=400,
                                content=error_body(400, "malformed_json", "The request body is not valid JSON."))
        fields = [{"field": ".".join(str(p) for p in e.get("loc", ()) if p != "body"),
                   "message": e.get("msg", "")} for e in errors]
        return JSONResponse(status_code=422,
                            content=error_body(422, "validation_failed",
                                               "The request is valid JSON but breaks the rules.", fields=fields))

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        # Never leak the stack trace to the client; log it on the server instead.
        return JSONResponse(status_code=500,
                            content=error_body(500, "internal_error", "Something went wrong on our side."))

    @app.get("/orders/{order_id}")
    def get_order(order_id: str, role: str = Depends(current_role)) -> dict:
        if order_id not in orders:
            raise ApiError(404, "order_not_found", f"No order with id '{order_id}'.")
        return orders[order_id]

    @app.post("/orders", status_code=201)
    def create_order(order: OrderIn, response: Response, role: str = Depends(current_role)) -> dict:
        if role != "admin":
            raise ApiError(403, "forbidden", "Your token can read orders but not create them.")
        if order.order_id in orders:
            raise ApiError(409, "order_exists", f"Order '{order.order_id}' already exists.")
        orders[order.order_id] = order.model_dump()
        response.headers["Location"] = f"/orders/{order.order_id}"
        return orders[order.order_id]

    @app.get("/simulate/crash")
    def crash() -> dict:
        raise RuntimeError("simulated bug: this message must not reach the client")

    return app


app = create_app()

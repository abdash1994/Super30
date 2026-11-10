"""An agent tool that asks the KAVACH API to score a payment for fraud risk.

An LLM agent decides *when* to call this tool. This module decides *how*:
a hard timeout on every attempt, a small number of retries for failures that
are worth retrying, and a structured error the agent can read when the call
still fails. The tool never raises, because an exception inside a tool call
usually ends the whole agent run instead of letting the agent recover.

The tool talks to POST /v1/score (request contract: kavach/app/schemas.py).
"""

from __future__ import annotations

import time
from typing import Any, Callable

import httpx

TOOL_NAME = "score_transaction"

# Tool definition in the shape LLM APIs expect (name, description, JSON
# Schema for the input). Kept small: the agent fills in the fields it knows,
# the KAVACH API validates the rest and the tool reports what it rejected.
TOOL_SPEC: dict[str, Any] = {
    "name": TOOL_NAME,
    "description": (
        "Score one payment transaction for fraud risk with the KAVACH API. "
        "Returns ok=true with the risk result, or ok=false with an error "
        "code, a message and whether retrying later could help."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "transaction_id": {"type": "string"},
            "customer_id": {"type": "string"},
            "amount_inr": {"type": "string", "description": "Decimal as text, e.g. '1499.00'"},
            "merchant_category": {"type": "string"},
            "payment_channel": {"type": "string"},
        },
        "required": ["transaction_id", "customer_id", "amount_inr"],
        "additionalProperties": True,
    },
}

# Status codes where the same request may succeed a moment later.
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def _error(code: str, message: str, *, retryable: bool, attempts: int,
           status: int | None = None, details: Any = None) -> dict[str, Any]:
    """The one error shape the agent ever sees."""
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "retryable": retryable,
            "status": status,
            "attempts": attempts,
            "details": details,
        },
    }


def _retry_after_seconds(response: httpx.Response) -> float | None:
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None  # HTTP-date form: fall back to our own backoff


class KavachScoreTool:
    """Callable tool: `tool(arguments) -> dict`, safe to hand to an agent loop."""

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        timeout_s: float = 2.0,
        max_attempts: int = 3,
        backoff_s: float = 0.5,
        max_backoff_s: float = 4.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self.max_attempts = max_attempts
        self.backoff_s = backoff_s
        self.max_backoff_s = max_backoff_s
        self.sleep = sleep
        self.client = httpx.Client(
            base_url=base_url,
            headers=headers,
            timeout=httpx.Timeout(timeout_s),
            transport=transport,
        )

    def _wait(self, attempt: int, response: httpx.Response | None = None) -> None:
        delay = self.backoff_s * (2 ** (attempt - 1))  # 0.5s, 1s, 2s ...
        if response is not None:
            hinted = _retry_after_seconds(response)
            if hinted is not None:
                delay = hinted
        self.sleep(min(delay, self.max_backoff_s))

    def __call__(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(arguments, dict) or not arguments.get("transaction_id"):
            return _error("invalid_arguments", "transaction_id is required",
                          retryable=False, attempts=0)

        # Same key on every attempt, so a retry after a lost response cannot
        # score (and audit-log) the same payment twice.
        idempotency_key = str(arguments["transaction_id"])
        last: dict[str, Any] = {}

        for attempt in range(1, self.max_attempts + 1):
            is_last = attempt == self.max_attempts
            try:
                response = self.client.post(
                    "/v1/score",
                    json=arguments,
                    headers={"Idempotency-Key": idempotency_key},
                )
            except httpx.TimeoutException:
                last = _error("timeout", "KAVACH did not answer in time",
                              retryable=True, attempts=attempt)
                if not is_last:
                    self._wait(attempt)
                continue
            except httpx.TransportError as exc:
                last = _error("unreachable", f"Could not reach KAVACH: {type(exc).__name__}",
                              retryable=True, attempts=attempt)
                if not is_last:
                    self._wait(attempt)
                continue

            if response.status_code in RETRYABLE_STATUS:
                last = _error("upstream_unavailable",
                              f"KAVACH returned {response.status_code}",
                              retryable=True, attempts=attempt,
                              status=response.status_code)
                if not is_last:
                    self._wait(attempt, response)
                continue

            if response.status_code >= 400:
                # The request itself is wrong. Retrying sends the same wrong
                # request, so hand the API's reasons back to the agent instead.
                try:
                    details = response.json()
                except ValueError:
                    details = response.text[:500]
                code = "invalid_request" if response.status_code in (400, 422) else "rejected"
                return _error(code, f"KAVACH rejected the request ({response.status_code})",
                              retryable=False, attempts=attempt,
                              status=response.status_code, details=details)

            try:
                data = response.json()
            except ValueError:
                return _error("bad_response", "KAVACH answered with something that is not JSON",
                              retryable=False, attempts=attempt,
                              status=response.status_code)
            return {"ok": True, "attempts": attempt, "data": data}

        return last

    def close(self) -> None:
        self.client.close()

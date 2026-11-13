"""Fake CRM, billing and ticket services with a fixed delay, so the lab runs with no network.

The sync and async transports wait the same amount of time; the only difference
is that the async one uses asyncio.sleep, which lets other calls run meanwhile,
exactly like a real network wait does.
"""

from __future__ import annotations

import asyncio
import time

import httpx

# How long each fake service takes to answer, in seconds.
DELAYS = {
    "crm.example": 0.30,
    "billing.example": 0.30,
    "tickets.example": 0.30,
}

URLS = [
    "https://crm.example/customers/42",
    "https://billing.example/customers/42/charges",
    "https://tickets.example/customers/42/open",
]


def _respond(request: httpx.Request) -> httpx.Response:
    host = request.url.host
    if host == "down.example":
        return httpx.Response(503, json={"error": "service unavailable"})
    return httpx.Response(200, json={"service": host, "path": request.url.path})


def sync_transport(delays: dict[str, float] = DELAYS) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        time.sleep(delays.get(request.url.host, 0.0))
        return _respond(request)

    return httpx.MockTransport(handler)


def async_transport(delays: dict[str, float] = DELAYS) -> httpx.MockTransport:
    async def handler(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(delays.get(request.url.host, 0.0))
        return _respond(request)

    return httpx.MockTransport(handler)

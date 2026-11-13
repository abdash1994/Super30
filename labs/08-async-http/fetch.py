"""Lab 08: three HTTP calls, one after another vs all at once with asyncio.gather.

The scenario: a support assistant answers "why was this customer charged twice?"
and needs three facts before it can reply: the CRM record, the billing history
and the open tickets. Each call waits on a different service.

- fetch_sequential: plain httpx.Client, one call after another. Total time is
  roughly the SUM of the three waits.
- fetch_concurrent: httpx.AsyncClient + asyncio.gather. All three are in flight
  together, so total time is roughly the SLOWEST single wait.

Both return the same list of CallResult in the same order as the input, and
both turn a failure (timeout, refused connection, 5xx) into a result with an
error instead of throwing away the calls that did work.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

import httpx

DEFAULT_TIMEOUT = 2.0  # seconds per call; a slow service must not hold the answer hostage


@dataclass
class CallResult:
    url: str
    status: int | None  # None when there was no HTTP response at all (timeout, DNS, refused)
    seconds: float
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.status is not None and self.status < 400


@dataclass
class Timing:
    mode: str
    total_seconds: float
    results: list[CallResult]


def _result_from(url: str, started: float, response: httpx.Response | None, exc: Exception | None) -> CallResult:
    seconds = time.perf_counter() - started
    if exc is not None:
        return CallResult(url, None, seconds, f"{type(exc).__name__}: {exc}")
    error = f"HTTP {response.status_code}" if response.status_code >= 400 else None
    return CallResult(url, response.status_code, seconds, error)


def _get_one_sync(client: httpx.Client, url: str) -> CallResult:
    started = time.perf_counter()
    try:
        return _result_from(url, started, client.get(url), None)
    except httpx.HTTPError as exc:
        return _result_from(url, started, None, exc)


async def _get_one_async(client: httpx.AsyncClient, url: str) -> CallResult:
    started = time.perf_counter()
    try:
        return _result_from(url, started, await client.get(url), None)
    except httpx.HTTPError as exc:
        return _result_from(url, started, None, exc)


def fetch_sequential(urls: list[str], client: httpx.Client) -> Timing:
    started = time.perf_counter()
    results = [_get_one_sync(client, url) for url in urls]
    return Timing("sequential", time.perf_counter() - started, results)


async def fetch_concurrent(urls: list[str], client: httpx.AsyncClient) -> Timing:
    started = time.perf_counter()
    # gather keeps the input order. Each task already catches its own HTTP errors,
    # so one failing service cannot cancel the other two.
    results = await asyncio.gather(*(_get_one_async(client, url) for url in urls))
    return Timing("concurrent", time.perf_counter() - started, list(results))


def compare(urls: list[str], transport=None, async_transport=None, timeout: float = DEFAULT_TIMEOUT) -> tuple[Timing, Timing]:
    """Run the same calls both ways and return (sequential, concurrent).

    Pass transports to fake the network (tests and the offline demo do this);
    leave them as None to make real HTTP calls.
    """
    with httpx.Client(transport=transport, timeout=timeout) as client:
        seq = fetch_sequential(urls, client)

    async def run() -> Timing:
        async with httpx.AsyncClient(transport=async_transport, timeout=timeout) as client:
            return await fetch_concurrent(urls, client)

    return seq, asyncio.run(run())

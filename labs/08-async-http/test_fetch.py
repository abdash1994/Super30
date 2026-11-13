import asyncio
import os

import httpx

import fake_services
from compare import table
from fetch import CallResult, compare, fetch_concurrent

DELAY = 0.30  # each fake service
URLS = fake_services.URLS


def run_both(urls=URLS, delays=fake_services.DELAYS):
    return compare(
        urls,
        transport=fake_services.sync_transport(delays),
        async_transport=fake_services.async_transport(delays),
    )


# --- the headline: same three calls, different total time -------------------

def test_sequential_takes_about_the_sum_of_the_waits():
    seq, _ = run_both()
    assert seq.total_seconds >= 3 * DELAY * 0.95


def test_concurrent_takes_about_the_slowest_single_wait():
    _, conc = run_both()
    assert conc.total_seconds >= DELAY * 0.95
    # Generous ceiling so a slow CI runner does not make this flaky; the point is "not 3x".
    assert conc.total_seconds < 2 * DELAY


def test_concurrent_is_at_least_twice_as_fast_and_reports_to_ci():
    seq, conc = run_both()
    assert seq.total_seconds / conc.total_seconds >= 2.0

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:  # only set inside GitHub Actions
        with open(summary, "a") as fh:
            fh.write("### Lab 08 timings (3 fake services, 300 ms each)\n\n" + table(seq, conc) + "\n\n")


def test_concurrent_time_follows_the_slowest_service_not_the_sum():
    delays = {"crm.example": 0.05, "billing.example": 0.05, "tickets.example": 0.40}
    seq, conc = run_both(delays=delays)
    assert seq.total_seconds >= 0.50 * 0.95
    assert 0.40 * 0.95 <= conc.total_seconds < 0.50


# --- same answers either way -------------------------------------------------

def test_both_modes_return_the_same_results_in_input_order():
    seq, conc = run_both()
    assert [r.url for r in seq.results] == URLS
    assert [r.url for r in conc.results] == URLS
    assert [r.status for r in seq.results] == [r.status for r in conc.results] == [200, 200, 200]
    assert all(r.ok for r in conc.results)


# --- one bad service does not sink the other two ------------------------------

def test_a_5xx_is_recorded_and_the_other_calls_still_succeed():
    urls = [URLS[0], "https://down.example/x", URLS[2]]
    seq, conc = run_both(urls=urls)
    for timing in (seq, conc):
        assert [r.ok for r in timing.results] == [True, False, True]
        assert timing.results[1].status == 503
        assert timing.results[1].error == "HTTP 503"


def test_a_timeout_becomes_an_error_result_not_an_exception():
    async def handler(request):
        if request.url.host == "billing.example":
            raise httpx.ReadTimeout("took too long", request=request)
        return httpx.Response(200)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetch_concurrent(URLS, client)

    conc = asyncio.run(run())
    assert [r.ok for r in conc.results] == [True, False, True]
    assert conc.results[1].status is None
    assert conc.results[1].error.startswith("ReadTimeout")


def test_call_result_ok_rules():
    assert CallResult("u", 200, 0.1).ok
    assert not CallResult("u", 404, 0.1, "HTTP 404").ok
    assert not CallResult("u", None, 0.1, "ConnectError: refused").ok


def test_table_shows_both_modes_and_the_speedup():
    seq, conc = run_both()
    text = table(seq, conc)
    assert "| sequential |" in text and "| concurrent |" in text
    assert "3/3" in text
    assert "x faster" in text

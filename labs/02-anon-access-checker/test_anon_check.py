"""Tests use a fake HTTP session, so CI needs no Supabase project, key or network."""

import requests

import anon_check as ac

KEY = "anon-test-key-not-real"
URL = "https://example.supabase.co"


class FakeResponse:
    def __init__(self, status_code, body=None, json_error=False):
        self.status_code = status_code
        self._body = body
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise ValueError("not json")
        return self._body


class FakeSession:
    """Maps table name -> FakeResponse (or an exception to raise). Records every call."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def get(self, url, headers=None, params=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "params": params, "timeout": timeout})
        outcome = self.routes[url.rsplit("/", 1)[-1]]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def test_rows_returned_means_exposed():
    session = FakeSession({"profiles": FakeResponse(200, [{"id": 1, "email": "a@b.c"}])})
    result = ac.check_table(session, URL, KEY, "profiles")
    assert result.verdict == ac.EXPOSED
    assert result.rows_seen == 1


def test_empty_list_means_no_rows_visible():
    session = FakeSession({"orders": FakeResponse(200, [])})
    assert ac.check_table(session, URL, KEY, "orders").verdict == ac.NO_ROWS


def test_401_and_403_mean_blocked():
    session = FakeSession({"a": FakeResponse(401, {}), "b": FakeResponse(403, {})})
    assert ac.check_table(session, URL, KEY, "a").verdict == ac.BLOCKED
    assert ac.check_table(session, URL, KEY, "b").verdict == ac.BLOCKED


def test_404_means_not_found():
    session = FakeSession({"ghost": FakeResponse(404, {})})
    assert ac.check_table(session, URL, KEY, "ghost").verdict == ac.NOT_FOUND


def test_network_failure_and_bad_body_are_errors_not_crashes():
    session = FakeSession({
        "down": requests.ConnectionError("boom"),
        "weird": FakeResponse(200, json_error=True),
        "oops": FakeResponse(500, {}),
    })
    for table in ("down", "weird", "oops"):
        assert ac.check_table(session, URL, KEY, table).verdict == ac.ERROR


def test_request_shape_uses_anon_key_reads_one_row_and_sets_timeout():
    session = FakeSession({"profiles": FakeResponse(200, [])})
    ac.check_table(session, URL + "/", KEY, "profiles")
    call = session.calls[0]
    assert call["url"] == "https://example.supabase.co/rest/v1/profiles"
    assert call["headers"] == {"apikey": KEY, "Authorization": f"Bearer {KEY}"}
    assert call["params"] == {"select": "*", "limit": "1"}
    assert call["timeout"] is not None


def test_main_exit_code_and_report_never_leaks_key(capsys):
    session = FakeSession({
        "profiles": FakeResponse(200, [{"id": 1}]),
        "orders": FakeResponse(200, []),
        "secrets": FakeResponse(401, {}),
    })
    env = {"SUPABASE_URL": URL, "SUPABASE_ANON_KEY": KEY}
    code = ac.main(["profiles", "orders", "secrets"], env=env, session=session)
    out = capsys.readouterr().out
    assert code == 1
    assert "1 of 3 tables exposed" in out
    assert KEY not in out


def test_main_exits_zero_when_nothing_exposed():
    session = FakeSession({"orders": FakeResponse(200, [])})
    env = {"SUPABASE_URL": URL, "SUPABASE_ANON_KEY": KEY}
    assert ac.main(["orders"], env=env, session=session) == 0


def test_main_without_config_prints_usage_and_exits_2():
    assert ac.main(["orders"], env={}) == 2

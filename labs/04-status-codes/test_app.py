import pytest
from fastapi.testclient import TestClient

from app import create_app

ADMIN = {"Authorization": "Bearer admin-token"}
VIEWER = {"Authorization": "Bearer viewer-token"}
NEW_ORDER = {"order_id": "ord-002", "item": "pen", "quantity": 3}


@pytest.fixture
def client():
    # A fresh app per test, so one test's orders never leak into another.
    # raise_server_exceptions=False lets us see the 500 response a real client would get.
    return TestClient(create_app(), raise_server_exceptions=False)


# One row per status code, mirroring demo.sh: (expected, method, path, headers, json body, raw body)
CASES = [
    (200, "GET", "/orders/ord-001", VIEWER, None, None),
    (201, "POST", "/orders", ADMIN, NEW_ORDER, None),
    (400, "POST", "/orders", {**ADMIN, "Content-Type": "application/json"}, None, '{"order_id": "ord-9",'),
    (401, "GET", "/orders/ord-001", {}, None, None),
    (403, "POST", "/orders", VIEWER, NEW_ORDER, None),
    (404, "GET", "/orders/ord-404", VIEWER, None, None),
    (409, "POST", "/orders", ADMIN, {"order_id": "ord-001", "item": "pen", "quantity": 1}, None),
    (422, "POST", "/orders", ADMIN, {"order_id": "ord-003", "item": "pen", "quantity": 0}, None),
    (500, "GET", "/simulate/crash", {}, None, None),
]


def test_every_status_code_is_covered():
    assert sorted(c[0] for c in CASES) == [200, 201, 400, 401, 403, 404, 409, 422, 500]


@pytest.mark.parametrize("expected,method,path,headers,body,raw", CASES, ids=[str(c[0]) for c in CASES])
def test_status_code(client, expected, method, path, headers, body, raw):
    r = client.request(method, path, headers=headers, json=body, content=raw)
    assert r.status_code == expected, r.text
    if expected >= 400:
        err = r.json()["error"]
        assert err["status"] == expected
        assert err["code"] and err["message"]


def test_201_returns_location_and_order_is_then_readable(client):
    r = client.post("/orders", headers=ADMIN, json=NEW_ORDER)
    assert r.status_code == 201
    assert r.headers["location"] == "/orders/ord-002"
    assert client.get("/orders/ord-002", headers=VIEWER).json() == NEW_ORDER


def test_creating_the_same_order_twice_is_409_not_a_duplicate(client):
    assert client.post("/orders", headers=ADMIN, json=NEW_ORDER).status_code == 201
    second = client.post("/orders", headers=ADMIN, json={**NEW_ORDER, "quantity": 99})
    assert second.status_code == 409
    # The first order is untouched.
    assert client.get("/orders/ord-002", headers=VIEWER).json()["quantity"] == 3


def test_401_tells_the_client_how_to_authenticate(client):
    r = client.get("/orders/ord-001")
    assert r.headers["www-authenticate"] == "Bearer"
    assert r.json()["error"]["code"] == "missing_token"


def test_unknown_token_is_401_not_403(client):
    r = client.get("/orders/ord-001", headers={"Authorization": "Bearer stolen-or-typo"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_token"


def test_auth_is_checked_before_the_body(client):
    # Bad body and no token: say "who are you?" first, not "your body is wrong".
    r = client.post("/orders", json={"quantity": 0})
    assert r.status_code == 401


def test_422_names_the_fields_that_failed(client):
    r = client.post("/orders", headers=ADMIN, json={"order_id": "ord-003", "quantity": 0})
    assert r.status_code == 422
    fields = {f["field"] for f in r.json()["error"]["fields"]}
    assert fields == {"item", "quantity"}


def test_400_is_only_for_unreadable_json(client):
    r = client.post("/orders", headers={**ADMIN, "Content-Type": "application/json"}, content="not json")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "malformed_json"


def test_500_does_not_leak_internals(client):
    r = client.get("/simulate/crash")
    assert r.status_code == 500
    assert "simulated bug" not in r.text
    assert "Traceback" not in r.text

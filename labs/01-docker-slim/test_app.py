from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_quote_is_versioned_under_v1():
    response = client.get("/v1/quote")
    assert response.status_code == 200
    assert "quote" in response.json()


def test_unknown_route_is_404():
    assert client.get("/nope").status_code == 404

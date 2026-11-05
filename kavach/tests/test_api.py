from fastapi.testclient import TestClient

from app import __version__
from app.main import app

client = TestClient(app)


def test_health_is_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_v1_status_reports_service_and_version():
    response = client.get("/v1/status")
    assert response.status_code == 200
    assert response.json() == {
        "service": "kavach",
        "api_version": "v1",
        "build": __version__,
    }


def test_unversioned_business_route_does_not_exist():
    # Business endpoints must always carry a version prefix.
    assert client.get("/status").status_code == 404


def test_unknown_version_is_404():
    assert client.get("/v2/status").status_code == 404


def test_openapi_lists_versioned_routes():
    paths = client.get("/openapi.json").json()["paths"]
    assert "/v1/status" in paths
    assert "/health" in paths

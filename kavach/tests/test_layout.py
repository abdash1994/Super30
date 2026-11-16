"""Guards for the routers / services / schemas split.

These fail if someone puts business logic back in a route or makes a
service depend on the web framework.
"""

import ast
from pathlib import Path

import app.schemas
from app import __version__
from app.schemas import HealthResponse, StatusResponse
from app.services import status as status_service

APP_DIR = Path(__file__).resolve().parent.parent / "app"


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_services_do_not_import_fastapi():
    for path in (APP_DIR / "services").glob("*.py"):
        assert not any(
            m == "fastapi" or m.startswith("fastapi.") for m in imported_modules(path)
        ), f"{path.name} imports FastAPI; services must not know about HTTP"


def test_schemas_do_not_import_services_or_routers():
    for path in (APP_DIR / "schemas").glob("*.py"):
        for module in imported_modules(path):
            assert not module.startswith(("app.services", "app.routers")), path.name


def test_status_service_works_without_a_web_server():
    assert status_service.health() == HealthResponse(status="ok")
    assert status_service.status("v1") == StatusResponse(
        service="kavach", api_version="v1", build=__version__
    )


def test_request_models_still_import_from_app_schemas():
    # Callers use `from app.schemas import ...`; the move into a package
    # must not break that.
    for name in ("ScoreRequest", "ExplainRequest", "Location"):
        assert hasattr(app.schemas, name)

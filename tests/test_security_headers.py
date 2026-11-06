from fastapi.routing import APIRoute
from fastapi.testclient import TestClient


def test_unhandled_server_error_includes_security_headers():
    from backend.app.main import app

    def raise_internal_error():
        raise RuntimeError("simulated internal failure")

    route = APIRoute("/_audit/unhandled-error", endpoint=raise_internal_error, methods=["GET"])
    app.router.routes.append(route)
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/_audit/unhandled-error")
    finally:
        app.router.routes.remove(route)

    assert response.status_code == 500
    assert response.headers.get("content-security-policy")
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"

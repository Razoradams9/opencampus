from datetime import datetime

from app.core.config import get_settings


def test_health_returns_ok(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "OpenCampus API"
    assert body["version"] == get_settings().version
    assert body["uptime_seconds"] >= 0
    datetime.fromisoformat(body["timestamp"])


def test_health_needs_no_authentication(client):
    assert client.get("/api/health").status_code == 200


def test_cors_allows_dev_frontend(client):
    response = client.get("/api/health", headers={"Origin": "http://localhost:5173"})

    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_unknown_route_is_404(client):
    assert client.get("/api/does-not-exist").status_code == 404
